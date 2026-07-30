"""Selection, comparison and persistence for catalogue refresh jobs."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Literal

import aiosqlite

from src.database.connection import connection_scope
from src.database.media_release_notifications import record_media_release
from src.database.media_search import replace_media_search_terms
from src.database.series_release import _replace_media_seasons
from src.database.series_subscriptions import record_series_release
from src.models import SeriesReleaseSnapshot
from src.release_availability import release_date_has_passed
from src.tmdb_matching import normalize_text
from src.tmdb_models import TmdbMovieDetails

RefreshMode = Literal["daily", "weekly"]
ACTIVE_STATUSES = ("Returning Series", "Planned", "In Production")


@dataclass(frozen=True)
class MediaRefreshCandidate:
    media_id: int
    tmdb_id: int
    title: str
    content_format: str


@dataclass(frozen=True)
class MediaChange:
    field: str
    before: object
    after: object


async def select_due_media_batch(
    mode: RefreshMode,
    *,
    after_id: int = 0,
    limit: int = 50,
    database_url: str | None = None,
) -> list[MediaRefreshCandidate]:
    """Return one stable id-ordered batch without opening a long transaction."""
    if limit <= 0:
        raise ValueError("limit must be positive")
    condition, parameters = _due_condition(mode)
    async with connection_scope(database_url) as connection:
        async with connection.execute(
            f"""
            SELECT id, tmdb_id, title, content_format
            FROM media
            WHERE id > ? AND tmdb_id IS NOT NULL AND {condition}
            ORDER BY id
            LIMIT ?
            """,
            (after_id, *parameters, limit),
        ) as cursor:
            rows = await cursor.fetchall()
    return [
        MediaRefreshCandidate(
            media_id=int(row["id"]),
            tmdb_id=int(row["tmdb_id"]),
            title=str(row["title"]),
            content_format=str(row["content_format"]),
        )
        for row in rows
    ]


async def has_due_media(
    mode: RefreshMode,
    *,
    database_url: str | None = None,
) -> bool:
    condition, parameters = _due_condition(mode)
    async with connection_scope(database_url) as connection:
        async with connection.execute(
            f"""
            SELECT 1 FROM media
            WHERE tmdb_id IS NOT NULL AND {condition}
            LIMIT 1
            """,
            parameters,
        ) as cursor:
            return await cursor.fetchone() is not None


async def get_media_candidate(
    media_id: int,
    *,
    database_url: str | None = None,
) -> MediaRefreshCandidate | None:
    async with connection_scope(database_url) as connection:
        async with connection.execute(
            """
            SELECT id, tmdb_id, title, content_format FROM media
            WHERE id = ? AND content_format = 'series' AND tmdb_id IS NOT NULL
            """,
            (media_id,),
        ) as cursor:
            row = await cursor.fetchone()
    if row is None:
        return None
    return MediaRefreshCandidate(
        int(row["id"]), int(row["tmdb_id"]), row["title"], row["content_format"]
    )


async def get_tmdb_candidates(
    tmdb_id: int,
    *,
    database_url: str | None = None,
) -> list[MediaRefreshCandidate]:
    async with connection_scope(database_url) as connection:
        async with connection.execute(
            """
            SELECT id, tmdb_id, title, content_format FROM media
            WHERE tmdb_id = ? AND content_format = 'series'
            ORDER BY id
            """,
            (tmdb_id,),
        ) as cursor:
            rows = await cursor.fetchall()
    return [
        MediaRefreshCandidate(
            int(row["id"]),
            int(row["tmdb_id"]),
            row["title"],
            row["content_format"],
        )
        for row in rows
    ]


async def preview_media_refresh(
    media_id: int,
    snapshot: SeriesReleaseSnapshot,
    *,
    database_url: str | None = None,
) -> list[MediaChange]:
    async with connection_scope(database_url) as connection:
        return await _collect_changes(connection, media_id, snapshot)


async def save_media_refresh(
    media_id: int,
    snapshot: SeriesReleaseSnapshot,
    mode: RefreshMode,
    *,
    database_url: str | None = None,
) -> list[MediaChange]:
    """Apply one TMDB snapshot in a short transaction and preserve progress."""
    async with connection_scope(database_url) as connection:
        async with connection.execute(
            """
            SELECT COALESCE(available_episode_count, 0), is_released
            FROM media WHERE id = ?
            """,
            (media_id,),
        ) as cursor:
            row = await cursor.fetchone()
        if row is None:
            raise ValueError(f"Media {media_id} does not exist")
        previous_episode_count = int(row[0])
        was_released = bool(row[1])
        changes = await _collect_changes(connection, media_id, snapshot)
        if changes:
            await _replace_media_seasons(connection, media_id, snapshot)
            await _write_metadata(connection, media_id, snapshot, mode)
            is_released = was_released or snapshot.available_episode_count > 0
            if is_released and not was_released:
                await record_media_release(connection, media_id)
            current_episode_count = max(
                previous_episode_count,
                snapshot.available_episode_count,
            )
            last_episode = snapshot.last_episode_to_air
            if was_released:
                await record_series_release(
                    connection,
                    media_id,
                    previous_episode_count,
                    current_episode_count,
                    season_number=(
                        last_episode.season_number if last_episode else None
                    ),
                    episode_number=(
                        last_episode.episode_number if last_episode else None
                    ),
                    active=snapshot.active,
                )
        else:
            await _touch_checked_at(connection, media_id, mode, error=None)
        return changes


async def mark_media_refresh_error(
    media_id: int,
    mode: RefreshMode,
    error: str,
    *,
    database_url: str | None = None,
) -> None:
    async with connection_scope(database_url) as connection:
        await _touch_checked_at(connection, media_id, mode, error=error[:500])


async def save_movie_release_refresh(
    media_id: int,
    snapshot: TmdbMovieDetails,
    *,
    today: date,
    database_url: str | None = None,
) -> list[MediaChange]:
    async with connection_scope(database_url) as connection:
        async with connection.execute(
            "SELECT * FROM media WHERE id = ? AND content_format = 'full_length'",
            (media_id,),
        ) as cursor:
            media = await cursor.fetchone()
        if media is None:
            raise ValueError(f"Movie {media_id} does not exist")

        was_released = bool(media["is_released"])
        has_release_date = bool(snapshot.release_date)
        is_released = (
            was_released
            or snapshot.status == "Released"
            or (
                has_release_date
                and release_date_has_passed(snapshot.release_date, today=today)
            )
        )
        fresh = {
            "title": snapshot.title,
            "original_title": snapshot.original_title,
            "description": snapshot.description,
            "poster_path": snapshot.poster_path,
            "rating": snapshot.rating,
            "release_date": snapshot.release_date,
            "status": snapshot.status,
            "is_released": int(is_released),
        }
        changes = [
            MediaChange(field, media[field], value)
            for field, value in fresh.items()
            if media[field] != value
        ]
        await connection.execute(
            """
            UPDATE media
            SET title = ?, original_title = ?,
                normalized_title = ?, normalized_original_title = ?,
                description = ?, poster_path = ?, rating = ?, release_date = ?,
                status = ?, is_released = ?,
                telegram_poster_file_id = CASE
                    WHEN poster_path IS NOT ? THEN NULL
                    ELSE telegram_poster_file_id
                END,
                tmdb_release_checked_at = CURRENT_TIMESTAMP,
                tmdb_refresh_error = NULL, last_updated = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (
                snapshot.title,
                snapshot.original_title,
                normalize_text(snapshot.title),
                normalize_text(snapshot.original_title or ""),
                snapshot.description,
                snapshot.poster_path,
                snapshot.rating,
                snapshot.release_date,
                snapshot.status,
                int(is_released),
                snapshot.poster_path,
                media_id,
            ),
        )
        await replace_media_search_terms(
            connection,
            media_id,
            snapshot.title,
            snapshot.original_title,
        )
        if is_released and not was_released:
            await record_media_release(connection, media_id)
        return changes


def _due_condition(mode: RefreshMode) -> tuple[str, tuple[object, ...]]:
    if mode == "daily":
        placeholders = ", ".join("?" for _ in ACTIVE_STATUSES)
        return (
            f"""
            (
                (content_format = 'series'
                 AND (tmdb_in_production = 1 OR tmdb_status IN ({placeholders})))
                OR
                (is_released = 0 AND EXISTS (
                    SELECT 1 FROM user_media
                    WHERE user_media.media_id = media.id
                      AND user_media.status = 'planned'
                ))
            )
            AND (
                tmdb_release_checked_at IS NULL
                OR tmdb_release_checked_at < datetime('now', '-23 hours')
            )
            """,
            ACTIVE_STATUSES,
        )
    if mode == "weekly":
        return (
            """
            content_format = 'series'
            AND (
                tmdb_metadata_checked_at IS NULL
                OR tmdb_metadata_checked_at < datetime('now', '-6 days 23 hours')
            )
            """,
            (),
        )
    raise ValueError(f"Unknown refresh mode: {mode}")


async def _collect_changes(
    connection: aiosqlite.Connection,
    media_id: int,
    snapshot: SeriesReleaseSnapshot,
) -> list[MediaChange]:
    async with connection.execute(
        "SELECT * FROM media WHERE id = ?", (media_id,)
    ) as cursor:
        media = await cursor.fetchone()
    if media is None:
        raise ValueError(f"Media {media_id} does not exist")

    next_episode = snapshot.next_episode
    last_episode = snapshot.last_episode_to_air
    fresh = {
        "title": snapshot.title or media["title"],
        "original_title": snapshot.original_title,
        "description": snapshot.description,
        "rating": snapshot.rating,
        "poster_path": snapshot.poster_path,
        "first_air_date": snapshot.first_air_date,
        "tmdb_status": snapshot.status,
        "tmdb_in_production": (
            int(snapshot.in_production) if snapshot.in_production is not None else None
        ),
        "number_of_seasons": max(
            int(media["number_of_seasons"] or 0), snapshot.number_of_seasons
        ),
        "number_of_episodes": max(
            int(media["number_of_episodes"] or 0), snapshot.number_of_episodes
        ),
        "available_episode_count": max(
            int(media["available_episode_count"] or 0),
            snapshot.available_episode_count,
        ),
        "next_episode_air_date": next_episode.air_date if next_episode else None,
        "next_episode_season_number": (
            next_episode.season_number if next_episode else None
        ),
        "next_episode_number": next_episode.episode_number if next_episode else None,
        "last_episode_air_date": last_episode.air_date if last_episode else None,
        "last_episode_season_number": (
            last_episode.season_number if last_episode else None
        ),
        "last_episode_number": last_episode.episode_number if last_episode else None,
        "is_released": int(
            bool(media["is_released"]) or snapshot.available_episode_count > 0
        ),
    }
    changes = [
        MediaChange(field, media[field], value)
        for field, value in fresh.items()
        if media[field] != value
    ]

    async with connection.execute(
        """
        SELECT season_number, name, announced_episode_count,
               available_episode_count
        FROM media_seasons WHERE media_id = ? ORDER BY season_number
        """,
        (media_id,),
    ) as cursor:
        old_seasons = {
            int(row["season_number"]): (
                row["name"],
                int(row["announced_episode_count"]),
                int(row["available_episode_count"]),
            )
            for row in await cursor.fetchall()
        }
    for season in snapshot.regular_seasons:
        old = old_seasons.get(season.season_number)
        fresh_season = (
            season.name,
            max(season.announced_episode_count, old[1] if old else 0),
            max(season.aired_episode_count, old[2] if old else 0),
        )
        if old != fresh_season:
            changes.append(
                MediaChange(
                    f"season_{season.season_number}",
                    old,
                    fresh_season,
                )
            )
    return changes


async def _write_metadata(
    connection: aiosqlite.Connection,
    media_id: int,
    snapshot: SeriesReleaseSnapshot,
    mode: RefreshMode,
) -> None:
    async with connection.execute(
        "SELECT title, is_released FROM media WHERE id = ?",
        (media_id,),
    ) as cursor:
        current = await cursor.fetchone()
    if current is None:
        raise ValueError(f"Media {media_id} does not exist")
    resolved_title = snapshot.title or str(current["title"])
    async with connection.execute(
        """
        SELECT COALESCE(MAX(season_number), 0),
               COALESCE(SUM(announced_episode_count), 0),
               COALESCE(SUM(available_episode_count), 0)
        FROM media_seasons WHERE media_id = ?
        """,
        (media_id,),
    ) as cursor:
        season_count, announced_count, available_count = await cursor.fetchone()
    async with connection.execute(
        "SELECT COALESCE(MAX(episodes_watched), 0) FROM user_media WHERE media_id = ?",
        (media_id,),
    ) as cursor:
        max_progress = int((await cursor.fetchone())[0])

    available = max(
        snapshot.available_episode_count, int(available_count), max_progress
    )
    seasons = max(snapshot.number_of_seasons, int(season_count))
    episodes = max(snapshot.number_of_episodes, int(announced_count), available)
    next_episode = snapshot.next_episode
    last_episode = snapshot.last_episode_to_air
    metadata_checked_sql = (
        ", tmdb_metadata_checked_at = CURRENT_TIMESTAMP" if mode == "weekly" else ""
    )
    await connection.execute(
        f"""
        UPDATE media
        SET title = ?, original_title = ?,
            normalized_title = ?, normalized_original_title = ?,
            description = ?, rating = ?, poster_path = ?, first_air_date = ?,
            telegram_poster_file_id = CASE
                WHEN poster_path IS NOT ? THEN NULL
                ELSE telegram_poster_file_id
            END,
            tmdb_status = ?, tmdb_in_production = ?,
            is_released = ?,
            number_of_seasons = ?, number_of_episodes = ?,
            available_episode_count = ?,
            next_episode_air_date = ?, next_episode_season_number = ?,
            next_episode_number = ?, last_episode_air_date = ?,
            last_episode_season_number = ?, last_episode_number = ?,
            tmdb_release_checked_at = CURRENT_TIMESTAMP,
            tmdb_refresh_error = NULL, last_updated = CURRENT_TIMESTAMP
            {metadata_checked_sql}
        WHERE id = ?
        """,
        (
            resolved_title,
            snapshot.original_title,
            normalize_text(resolved_title),
            normalize_text(snapshot.original_title or ""),
            snapshot.description,
            snapshot.rating,
            snapshot.poster_path,
            snapshot.first_air_date,
            snapshot.poster_path,
            snapshot.status,
            snapshot.in_production,
            int(bool(current["is_released"]) or snapshot.available_episode_count > 0),
            seasons,
            episodes,
            available,
            next_episode.air_date if next_episode else None,
            next_episode.season_number if next_episode else None,
            next_episode.episode_number if next_episode else None,
            last_episode.air_date if last_episode else None,
            last_episode.season_number if last_episode else None,
            last_episode.episode_number if last_episode else None,
            media_id,
        ),
    )
    await replace_media_search_terms(
        connection,
        media_id,
        resolved_title,
        snapshot.original_title,
    )


async def _touch_checked_at(
    connection: aiosqlite.Connection,
    media_id: int,
    mode: RefreshMode,
    *,
    error: str | None,
) -> None:
    metadata_checked_sql = (
        ", tmdb_metadata_checked_at = CURRENT_TIMESTAMP" if mode == "weekly" else ""
    )
    await connection.execute(
        f"""
        UPDATE media
        SET tmdb_release_checked_at = CURRENT_TIMESTAMP,
            tmdb_refresh_error = ?
            {metadata_checked_sql}
        WHERE id = ?
        """,
        (error, media_id),
    )


__all__ = (
    "MediaChange",
    "MediaRefreshCandidate",
    "RefreshMode",
    "get_media_candidate",
    "get_tmdb_candidates",
    "has_due_media",
    "mark_media_refresh_error",
    "preview_media_refresh",
    "save_media_refresh",
    "save_movie_release_refresh",
    "select_due_media_batch",
)
