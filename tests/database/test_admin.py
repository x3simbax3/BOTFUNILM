from src.database.admin import get_admin_overview, get_admin_user, get_admin_users
from src.database.bot_users import (
    mark_bot_user_inactive,
    register_bot_user,
    touch_bot_user,
)
from src.database.connection import connection_scope
from tests.support.database import DatabaseTestCase


class AdminOverviewDatabaseTests(DatabaseTestCase):
    async def test_returns_user_and_library_overview(self) -> None:
        for user_id in (1, 2, 3):
            await register_bot_user(user_id, database_url=self.database_url)
        await mark_bot_user_inactive(3, database_url=self.database_url)

        first_media_id = await self.create_user_media(
            user_id=1,
            user_rating=8,
        )
        await self.create_user_media(
            user_id=1,
            media_kwargs={
                "tmdb_id": 43,
                "content_format": "series",
                "title": "Series",
            },
            status="watching",
            is_tracking=True,
        )
        self.assertGreater(first_media_id, 0)

        async with connection_scope(self.database_url) as connection:
            await connection.execute(
                """
                UPDATE bot_users
                SET started_at = datetime('now', '-10 days'),
                    last_activity_at = datetime('now', '-8 days')
                WHERE user_id = 2
                """
            )
            await connection.execute(
                """
                UPDATE bot_users
                SET started_at = datetime('now', '-40 days'),
                    last_activity_at = datetime('now', '-40 days')
                WHERE user_id = 3
                """
            )

        overview = await get_admin_overview(database_url=self.database_url)

        self.assertEqual(overview.total_users, 3)
        self.assertEqual(overview.active_users, 2)
        self.assertEqual(overview.inactive_users, 1)
        self.assertEqual(
            (overview.new_24h, overview.new_7d, overview.new_30d), (1, 1, 2)
        )
        self.assertEqual(
            (overview.active_24h, overview.active_7d, overview.active_30d),
            (1, 1, 2),
        )
        self.assertEqual(overview.activated_users, 1)
        self.assertAlmostEqual(overview.activation_percent, 100 / 3)
        self.assertEqual(overview.library_items, 2)
        self.assertAlmostEqual(overview.average_library_items, 2 / 3)
        self.assertEqual(overview.rated_items, 1)
        self.assertEqual(overview.tracked_series, 1)
        self.assertEqual(overview.news_users, 2)

        await touch_bot_user(
            1,
            username="viewer",
            display_name="Test Viewer",
            database_url=self.database_url,
        )
        first_page = await get_admin_users(
            1,
            page_size=2,
            database_url=self.database_url,
        )
        second_page = await get_admin_users(
            2,
            page_size=2,
            database_url=self.database_url,
        )

        self.assertEqual(first_page.total_users, 3)
        self.assertEqual(first_page.total_pages, 2)
        self.assertEqual([user.user_id for user in first_page.users], [1, 2])
        self.assertEqual(first_page.users[0].username, "viewer")
        self.assertEqual(first_page.users[0].display_name, "Test Viewer")
        self.assertEqual(first_page.users[0].library_items, 2)
        self.assertEqual([user.user_id for user in second_page.users], [3])

        user = await get_admin_user(1, database_url=self.database_url)

        self.assertIsNotNone(user)
        self.assertEqual(user.library_items, 2)
        self.assertEqual(user.planned_items, 1)
        self.assertEqual(user.watching_items, 1)
        self.assertEqual(user.rated_items, 1)
        self.assertEqual(user.average_rating, 8)
        self.assertEqual(user.tracked_series, 1)

    async def test_missing_user_returns_none(self) -> None:
        self.assertIsNone(await get_admin_user(999, database_url=self.database_url))

    async def test_user_page_rejects_invalid_values(self) -> None:
        with self.assertRaisesRegex(ValueError, "page must be positive"):
            await get_admin_users(0, database_url=self.database_url)
        with self.assertRaisesRegex(ValueError, "page_size must be positive"):
            await get_admin_users(
                1,
                page_size=0,
                database_url=self.database_url,
            )

    async def test_empty_database_returns_zeroes(self) -> None:
        overview = await get_admin_overview(database_url=self.database_url)

        self.assertEqual(overview.total_users, 0)
        self.assertEqual(overview.activation_percent, 0)
        self.assertEqual(overview.average_library_items, 0)
