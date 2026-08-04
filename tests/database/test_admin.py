from src.database.admin import (
    get_admin_libraries,
    get_admin_overview,
    get_admin_system,
    get_admin_user,
    get_admin_users,
    toggle_feature,
)
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


class AdminLibrariesDatabaseTests(DatabaseTestCase):
    async def test_returns_distributions_ratings_and_popular_titles(self) -> None:
        movie_id = await self.create_media(title="Popular Movie")
        series_id = await self.create_media(
            tmdb_id=43,
            content_format="series",
            content_type="anime",
            title="Popular Series",
        )
        cartoon_id = await self.create_media(
            tmdb_id=44,
            content_type="cartoon",
            title="Cartoon",
        )
        await self.create_user_media(
            user_id=1,
            media_id=movie_id,
            status="completed",
            user_rating=8,
        )
        await self.create_user_media(
            user_id=2,
            media_id=movie_id,
            status="planned",
            user_rating=10,
        )
        await self.create_user_media(
            user_id=1,
            media_id=series_id,
            status="watching",
            is_tracking=True,
        )
        await self.create_user_media(
            user_id=1,
            media_id=cartoon_id,
            status="dropped",
        )

        libraries = await get_admin_libraries(database_url=self.database_url)

        self.assertEqual(libraries.total_items, 4)
        self.assertEqual(libraries.users_with_library, 2)
        self.assertEqual(libraries.average_items_per_user, 2)
        self.assertEqual(libraries.planned_items, 1)
        self.assertEqual(libraries.watching_items, 1)
        self.assertEqual(libraries.completed_items, 1)
        self.assertEqual(libraries.on_hold_items, 0)
        self.assertEqual(libraries.dropped_items, 1)
        self.assertEqual(libraries.full_length_items, 3)
        self.assertEqual(libraries.series_items, 1)
        self.assertEqual(libraries.movie_items, 2)
        self.assertEqual(libraries.anime_items, 1)
        self.assertEqual(libraries.cartoon_items, 1)
        self.assertEqual(libraries.rated_items, 2)
        self.assertEqual(libraries.average_rating, 9)
        self.assertEqual(libraries.tracked_series, 1)
        self.assertEqual(libraries.popular_movies[0].title, "Popular Movie")
        self.assertEqual(libraries.popular_movies[0].library_users, 2)
        self.assertEqual(libraries.popular_series[0].title, "Popular Series")

    async def test_empty_database_returns_zeroes_and_empty_tops(self) -> None:
        libraries = await get_admin_libraries(database_url=self.database_url)

        self.assertEqual(libraries.total_items, 0)
        self.assertEqual(libraries.average_items_per_user, 0)
        self.assertIsNone(libraries.average_rating)
        self.assertEqual(libraries.popular_movies, ())
        self.assertEqual(libraries.popular_series, ())


class AdminSystemDatabaseTests(DatabaseTestCase):
    async def test_returns_catalog_queues_database_and_features(self) -> None:
        await self.create_series(title="Due series")
        await self.create_media(title="Movie")

        system = await get_admin_system(database_url=self.database_url)

        self.assertEqual(system.catalog_items, 2)
        self.assertEqual(system.weekly_overdue, 1)
        self.assertEqual(system.daily_overdue, 0)
        self.assertGreater(system.database_size_bytes, 0)
        self.assertEqual(system.database_journal_mode, "wal")
        self.assertEqual(system.media_refresh_enabled, 1)
        self.assertEqual(system.notifications_enabled, 1)
        self.assertEqual(system.news_enabled, 1)

    async def test_toggles_only_known_feature(self) -> None:
        enabled = await toggle_feature("news", 123, database_url=self.database_url)
        self.assertFalse(enabled)

        system = await get_admin_system(database_url=self.database_url)
        self.assertEqual(system.news_enabled, 0)

        with self.assertRaisesRegex(ValueError, "Unknown feature"):
            await toggle_feature("unknown", 123, database_url=self.database_url)
