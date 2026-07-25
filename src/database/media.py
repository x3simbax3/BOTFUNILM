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
    status: str | None = None,
    database_url: str | None = None,
) -> int:
    """Insert media or refresh an existing TMDB-backed record."""
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
                    number_of_seasons, number_of_episodes, status
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
                number_of_seasons, number_of_episodes, status
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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


def _last_row_id(cursor: aiosqlite.Cursor) -> int:
    if cursor.lastrowid is None:
        raise RuntimeError("Insert did not produce a row id")
    return int(cursor.lastrowid)


__all__ = (
    "find_media_by_title",
    "get_media_by_tmdb",
    "upsert_media",
    "update_media_poster",
)
