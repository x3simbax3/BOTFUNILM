"""Persistence for users who started the bot."""

from __future__ import annotations

from src.database.connection import connection_scope


async def register_bot_user(
    user_id: int,
    *,
    database_url: str | None = None,
) -> bool:
    async with connection_scope(database_url) as connection:
        await connection.execute(
            """
            INSERT INTO bot_users (user_id, last_activity_at)
            VALUES (?, CURRENT_TIMESTAMP)
            ON CONFLICT(user_id) DO UPDATE SET
                is_active = 1,
                last_started_at = CURRENT_TIMESTAMP,
                last_activity_at = CURRENT_TIMESTAMP
            """,
            (user_id,),
        )
        async with connection.execute(
            "SELECT news_enabled FROM bot_users WHERE user_id = ?",
            (user_id,),
        ) as cursor:
            row = await cursor.fetchone()
    return bool(row["news_enabled"])


async def touch_bot_user(
    user_id: int,
    *,
    database_url: str | None = None,
) -> None:
    """Register user activity without changing the last /start timestamp."""
    async with connection_scope(database_url) as connection:
        await connection.execute(
            """
            INSERT INTO bot_users (user_id, last_activity_at)
            VALUES (?, CURRENT_TIMESTAMP)
            ON CONFLICT(user_id) DO UPDATE SET
                is_active = 1,
                last_activity_at = CURRENT_TIMESTAMP
            WHERE bot_users.is_active = 0
               OR bot_users.last_activity_at < datetime('now', '-1 minute')
            """,
            (user_id,),
        )


async def get_news_recipients(
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
            WHERE is_active = 1 AND news_enabled = 1 AND user_id > ?
            ORDER BY user_id
            LIMIT ?
            """,
            (after_user_id, limit),
        ) as cursor:
            return [int(row["user_id"]) for row in await cursor.fetchall()]


async def get_news_enabled(
    user_id: int,
    *,
    database_url: str | None = None,
) -> bool:
    async with connection_scope(database_url) as connection:
        async with connection.execute(
            "SELECT news_enabled FROM bot_users WHERE user_id = ?",
            (user_id,),
        ) as cursor:
            row = await cursor.fetchone()
    return True if row is None else bool(row["news_enabled"])


async def toggle_news_enabled(
    user_id: int,
    *,
    database_url: str | None = None,
) -> bool:
    async with connection_scope(database_url) as connection:
        async with connection.execute(
            """
            INSERT INTO bot_users (user_id, news_enabled)
            VALUES (?, 0)
            ON CONFLICT(user_id) DO UPDATE SET
                news_enabled = NOT news_enabled
            RETURNING news_enabled
            """,
            (user_id,),
        ) as cursor:
            row = await cursor.fetchone()
    return bool(row["news_enabled"])


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
    "get_news_enabled",
    "get_news_recipients",
    "mark_bot_user_inactive",
    "register_bot_user",
    "touch_bot_user",
    "toggle_news_enabled",
)
