from src.database.admin import get_admin_notifications
from src.database.bot_users import (
    mark_bot_user_inactive,
    register_bot_user,
    toggle_news_enabled,
)
from src.database.connection import connection_scope
from src.database.notification_delivery import record_notification_delivery
from tests.support.database import DatabaseTestCase


class NotificationDeliveryDatabaseTests(DatabaseTestCase):
    async def test_returns_subscriptions_queues_history_and_delivery(self) -> None:
        for user_id in (1, 2, 3):
            await register_bot_user(user_id, database_url=self.database_url)
        await toggle_news_enabled(2, database_url=self.database_url)
        await mark_bot_user_inactive(3, database_url=self.database_url)

        media_id = await self.create_media(
            content_format="series",
            title="Series",
        )
        for user_id in (1, 2):
            await self.create_user_media(
                user_id=user_id,
                media_id=media_id,
                is_tracking=True,
            )

        async with connection_scope(self.database_url) as connection:
            sent_batch = await connection.execute(
                """
                INSERT INTO series_notification_batches (user_id, sent_at)
                VALUES (1, CURRENT_TIMESTAMP)
                """
            )
            pending_batch = await connection.execute(
                "INSERT INTO series_notification_batches (user_id) VALUES (2)"
            )
            await connection.executemany(
                """
                INSERT INTO user_series_notifications (
                    user_id, media_id, previous_episode_count,
                    current_episode_count, batch_id
                ) VALUES (?, ?, ?, ?, ?)
                """,
                (
                    (1, media_id, 1, 2, sent_batch.lastrowid),
                    (2, media_id, 1, 2, pending_batch.lastrowid),
                    (1, media_id, 2, 3, None),
                ),
            )
            await connection.executemany(
                """
                INSERT INTO user_media_release_notifications (
                    user_id, media_id, sent_at
                ) VALUES (?, ?, ?)
                """,
                (
                    (1, media_id, "2026-08-01 10:00:00"),
                    (2, media_id, None),
                ),
            )

        await record_notification_delivery(
            "news",
            selected=10,
            sent=8,
            failed=1,
            deactivated=1,
            database_url=self.database_url,
        )
        await record_notification_delivery(
            "release",
            selected=5,
            sent=4,
            failed=1,
            database_url=self.database_url,
        )

        notifications = await get_admin_notifications(database_url=self.database_url)

        self.assertEqual(notifications.news_subscribers, 1)
        self.assertEqual(notifications.news_opted_out, 1)
        self.assertEqual(notifications.series_subscribers, 2)
        self.assertEqual(notifications.series_subscriptions, 2)
        self.assertEqual(notifications.pending_series_notifications, 2)
        self.assertEqual(notifications.sent_series_notifications, 1)
        self.assertEqual(notifications.pending_release_notifications, 1)
        self.assertEqual(notifications.sent_release_notifications, 1)
        self.assertEqual(notifications.news_sent_30d, 8)
        self.assertEqual(notifications.release_messages_sent_30d, 4)
        self.assertEqual(notifications.selected_30d, 15)
        self.assertEqual(notifications.sent_30d, 12)
        self.assertEqual(notifications.failed_30d, 2)
        self.assertEqual(notifications.deactivated_30d, 1)
        self.assertEqual(notifications.success_percent_30d, 80)
        self.assertEqual(notifications.blocked_users, 1)
        self.assertIsNotNone(notifications.last_delivery_at)

    async def test_empty_database_returns_zeroes(self) -> None:
        notifications = await get_admin_notifications(database_url=self.database_url)

        self.assertEqual(notifications.selected_30d, 0)
        self.assertEqual(notifications.success_percent_30d, 0)
        self.assertIsNone(notifications.last_delivery_at)

    async def test_rejects_invalid_delivery_values(self) -> None:
        with self.assertRaisesRegex(ValueError, "Unknown notification type"):
            await record_notification_delivery(
                "unknown",
                selected=1,
                sent=1,
                failed=0,
                database_url=self.database_url,
            )
        with self.assertRaisesRegex(ValueError, "non-negative integers"):
            await record_notification_delivery(
                "news",
                selected=1,
                sent=-1,
                failed=0,
                database_url=self.database_url,
            )
