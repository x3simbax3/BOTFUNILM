"""Persistence for users who started the bot."""

from __future__ import annotations

from src.database.connection import connection_scope


async def register_bot_user(
    user_id: int,
    *,
    database_url: str | None = None,
) -> None:
    async with connection_scope(database_url) as connection:
        await connection.execute(
            """
            INSERT INTO bot_users (user_id)
            VALUES (?)
            ON CONFLICT(user_id) DO UPDATE SET
                is_active = 1,
                last_started_at = CURRENT_TIMESTAMP
            """,
            (user_id,),
        )


async def get_active_bot_users(
    *,
    after_user_id: int = 0,
    limit: int = 100,
    database_url: str | None = None,
) -> list[int]:
    if limit <= 0:
        raise ValueError("limit must be positive")
    async with connection_scope(database_url) as connection:
        async with connection.execute(
            """
            SELECT user_id
            FROM bot_users
            WHERE is_active = 1 AND user_id > ?
            ORDER BY user_id
            LIMIT ?
            """,
            (after_user_id, limit),
        ) as cursor:
            return [int(row["user_id"]) for row in await cursor.fetchall()]


async def mark_bot_user_inactive(
    user_id: int,
    *,
    database_url: str | None = None,
) -> None:
    async with connection_scope(database_url) as connection:
        await connection.execute(
            "UPDATE bot_users SET is_active = 0 WHERE user_id = ?",
            (user_id,),
        )


__all__ = (
    "get_active_bot_users",
    "mark_bot_user_inactive",
    "register_bot_user",
)
