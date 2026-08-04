from src.database.admin import get_admin_activity
from src.database.bot_users import register_bot_user, touch_bot_user
from src.database.connection import connection_scope
from src.database.user_activity import record_user_event
from tests.support.database import DatabaseTestCase


class UserActivityDatabaseTests(DatabaseTestCase):
    async def test_returns_daily_audience_and_action_metrics(self) -> None:
        await register_bot_user(1, database_url=self.database_url)
        await touch_bot_user(
            1,
            username="new_user",
            display_name="New User",
            database_url=self.database_url,
        )
        await register_bot_user(2, database_url=self.database_url)
        await touch_bot_user(
            2,
            username="returning_user",
            display_name="Returning User",
            database_url=self.database_url,
        )
        async with connection_scope(self.database_url) as connection:
            await connection.execute(
                """
                UPDATE bot_users
                SET started_at = datetime('now', '-10 days')
                WHERE user_id = 2
                """
            )
            await connection.execute(
                """
                INSERT INTO bot_user_daily_events (
                    user_id, event_date, event_type, event_count
                ) VALUES (2, date('now', '-1 day'), 'active', 1)
                """
            )

        for _ in range(2):
            await record_user_event(
                1,
                "search",
                database_url=self.database_url,
            )
        for event_type in (
            "library_open",
            "media_added",
            "rating_set",
            "progress_updated",
        ):
            await record_user_event(
                1,
                event_type,
                database_url=self.database_url,
            )

        activity = await get_admin_activity(7, database_url=self.database_url)

        self.assertEqual((activity.dau, activity.wau, activity.mau), (2, 2, 2))
        self.assertEqual(activity.new_users, 1)
        self.assertEqual(activity.returning_users, 1)
        self.assertEqual(activity.searches, 2)
        self.assertEqual(activity.library_opens, 1)
        self.assertEqual(activity.media_added, 1)
        self.assertEqual(activity.ratings_set, 1)
        self.assertEqual(activity.progress_updates, 1)
        self.assertEqual(len(activity.daily), 7)
        self.assertEqual(activity.daily[-2].active_users, 1)
        self.assertEqual(activity.daily[-2].returning_users, 1)
        self.assertEqual(activity.daily[-1].active_users, 2)
        self.assertEqual(activity.daily[-1].new_users, 1)
        self.assertEqual(activity.daily[-1].returning_users, 1)

    async def test_empty_activity_has_full_thirty_day_series(self) -> None:
        activity = await get_admin_activity(30, database_url=self.database_url)

        self.assertEqual((activity.dau, activity.wau, activity.mau), (0, 0, 0))
        self.assertEqual(len(activity.daily), 30)
        self.assertTrue(all(day.active_users == 0 for day in activity.daily))

    async def test_rejects_unknown_period_and_event(self) -> None:
        with self.assertRaisesRegex(ValueError, "days must be 7 or 30"):
            await get_admin_activity(14, database_url=self.database_url)
        with self.assertRaisesRegex(ValueError, "Unknown user activity event"):
            await record_user_event(
                1,
                "unknown",
                database_url=self.database_url,
            )
