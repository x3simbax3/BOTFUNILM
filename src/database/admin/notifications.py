"""Admin queries for notification delivery."""

from __future__ import annotations

from src.database.admin.models import AdminNotifications
from src.database.connection import connection_scope


async def get_admin_notifications(
    *, database_url: str | None = None
) -> AdminNotifications:
    async with connection_scope(database_url) as connection:
        async with connection.execute(
            """
            SELECT
                (SELECT COUNT(*) FROM bot_users WHERE is_active = 1 AND news_enabled = 1) AS news_subscribers,
                (SELECT COUNT(*) FROM bot_users WHERE news_enabled = 0) AS news_opted_out,
                (SELECT COUNT(DISTINCT user_id) FROM user_media WHERE is_tracking = 1) AS series_subscribers,
                (SELECT COUNT(*) FROM user_media WHERE is_tracking = 1) AS series_subscriptions,
                (SELECT COUNT(*) FROM user_series_notifications AS notifications
                 LEFT JOIN series_notification_batches AS batches ON batches.id = notifications.batch_id
                 WHERE notifications.batch_id IS NULL OR batches.sent_at IS NULL) AS pending_series_notifications,
                (SELECT COUNT(*) FROM user_series_notifications AS notifications
                 JOIN series_notification_batches AS batches ON batches.id = notifications.batch_id
                 WHERE batches.sent_at IS NOT NULL) AS sent_series_notifications,
                (SELECT COUNT(*) FROM user_media_release_notifications WHERE sent_at IS NULL) AS pending_release_notifications,
                (SELECT COUNT(*) FROM user_media_release_notifications WHERE sent_at IS NOT NULL) AS sent_release_notifications,
                COALESCE((SELECT SUM(sent) FROM notification_delivery_runs
                 WHERE notification_type = 'news' AND created_at >= datetime('now', '-30 days')), 0) AS news_sent_30d,
                COALESCE((SELECT SUM(sent) FROM notification_delivery_runs
                 WHERE notification_type = 'release' AND created_at >= datetime('now', '-30 days')), 0) AS release_messages_sent_30d,
                COALESCE((SELECT SUM(selected) FROM notification_delivery_runs
                 WHERE created_at >= datetime('now', '-30 days')), 0) AS selected_30d,
                COALESCE((SELECT SUM(sent) FROM notification_delivery_runs
                 WHERE created_at >= datetime('now', '-30 days')), 0) AS sent_30d,
                COALESCE((SELECT SUM(failed) FROM notification_delivery_runs
                 WHERE created_at >= datetime('now', '-30 days')), 0) AS failed_30d,
                COALESCE((SELECT SUM(deactivated) FROM notification_delivery_runs
                 WHERE created_at >= datetime('now', '-30 days')), 0) AS deactivated_30d,
                (SELECT COUNT(*) FROM bot_users WHERE is_active = 0) AS blocked_users,
                (SELECT MAX(created_at) FROM notification_delivery_runs) AS last_delivery_at,
                CURRENT_TIMESTAMP AS generated_at
            """
        ) as cursor:
            row = await cursor.fetchone()
    return AdminNotifications(**dict(row))
