"""Queries for the shared media catalogue."""

from __future__ import annotations

import aiosqlite

from src.database.connection import connection_scope, existing_or_connection_scope
from src.database.media_search import find_media_by_title
from src.database.series_release import (
    replace_media_seasons as _replace_media_seasons,
)
from src.database.series_release import (
    update_media_series_release_info as _update_media_series_release_info,
)
from src.models import SeriesEpisode, SeriesReleaseSnapshot, SeriesSeason
from src.tmdb_matching import normalize_text


async def get_media_by_tmdb(
    tmdb_id: int,
    content_format: str,
    content_type: str,
    *,
    database_url: str | None = None,
) -> aiosqlite.Row | None:
    async with connection_scope(database_url) as connection:
        async with connection.execute(
            """
            SELECT *
            FROM media
            WHERE tmdb_id = ? AND content_format = ? AND content_type = ?
            """,
            (tmdb_id, content_format, content_type),
        ) as cursor:
            return await cursor.fetchone()


async def upsert_media(
    *,
    tmdb_id: int | None,
    content_format: str,
    content_type: str,
    title: str,
    original_title: str | None = None,
    description: str | None = None,
    poster_path: str | None = None,
    telegram_poster_file_id: str | None = None,
    rating: float | None = None,
    release_date: str | None = None,
    first_air_date: str | None = None,
    number_of_seasons: int | None = None,
    number_of_episodes: int | None = None,
    available_episode_count: int | None = None,
    status: str | None = None,
    database_url: str | None = None,
    connection: aiosqlite.Connection | None = None,
) -> int:
    """Insert media or refresh an existing TMDB-backed record."""
    resolved_available_episode_count = (
        available_episode_count
        if available_episode_count is not None
        else number_of_episodes
    )
    values = (
        tmdb_id,
        content_format,
        content_type,
        title,
        original_title,
        normalize_text(title),
        normalize_text(original_title or ""),
        description,
        poster_path,
        telegram_poster_file_id,
        rating,
        release_date,
        first_air_date,
        number_of_seasons,
        number_of_episodes,
        resolved_available_episode_count,
        status,
    )

    async with existing_or_connection_scope(
        connection,
        database_url=database_url,
    ) as active_connection:
        if tmdb_id is None:
            async with active_connection.execute(
                """
                INSERT INTO media (
                    tmdb_id, content_format, content_type, title,
                    original_title, normalized_title,
                    normalized_original_title, description,
                    poster_path, telegram_poster_file_id,
                    rating, release_date, first_air_date,
                    number_of_seasons, number_of_episodes,
                    available_episode_count, status
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                values,
            ) as cursor:
                return _last_row_id(cursor)

        await active_connection.execute(
            """
            INSERT INTO media (
                tmdb_id, content_format, content_type, title,
                original_title, normalized_title,
                normalized_original_title, description,
                poster_path, telegram_poster_file_id,
                rating, release_date, first_air_date,
                number_of_seasons, number_of_episodes,
                available_episode_count, status
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(tmdb_id, content_format, content_type) DO UPDATE SET
                title = excluded.title,
                normalized_title = excluded.normalized_title,
                original_title = COALESCE(
                    excluded.original_title, media.original_title
                ),
                normalized_original_title = CASE
                    WHEN excluded.original_title IS NULL
                        THEN media.normalized_original_title
                    ELSE excluded.normalized_original_title
                END,
                description = COALESCE(excluded.description, media.description),
                poster_path = COALESCE(excluded.poster_path, media.poster_path),
                telegram_poster_file_id = COALESCE(
                    excluded.telegram_poster_file_id,
                    media.telegram_poster_file_id
                ),
                rating = COALESCE(excluded.rating, media.rating),
                release_date = COALESCE(excluded.release_date, media.release_date),
                first_air_date = COALESCE(
                    excluded.first_air_date, media.first_air_date
                ),
                number_of_seasons = COALESCE(
                    excluded.number_of_seasons, media.number_of_seasons
                ),
                number_of_episodes = COALESCE(
                    excluded.number_of_episodes, media.number_of_episodes
                ),
                available_episode_count = COALESCE(
                    excluded.available_episode_count,
                    media.available_episode_count
                ),
                status = COALESCE(excluded.status, media.status),
                last_updated = CURRENT_TIMESTAMP
            """,
            values,
        )
        async with active_connection.execute(
            """
            SELECT id FROM media
            WHERE tmdb_id = ? AND content_format = ? AND content_type = ?
            """,
            (tmdb_id, content_format, content_type),
        ) as cursor:
            row = await cursor.fetchone()
        if row is None:
            raise RuntimeError("Media upsert did not produce a row")
        return int(row["id"])


async def update_media_poster(
    media_id: int,
    poster_path: str,
    *,
    database_url: str | None = None,
) -> None:
    async with connection_scope(database_url) as connection:
        await connection.execute(
            """
            UPDATE media
            SET poster_path = ?, last_updated = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (poster_path, media_id),
        )


async def update_media_telegram_poster_file_id(
    media_id: int,
    file_id: str,
    *,
    database_url: str | None = None,
) -> None:
    """Cache a reusable Telegram photo id for a catalogue item."""
    if not file_id:
        raise ValueError("Telegram poster file id cannot be empty")
    async with connection_scope(database_url) as connection:
        await connection.execute(
            """
            UPDATE media
            SET telegram_poster_file_id = ?, last_updated = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (file_id, media_id),
        )


async def update_media_metadata(
    media_id: int,
    *,
    poster_path: str | None = None,
    rating: float | None = None,
    database_url: str | None = None,
) -> None:
    """Fill refreshable TMDB metadata without clearing existing values."""
    async with connection_scope(database_url) as connection:
        await connection.execute(
            """
            UPDATE media
            SET poster_path = COALESCE(?, poster_path),
                rating = COALESCE(?, rating),
                last_updated = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (poster_path, rating, media_id),
        )


def _last_row_id(cursor: aiosqlite.Cursor) -> int:
    if cursor.lastrowid is None:
        raise RuntimeError("Insert did not produce a row id")
    return int(cursor.lastrowid)


async def replace_media_seasons(
    media_id: int,
    seasons: list[dict],
    *,
    database_url: str | None = None,
) -> None:
    """Compatibility wrapper for the former season-list API."""
    snapshot = SeriesReleaseSnapshot(
        number_of_seasons=len(seasons),
        number_of_episodes=sum(
            int(season.get("announced_episode_count", season["episode_count"]))
            for season in seasons
        ),
        seasons=tuple(SeriesSeason.from_mapping(season) for season in seasons),
    )
    await _replace_media_seasons(media_id, snapshot, database_url=database_url)


async def update_media_series_release_info(
    media_id: int,
    *,
    user_id: int,
    status: str | None,
    in_production: bool | None,
    number_of_seasons: int,
    number_of_episodes: int,
    available_episode_count: int,
    seasons: list[dict],
    poster_path: str | None,
    rating: float | None,
    next_episode_air_date: str | None,
    next_episode_season_number: int | None,
    next_episode_number: int | None,
    database_url: str | None = None,
) -> None:
    """Compatibility wrapper for the former expanded release-info API."""
    parsed_seasons = tuple(SeriesSeason.from_mapping(season) for season in seasons)
    if sum(season.aired_episode_count for season in parsed_seasons) != (
        available_episode_count
    ):
        raise ValueError("Season availability does not match the supplied total")
    next_episode = (
        SeriesEpisode(
            season_number=next_episode_season_number,
            episode_number=next_episode_number,
            air_date=next_episode_air_date,
        )
        if next_episode_season_number is not None and next_episode_number is not None
        else None
    )
    snapshot = SeriesReleaseSnapshot(
        number_of_seasons=number_of_seasons,
        number_of_episodes=number_of_episodes,
        seasons=parsed_seasons,
        status=status,
        in_production=in_production,
        next_episode_to_air=next_episode,
        poster_path=poster_path,
        rating=rating,
    )
    await _update_media_series_release_info(
        media_id,
        user_id=user_id,
        snapshot=snapshot,
        database_url=database_url,
    )


__all__ = (
    "find_media_by_title",
    "get_media_by_tmdb",
    "replace_media_seasons",
    "upsert_media",
    "update_media_metadata",
    "update_media_poster",
    "update_media_telegram_poster_file_id",
    "update_media_series_release_info",
)
