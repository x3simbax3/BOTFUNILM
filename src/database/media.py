"""Queries for the shared media catalogue."""

from __future__ import annotations

import aiosqlite

from src.database.connection import connection_scope
from src.tmdb import MIN_RELEVANCE, title_relevance_score


async def find_media_by_title(
    title: str,
    content_format: str,
    content_type: str,
    *,
    database_url: str | None = None,
) -> aiosqlite.Row | None:
    """Return the closest local title, using the same relevance logic as TMDB."""
    async with connection_scope(database_url) as connection:
        async with connection.execute(
            """
            SELECT id, title, original_title
            FROM media
            WHERE content_format = ? AND content_type = ?
            """,
            (content_format, content_type),
        ) as cursor:
            rows = await cursor.fetchall()

        best = None
        best_score = 0.0
        for row in rows:
            score = title_relevance_score(dict(row), title)
            if score > best_score:
                best = row
                best_score = score

        if best is None or best_score < MIN_RELEVANCE:
            return None

        async with connection.execute(
            "SELECT * FROM media WHERE id = ?",
            (best["id"],),
        ) as cursor:
            return await cursor.fetchone()


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
    rating: float | None = None,
    release_date: str | None = None,
    first_air_date: str | None = None,
    number_of_seasons: int | None = None,
    number_of_episodes: int | None = None,
    available_episode_count: int | None = None,
    status: str | None = None,
    database_url: str | None = None,
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
        description,
        poster_path,
        rating,
        release_date,
        first_air_date,
        number_of_seasons,
        number_of_episodes,
        resolved_available_episode_count,
        status,
    )

    async with connection_scope(database_url) as connection:
        if tmdb_id is None:
            async with connection.execute(
                """
                INSERT INTO media (
                    tmdb_id, content_format, content_type, title,
                    original_title, description,
                    poster_path, rating, release_date, first_air_date,
                    number_of_seasons, number_of_episodes,
                    available_episode_count, status
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                values,
            ) as cursor:
                return _last_row_id(cursor)

        await connection.execute(
            """
            INSERT INTO media (
                tmdb_id, content_format, content_type, title,
                original_title, description,
                poster_path, rating, release_date, first_air_date,
                number_of_seasons, number_of_episodes,
                available_episode_count, status
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(tmdb_id, content_format, content_type) DO UPDATE SET
                title = excluded.title,
                original_title = excluded.original_title,
                description = excluded.description,
                poster_path = excluded.poster_path,
                rating = excluded.rating,
                release_date = excluded.release_date,
                first_air_date = excluded.first_air_date,
                number_of_seasons = excluded.number_of_seasons,
                number_of_episodes = excluded.number_of_episodes,
                available_episode_count = excluded.available_episode_count,
                status = excluded.status,
                last_updated = CURRENT_TIMESTAMP
            """,
            values,
        )
        async with connection.execute(
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


async def update_media_series_release_info(
    media_id: int,
    *,
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
    """Overwrite cached TMDB release information after a card refresh."""
    async with connection_scope(database_url) as connection:
        await connection.execute(
            """
            UPDATE media
            SET tmdb_status = ?, tmdb_in_production = ?,
                number_of_seasons = ?, number_of_episodes = ?,
                available_episode_count = MAX(?, COALESCE((
                    SELECT MAX(episodes_watched)
                    FROM user_media
                    WHERE media_id = ?
                ), 0)),
                poster_path = COALESCE(?, poster_path),
                rating = COALESCE(?, rating),
                next_episode_air_date = ?, next_episode_season_number = ?,
                next_episode_number = ?,
                tmdb_release_checked_at = CURRENT_TIMESTAMP,
                last_updated = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (
                status,
                in_production,
                number_of_seasons,
                number_of_episodes,
                available_episode_count,
                media_id,
                poster_path,
                rating,
                next_episode_air_date,
                next_episode_season_number,
                next_episode_number,
                media_id,
            ),
        )
        await _replace_media_seasons(connection, media_id, seasons)
        await connection.execute(
            """
            UPDATE user_season_progress
            SET episodes_watched = (
                    SELECT ms.available_episode_count
                    FROM media_seasons AS ms
                    WHERE ms.media_id = user_season_progress.media_id
                      AND ms.season_number = user_season_progress.season_number
                ),
                last_watched_at = CURRENT_TIMESTAMP
            WHERE media_id = ?
              AND EXISTS (
                  SELECT 1 FROM media_seasons AS ms
                  WHERE ms.media_id = user_season_progress.media_id
                    AND ms.season_number = user_season_progress.season_number
                    AND user_season_progress.episodes_watched
                        > ms.available_episode_count
              )
            """,
            (media_id,),
        )
        active = bool(in_production) or status in {
            "Returning Series",
            "Planned",
            "In Production",
        }
        await connection.execute(
            """
            UPDATE user_media
            SET episodes_watched = COALESCE((
                    SELECT SUM(usp.episodes_watched)
                    FROM user_season_progress AS usp
                    WHERE usp.user_id = user_media.user_id
                      AND usp.media_id = user_media.media_id
                ), 0),
                status = CASE
                    WHEN COALESCE((
                        SELECT SUM(usp.episodes_watched)
                        FROM user_season_progress AS usp
                        WHERE usp.user_id = user_media.user_id
                          AND usp.media_id = user_media.media_id
                    ), 0) = 0 THEN 'planned'
                    WHEN ? THEN 'watching'
                    WHEN COALESCE((
                        SELECT SUM(usp.episodes_watched)
                        FROM user_season_progress AS usp
                        WHERE usp.user_id = user_media.user_id
                          AND usp.media_id = user_media.media_id
                    ), 0) = ? THEN 'completed'
                    ELSE 'watching'
                END,
                last_watched_at = CURRENT_TIMESTAMP
            WHERE media_id = ?
            """,
            (active, available_episode_count, media_id),
        )
        await connection.execute(
            """
            UPDATE media
            SET available_episode_count = ?
            WHERE id = ?
            """,
            (available_episode_count, media_id),
        )


async def replace_media_seasons(
    media_id: int,
    seasons: list[dict],
    *,
    database_url: str | None = None,
) -> None:
    """Replace cached season availability from one TMDB response."""
    async with connection_scope(database_url) as connection:
        await _replace_media_seasons(connection, media_id, seasons)


async def _replace_media_seasons(
    connection: aiosqlite.Connection,
    media_id: int,
    seasons: list[dict],
) -> None:
    await connection.execute(
        "DELETE FROM media_seasons WHERE media_id = ?", (media_id,)
    )
    if seasons:
        await connection.executemany(
            """
            INSERT INTO media_seasons (
                media_id, season_number, name,
                announced_episode_count, available_episode_count
            ) VALUES (?, ?, ?, ?, ?)
            """,
            [
                (
                    media_id,
                    season["season_number"],
                    season["name"],
                    season.get("announced_episode_count", season["episode_count"]),
                    season["episode_count"],
                )
                for season in seasons
            ],
        )


def _last_row_id(cursor: aiosqlite.Cursor) -> int:
    if cursor.lastrowid is None:
        raise RuntimeError("Insert did not produce a row id")
    return int(cursor.lastrowid)


__all__ = (
    "find_media_by_title",
    "get_media_by_tmdb",
    "replace_media_seasons",
    "upsert_media",
    "update_media_metadata",
    "update_media_poster",
    "update_media_series_release_info",
)
