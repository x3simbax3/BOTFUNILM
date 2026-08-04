"""Persistence for series subscriptions and release notifications."""

from __future__ import annotations

from dataclasses import dataclass

import aiosqlite

from src.database.connection import connection_scope

TRACKED_SERIES_LIMIT = 50


class SeriesSubscriptionError(ValueError):
    """Base error for invalid subscription changes."""


class SeriesSubscriptionNotFoundError(SeriesSubscriptionError):
    pass


class SeriesSubscriptionUnavailableError(SeriesSubscriptionError):
    pass


class SeriesSubscriptionLimitError(SeriesSubscriptionError):
    pass


@dataclass(frozen=True)
class NotificationBatch:
    batch_id: int
    user_id: int


@dataclass(frozen=True)
class NotificationItem:
    media_id: int
    title: str
    previous_episode_count: int
    current_episode_count: int
    season_number: int | None
    episode_number: int | None

    @property
    def released_count(self) -> int:
        return self.current_episode_count - self.previous_episode_count


async def set_series_subscription(
    user_id: int,
    media_id: int,
    enabled: bool,
    *,
    database_url: str | None = None,
) -> bool:
    """Enable or disable one active series subscription for a library item."""
    async with connection_scope(database_url) as connection:
        async with connection.execute(
            """
            SELECT um.is_tracking, m.content_format, m.tmdb_status,
                   m.tmdb_in_production
            FROM user_media AS um
            JOIN media AS m ON m.id = um.media_id
            WHERE um.user_id = ? AND um.media_id = ?
            """,
            (user_id, media_id),
        ) as cursor:
            item = await cursor.fetchone()
        if item is None:
            raise SeriesSubscriptionNotFoundError

        current = bool(item["is_tracking"])
        if not enabled:
            if current:
                await connection.execute(
                    """
                    UPDATE user_media SET is_tracking = 0
                    WHERE user_id = ? AND media_id = ?
                    """,
                    (user_id, media_id),
                )
            return False

        active = bool(item["tmdb_in_production"]) or item["tmdb_status"] in {
            "Returning Series",
            "Planned",
            "In Production",
        }
        if item["content_format"] != "series" or not active:
            raise SeriesSubscriptionUnavailableError
        if current:
            return True

        cursor = await connection.execute(
            """
            UPDATE user_media SET is_tracking = 1
            WHERE user_id = ? AND media_id = ? AND is_tracking = 0
              AND (
                  SELECT COUNT(*) FROM user_media
                  WHERE user_id = ? AND is_tracking = 1
              ) < ?
            """,
            (user_id, media_id, user_id, TRACKED_SERIES_LIMIT),
        )
        if cursor.rowcount == 0:
            raise SeriesSubscriptionLimitError
        return True


async def list_tracked_series(
    user_id: int,
    *,
    limit: int = 11,
    offset: int = 0,
    database_url: str | None = None,
) -> list[aiosqlite.Row]:
    if limit <= 0 or offset < 0:
        raise ValueError("Invalid tracked series page")
    async with connection_scope(database_url) as connection:
        async with connection.execute(
            """
            SELECT m.*, um.status AS user_status, um.user_rating,
                   um.episodes_watched, um.last_watched_at, um.is_tracking,
                   um.badge
            FROM user_media AS um
            JOIN media AS m ON m.id = um.media_id
            WHERE um.user_id = ? AND (
                (
                    um.is_tracking = 1
                    AND COALESCE(um.episodes_watched, 0)
                        < COALESCE(m.available_episode_count, 0)
                )
                OR (
                    m.is_released = 0
                    AND um.status = 'planned'
                )
            )
            ORDER BY m.title COLLATE NOCASE, m.id
            LIMIT ? OFFSET ?
            """,
            (user_id, limit, offset),
        ) as cursor:
            return await cursor.fetchall()


async def record_series_release(
    connection: aiosqlite.Connection,
    media_id: int,
    previous_episode_count: int,
    current_episode_count: int,
    *,
    season_number: int | None,
    episode_number: int | None,
) -> None:
    """Fan out one catalogue release to subscribers without another TMDB call."""
    if current_episode_count > previous_episode_count:
        await connection.execute(
            """
            INSERT OR IGNORE INTO user_series_notifications (
                user_id, media_id, previous_episode_count,
                current_episode_count, season_number, episode_number
            )
            SELECT user_id, media_id, ?, ?, ?, ?
            FROM user_media
            WHERE media_id = ? AND is_tracking = 1
            """,
            (
                previous_episode_count,
                current_episode_count,
                season_number,
                episode_number,
                media_id,
            ),
        )
        await connection.execute(
            """
            UPDATE user_media
            SET status = 'watching'
            WHERE media_id = ? AND is_tracking = 1 AND status = 'completed'
            """,
            (media_id,),
        )


async def prepare_notification_batches(
    *,
    database_url: str | None = None,
) -> list[NotificationBatch]:
    """Attach unbatched events to one pending batch per user."""
    async with connection_scope(database_url) as connection:
        async with connection.execute(
            """
            SELECT DISTINCT user_id FROM user_series_notifications
            WHERE batch_id IS NULL ORDER BY user_id
            """
        ) as cursor:
            user_ids = [int(row["user_id"]) for row in await cursor.fetchall()]

        for user_id in user_ids:
            async with connection.execute(
                """
                SELECT id FROM series_notification_batches
                WHERE user_id = ? AND sent_at IS NULL
                ORDER BY id LIMIT 1
                """,
                (user_id,),
            ) as cursor:
                pending = await cursor.fetchone()
            if pending is None:
                cursor = await connection.execute(
                    "INSERT INTO series_notification_batches (user_id) VALUES (?)",
                    (user_id,),
                )
                batch_id = int(cursor.lastrowid)
            else:
                batch_id = int(pending["id"])
            await connection.execute(
                """
                UPDATE user_series_notifications SET batch_id = ?
                WHERE user_id = ? AND batch_id IS NULL
                """,
                (batch_id, user_id),
            )

        async with connection.execute(
            """
            SELECT id, user_id FROM series_notification_batches
            WHERE sent_at IS NULL ORDER BY id
            """
        ) as cursor:
            rows = await cursor.fetchall()
    return [
        NotificationBatch(batch_id=int(row["id"]), user_id=int(row["user_id"]))
        for row in rows
    ]


async def get_notification_batch(
    batch_id: int,
    user_id: int,
    *,
    database_url: str | None = None,
) -> list[NotificationItem] | None:
    """Return a user's batch, grouping delayed releases of the same title."""
    async with connection_scope(database_url) as connection:
        async with connection.execute(
            """
            SELECT 1 FROM series_notification_batches
            WHERE id = ? AND user_id = ?
            """,
            (batch_id, user_id),
        ) as cursor:
            if await cursor.fetchone() is None:
                return None
        async with connection.execute(
            """
            SELECT n.*, m.title
            FROM user_series_notifications AS n
            JOIN media AS m ON m.id = n.media_id
            WHERE n.batch_id = ?
            ORDER BY n.id
            """,
            (batch_id,),
        ) as cursor:
            rows = await cursor.fetchall()

    grouped: dict[int, NotificationItem] = {}
    for row in rows:
        media_id = int(row["media_id"])
        previous = grouped.get(media_id)
        grouped[media_id] = NotificationItem(
            media_id=media_id,
            title=str(row["title"]),
            previous_episode_count=(
                previous.previous_episode_count
                if previous is not None
                else int(row["previous_episode_count"])
            ),
            current_episode_count=int(row["current_episode_count"]),
            season_number=(
                int(row["season_number"]) if row["season_number"] is not None else None
            ),
            episode_number=(
                int(row["episode_number"])
                if row["episode_number"] is not None
                else None
            ),
        )
    return list(grouped.values())


async def mark_notification_batch_sent(
    batch_id: int,
    *,
    database_url: str | None = None,
) -> None:
    async with connection_scope(database_url) as connection:
        await connection.execute(
            """
            UPDATE series_notification_batches SET sent_at = CURRENT_TIMESTAMP
            WHERE id = ? AND sent_at IS NULL
            """,
            (batch_id,),
        )


__all__ = (
    "NotificationBatch",
    "NotificationItem",
    "SeriesSubscriptionError",
    "SeriesSubscriptionLimitError",
    "SeriesSubscriptionNotFoundError",
    "SeriesSubscriptionUnavailableError",
    "TRACKED_SERIES_LIMIT",
    "get_notification_batch",
    "list_tracked_series",
    "mark_notification_batch_sent",
    "prepare_notification_batches",
    "record_series_release",
    "set_series_subscription",
)
