"""Queries for the shared media catalogue."""

from __future__ import annotations

import aiosqlite

from src.database.connection import connection_scope


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


def _last_row_id(cursor: aiosqlite.Cursor) -> int:
    if cursor.lastrowid is None:
        raise RuntimeError("Insert did not produce a row id")
    return int(cursor.lastrowid)


__all__ = (
    "get_media_by_tmdb",
    "upsert_media",
    "update_media_metadata",
    "update_media_poster",
)
