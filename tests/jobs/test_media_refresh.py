from datetime import date

from src.database.connection import connection_scope
from src.database.media import get_media_by_tmdb
from src.database.media_release_notifications import (
    get_pending_release_users,
    get_release_notifications,
)
from src.database.series import get_user_season_progress, save_user_series_progress
from src.database.series_subscriptions import (
    get_notification_batch,
    list_tracked_series,
    prepare_notification_batches,
    set_series_subscription,
)
from src.jobs.media_refresh import (
    preview_media_refresh,
    save_media_refresh,
    save_movie_release_refresh,
    select_due_media_batch,
)
from src.models import SeriesEpisode, SeriesReleaseSnapshot, SeriesSeason
from src.tmdb_models import TmdbMovieDetails
from tests.support.database import DatabaseTestCase


class MediaRefreshDatabaseTests(DatabaseTestCase):
    async def test_daily_selects_and_releases_planned_future_movie(self) -> None:
        media_id = await self.create_user_media(
            status="planned",
            media_kwargs={
                "tmdb_id": 99,
                "title": "Будущий фильм",
                "release_date": "2026-07-31",
                "is_released": False,
            },
        )

        rows = await select_due_media_batch("daily", database_url=self.database_url)
        self.assertEqual([row.media_id for row in rows], [media_id])
        self.assertEqual(rows[0].content_format, "full_length")

        await save_movie_release_refresh(
            media_id,
            TmdbMovieDetails(
                title="Будущий фильм",
                original_title=None,
                description="Описание",
                poster_path=None,
                rating=8.0,
                release_date="2026-07-30",
                status="Released",
            ),
            today=date(2026, 7, 30),
            database_url=self.database_url,
        )

        self.assertEqual(
            await get_pending_release_users(database_url=self.database_url),
            [123],
        )
        notifications = await get_release_notifications(
            123,
            database_url=self.database_url,
        )
        self.assertEqual(notifications[0].title, "Будущий фильм")

    async def test_movie_status_does_not_override_future_regional_date(self) -> None:
        media_id = await self.create_user_media(
            status="planned",
            media_kwargs={
                "tmdb_id": 100,
                "title": "Будущий фильм",
                "release_date": "2026-08-06",
                "is_released": False,
            },
        )

        await save_movie_release_refresh(
            media_id,
            TmdbMovieDetails(
                title="Будущий фильм",
                original_title=None,
                description=None,
                poster_path=None,
                rating=None,
                release_date="2026-08-06",
                status="Released",
            ),
            today=date(2026, 7, 30),
            database_url=self.database_url,
        )

        media = await get_media_by_tmdb(
            100,
            "full_length",
            "movie",
            database_url=self.database_url,
        )
        self.assertFalse(media["is_released"])
        self.assertEqual(
            await get_pending_release_users(database_url=self.database_url), []
        )

    async def test_refresh_queues_new_episode_for_subscriber(self) -> None:
        media_id = await self.create_user_media(
            media_kwargs={
                "tmdb_id": 300,
                "content_format": "series",
                "content_type": "anime",
                "title": "Табакошка",
                "number_of_episodes": 4,
                "available_episode_count": 3,
            }
        )
        async with connection_scope(self.database_url) as connection:
            await connection.execute(
                "UPDATE media SET tmdb_status = 'Returning Series' WHERE id = ?",
                (media_id,),
            )
        await set_series_subscription(
            123,
            media_id,
            True,
            database_url=self.database_url,
        )
        snapshot = SeriesReleaseSnapshot(
            number_of_seasons=1,
            number_of_episodes=4,
            seasons=(SeriesSeason(1, "Season 1", 4, 4),),
            status="Returning Series",
            in_production=True,
            last_episode_to_air=SeriesEpisode(1, 4, "2026-07-30"),
        )

        await save_media_refresh(
            media_id,
            snapshot,
            "daily",
            database_url=self.database_url,
        )

        batches = await prepare_notification_batches(database_url=self.database_url)
        self.assertEqual(len(batches), 1)
        items = await get_notification_batch(
            batches[0].batch_id,
            123,
            database_url=self.database_url,
        )
        self.assertEqual(items[0].released_count, 1)
        self.assertEqual(items[0].episode_number, 4)

    async def test_series_premiere_sends_one_notification_and_stays_tracked(
        self,
    ) -> None:
        media_id = await self.create_user_media(
            status="planned",
            is_tracking=True,
            media_kwargs={
                "tmdb_id": 301,
                "content_format": "series",
                "content_type": "movie",
                "title": "Будущий сериал",
                "number_of_episodes": 8,
                "available_episode_count": 0,
                "is_released": False,
            },
        )
        snapshot = SeriesReleaseSnapshot(
            number_of_seasons=1,
            number_of_episodes=8,
            seasons=(SeriesSeason(1, "Season 1", 8, 1),),
            status="Returning Series",
            in_production=True,
            last_episode_to_air=SeriesEpisode(1, 1, "2026-07-30"),
        )

        await save_media_refresh(
            media_id,
            snapshot,
            "daily",
            database_url=self.database_url,
        )

        self.assertEqual(
            await get_pending_release_users(database_url=self.database_url),
            [123],
        )
        self.assertEqual(
            await prepare_notification_batches(database_url=self.database_url),
            [],
        )
        tracked = await list_tracked_series(123, database_url=self.database_url)
        self.assertEqual([int(item["id"]) for item in tracked], [media_id])
        self.assertEqual(tracked[0]["user_status"], "planned")

    async def test_daily_selects_only_due_active_series(self) -> None:
        active_id = await self.create_series(tmdb_id=101, title="Active")
        await self.create_series(tmdb_id=102, title="Ended")
        await self.create_media(tmdb_id=103, title="Movie")
        fresh_id = await self.create_series(tmdb_id=104, title="Fresh")
        async with connection_scope(self.database_url) as connection:
            await connection.execute(
                "UPDATE media SET tmdb_status = 'Returning Series' WHERE id = ?",
                (active_id,),
            )
            await connection.execute(
                "UPDATE media SET tmdb_status = 'Ended' WHERE tmdb_id = 102"
            )
            await connection.execute(
                """
                UPDATE media SET tmdb_status = 'Returning Series',
                    tmdb_release_checked_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (fresh_id,),
            )

        rows = await select_due_media_batch("daily", database_url=self.database_url)

        self.assertEqual([row.media_id for row in rows], [active_id])

    async def test_weekly_selects_series_of_every_status(self) -> None:
        ended_id = await self.create_series(tmdb_id=201, title="Ended")
        active_id = await self.create_series(tmdb_id=202, title="Active")
        await self.create_media(tmdb_id=203, title="Movie")
        async with connection_scope(self.database_url) as connection:
            await connection.execute(
                "UPDATE media SET tmdb_status = 'Ended' WHERE id = ?",
                (ended_id,),
            )
            await connection.execute(
                "UPDATE media SET tmdb_status = 'Returning Series' WHERE id = ?",
                (active_id,),
            )

        rows = await select_due_media_batch("weekly", database_url=self.database_url)

        self.assertEqual([row.media_id for row in rows], [ended_id, active_id])

    async def test_weekly_refresh_updates_metadata_and_preserves_user_progress(
        self,
    ) -> None:
        media_id = await self.create_series(
            tmdb_id=301,
            title="Old title",
            poster_path="/old.jpg",
            telegram_poster_file_id="cached-file",
            number_of_seasons=1,
            number_of_episodes=10,
            available_episode_count=5,
        )
        await save_user_series_progress(
            user_id=123,
            media_id=media_id,
            seasons={1: 4},
            total_episodes=5,
            database_url=self.database_url,
        )
        snapshot = SeriesReleaseSnapshot(
            number_of_seasons=2,
            number_of_episodes=12,
            seasons=(
                SeriesSeason(1, "Season 1", 10, 10),
                SeriesSeason(2, "Season 2", 2, 1),
            ),
            status="Returning Series",
            in_production=True,
            next_episode_to_air=SeriesEpisode(2, 2, "2026-08-02"),
            last_episode_to_air=SeriesEpisode(2, 1, "2026-07-26"),
            poster_path="/new.jpg",
            rating=8.8,
            title="New title",
            original_title="Original title",
            description="New description",
            first_air_date="2025-01-01",
        )

        changes = await save_media_refresh(
            media_id,
            snapshot,
            "weekly",
            database_url=self.database_url,
        )

        self.assertTrue(changes)
        media = await get_media_by_tmdb(
            301,
            "series",
            "movie",
            database_url=self.database_url,
        )
        self.assertEqual(media["title"], "New title")
        self.assertEqual(media["available_episode_count"], 11)
        self.assertEqual(media["next_episode_number"], 2)
        self.assertEqual(media["last_episode_number"], 1)
        self.assertEqual(media["telegram_poster_file_id"], None)
        self.assertIsNotNone(media["tmdb_release_checked_at"])
        self.assertIsNotNone(media["tmdb_metadata_checked_at"])
        progress = await get_user_season_progress(
            123,
            media_id,
            database_url=self.database_url,
        )
        self.assertEqual(progress[0]["episodes_watched"], 4)

    async def test_preview_reports_changes_without_writing(self) -> None:
        media_id = await self.create_series(tmdb_id=401, title="Old")
        snapshot = SeriesReleaseSnapshot(
            number_of_seasons=1,
            number_of_episodes=1,
            seasons=(SeriesSeason(1, "Season 1", 1, 1),),
            title="New",
        )

        changes = await preview_media_refresh(
            media_id,
            snapshot,
            database_url=self.database_url,
        )

        self.assertIn("title", {change.field for change in changes})
        media = await get_media_by_tmdb(
            401,
            "series",
            "movie",
            database_url=self.database_url,
        )
        self.assertEqual(media["title"], "Old")
        self.assertIsNone(media["tmdb_release_checked_at"])
