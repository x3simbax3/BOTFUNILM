"""Persistence for notifications when planned titles become available."""

from __future__ import annotations

from dataclasses import dataclass

import aiosqlite

from src.database.connection import connection_scope


@dataclass(frozen=True)
class MediaReleaseNotification:
    notification_id: int
    media_id: int
    title: str


async def record_media_release(
    connection: aiosqlite.Connection,
    media_id: int,
) -> None:
    await connection.execute(
        """
        INSERT OR IGNORE INTO user_media_release_notifications (user_id, media_id)
        SELECT user_id, media_id
        FROM user_media
        WHERE media_id = ? AND status = 'planned'
        """,
        (media_id,),
    )


async def get_pending_release_users(
    *,
    after_user_id: int = 0,
    limit: int = 100,
    database_url: str | None = None,
) -> list[int]:
    async with connection_scope(database_url) as connection:
        async with connection.execute(
            """
            SELECT DISTINCT user_id
            FROM user_media_release_notifications
            WHERE sent_at IS NULL AND user_id > ?
            ORDER BY user_id
            LIMIT ?
            """,
            (after_user_id, limit),
        ) as cursor:
            return [int(row["user_id"]) for row in await cursor.fetchall()]


async def get_release_notifications(
    user_id: int,
    *,
    limit: int = 10,
    database_url: str | None = None,
) -> list[MediaReleaseNotification]:
    async with connection_scope(database_url) as connection:
        async with connection.execute(
            """
            SELECT n.id, n.media_id, m.title
            FROM user_media_release_notifications AS n
            JOIN media AS m ON m.id = n.media_id
            WHERE n.user_id = ? AND n.sent_at IS NULL
            ORDER BY n.id
            LIMIT ?
            """,
            (user_id, limit),
        ) as cursor:
            rows = await cursor.fetchall()
    return [
        MediaReleaseNotification(
            notification_id=int(row["id"]),
            media_id=int(row["media_id"]),
            title=str(row["title"]),
        )
        for row in rows
    ]


async def mark_release_notifications_sent(
    notification_ids: list[int],
    *,
    database_url: str | None = None,
) -> None:
    if not notification_ids:
        return
    placeholders = ", ".join("?" for _ in notification_ids)
    async with connection_scope(database_url) as connection:
        await connection.execute(
            f"""
            UPDATE user_media_release_notifications
            SET sent_at = CURRENT_TIMESTAMP
            WHERE sent_at IS NULL AND id IN ({placeholders})
            """,
            notification_ids,
        )


__all__ = (
    "MediaReleaseNotification",
    "get_pending_release_users",
    "get_release_notifications",
    "mark_release_notifications_sent",
    "record_media_release",
)
