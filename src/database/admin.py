"""Read-only aggregate queries for the Telegram admin overview."""

from __future__ import annotations

from dataclasses import dataclass

from src.database.connection import connection_scope


@dataclass(frozen=True)
class AdminOverview:
    total_users: int
    active_users: int
    inactive_users: int
    new_24h: int
    new_7d: int
    new_30d: int
    active_24h: int
    active_7d: int
    active_30d: int
    activated_users: int
    library_items: int
    rated_items: int
    tracked_series: int
    news_users: int
    generated_at: str

    @property
    def activation_percent(self) -> float:
        if not self.total_users:
            return 0.0
        return self.activated_users * 100 / self.total_users

    @property
    def average_library_items(self) -> float:
        if not self.total_users:
            return 0.0
        return self.library_items / self.total_users


async def get_admin_overview(
    *,
    database_url: str | None = None,
) -> AdminOverview:
    async with connection_scope(database_url) as connection:
        async with connection.execute(
            """
            SELECT
                COUNT(*) AS total_users,
                COUNT(*) FILTER (WHERE is_active = 1) AS active_users,
                COUNT(*) FILTER (WHERE is_active = 0) AS inactive_users,
                COUNT(*) FILTER (
                    WHERE started_at >= datetime('now', '-1 day')
                ) AS new_24h,
                COUNT(*) FILTER (
                    WHERE started_at >= datetime('now', '-7 days')
                ) AS new_7d,
                COUNT(*) FILTER (
                    WHERE started_at >= datetime('now', '-30 days')
                ) AS new_30d,
                COUNT(*) FILTER (
                    WHERE last_activity_at >= datetime('now', '-1 day')
                ) AS active_24h,
                COUNT(*) FILTER (
                    WHERE last_activity_at >= datetime('now', '-7 days')
                ) AS active_7d,
                COUNT(*) FILTER (
                    WHERE last_activity_at >= datetime('now', '-30 days')
                ) AS active_30d,
                COUNT(*) FILTER (
                    WHERE EXISTS (
                        SELECT 1 FROM user_media
                        WHERE user_media.user_id = bot_users.user_id
                    )
                ) AS activated_users,
                (SELECT COUNT(*) FROM user_media) AS library_items,
                (SELECT COUNT(*) FROM user_media WHERE user_rating IS NOT NULL)
                    AS rated_items,
                (SELECT COUNT(*) FROM user_media WHERE is_tracking = 1)
                    AS tracked_series,
                COUNT(*) FILTER (
                    WHERE is_active = 1 AND news_enabled = 1
                ) AS news_users,
                CURRENT_TIMESTAMP AS generated_at
            FROM bot_users
            """
        ) as cursor:
            row = await cursor.fetchone()

    return AdminOverview(**dict(row))


__all__ = ("AdminOverview", "get_admin_overview")
