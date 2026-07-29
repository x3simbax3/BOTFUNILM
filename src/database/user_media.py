"""Queries for media saved by a user."""

from __future__ import annotations

from collections.abc import Mapping

import aiosqlite

from src.database.connection import connection_scope, existing_or_connection_scope
from src.database.ratings import replace_user_rating_details


async def save_user_media(
    *,
    user_id: int,
    media_id: int,
    status: str,
    user_rating: int | None = None,
    episodes_watched: int | None = None,
    rating_details: Mapping[str, int] | None = None,
    database_url: str | None = None,
    connection: aiosqlite.Connection | None = None,
) -> None:
    async with existing_or_connection_scope(
        connection,
        database_url=database_url,
    ) as active_connection:
        await active_connection.execute(
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
        if rating_details is not None:
            await replace_user_rating_details(
                active_connection,
                user_id,
                media_id,
                rating_details,
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


async def set_user_media_status(
    user_id: int,
    media_id: int,
    status: str,
    *,
    database_url: str | None = None,
) -> bool:
    if status not in {"planned", "watching", "completed", "on_hold", "dropped"}:
        raise ValueError("Unknown user media status")
    async with connection_scope(database_url) as connection:
        cursor = await connection.execute(
            """
            UPDATE user_media
            SET status = ?, last_watched_at = CURRENT_TIMESTAMP
            WHERE user_id = ? AND media_id = ?
            """,
            (status, user_id, media_id),
        )
        return cursor.rowcount > 0


async def update_user_media_rating(
    user_id: int,
    media_id: int,
    user_rating: int,
    *,
    rating_details: Mapping[str, int] | None = None,
    database_url: str | None = None,
) -> bool:
    if type(user_rating) is not int or not 1 <= user_rating <= 10:
        raise ValueError("Rating must be an integer from 1 to 10")
    async with connection_scope(database_url) as connection:
        cursor = await connection.execute(
            """
            UPDATE user_media
            SET user_rating = ?, last_watched_at = CURRENT_TIMESTAMP
            WHERE user_id = ? AND media_id = ?
            """,
            (user_rating, user_id, media_id),
        )
        updated = cursor.rowcount > 0
        if updated and rating_details is not None:
            await replace_user_rating_details(
                connection,
                user_id,
                media_id,
                rating_details,
            )
        return updated


async def delete_user_media(
    user_id: int,
    media_id: int,
    *,
    database_url: str | None = None,
) -> bool:
    async with connection_scope(database_url) as connection:
        cursor = await connection.execute(
            "DELETE FROM user_media WHERE user_id = ? AND media_id = ?",
            (user_id, media_id),
        )
        return cursor.rowcount > 0


__all__ = (
    "delete_user_media",
    "get_user_media",
    "save_user_media",
    "set_user_media_status",
    "update_user_media_rating",
)
