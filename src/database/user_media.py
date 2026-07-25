"""Queries for media saved by a user."""

from __future__ import annotations

import aiosqlite

from src.database.connection import connection_scope


async def save_user_media(
    *,
    user_id: int,
    media_id: int,
    status: str,
    user_rating: int | None = None,
    episodes_watched: int | None = None,
    database_url: str | None = None,
) -> None:
    async with connection_scope(database_url) as connection:
        await connection.execute(
            """
            INSERT INTO user_media (
                user_id, media_id, status, user_rating, episodes_watched, added_at
            ) VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(user_id, media_id) DO UPDATE SET
                status = excluded.status,
                user_rating = excluded.user_rating,
                episodes_watched = excluded.episodes_watched,
                last_watched_at = CURRENT_TIMESTAMP
            """,
            (user_id, media_id, status, user_rating, episodes_watched),
        )


async def get_user_media(
    user_id: int,
    media_id: int,
    *,
    database_url: str | None = None,
) -> aiosqlite.Row | None:
    async with connection_scope(database_url) as connection:
        async with connection.execute(
            """
            SELECT *
            FROM user_media
            WHERE user_id = ? AND media_id = ?
            """,
            (user_id, media_id),
        ) as cursor:
            return await cursor.fetchone()


__all__ = ("get_user_media", "save_user_media")
