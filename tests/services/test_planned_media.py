import unittest
from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, patch, sentinel

from src.database.media import get_media_by_tmdb
from src.models import MediaWorkflowData, SeriesReleaseSnapshot, SeriesSeason
from src.services import planned_media
from tests.support.database import DatabaseTestCase


@asynccontextmanager
async def connection_scope_stub(*args, **kwargs):
    yield sentinel.connection


class PlannedMediaServiceTests(DatabaseTestCase):
    async def test_existing_series_plan_uses_cached_snapshot_without_tmdb(self) -> None:
        workflow = MediaWorkflowData(
            media_id=7,
            tmdb_id=42,
            tmdb_title="Сериал",
            tmdb_description=None,
            tmdb_poster_path=None,
            tmdb_original_title=None,
            tmdb_release_date=None,
            tmdb_rating=None,
            content_format="series",
            content_type="movie",
        )
        snapshot = SeriesReleaseSnapshot(
            number_of_seasons=1,
            number_of_episodes=12,
            seasons=(SeriesSeason(1, "Сезон 1", 12, 3),),
            status="Returning Series",
            in_production=True,
        )
        with (
            patch.object(
                planned_media,
                "load_cached_series_release_snapshot",
                AsyncMock(return_value=snapshot),
            ) as cached,
            patch.object(planned_media, "fetch_tv_details", AsyncMock()) as fetch,
            patch.object(
                planned_media,
                "ensure_media",
                AsyncMock(return_value=7),
            ),
            patch.object(
                planned_media,
                "update_media_series_release_info",
                AsyncMock(),
            ),
            patch.object(planned_media, "save_user_media", AsyncMock()),
            patch.object(planned_media, "connection_scope", connection_scope_stub),
        ):
            result = await planned_media.save_planned_media(123, workflow)

        cached.assert_awaited_once_with(7, database_url=None)
        fetch.assert_not_awaited()
        self.assertEqual(result.series_snapshot.available_episode_count, 3)

    async def test_series_plan_persists_release_snapshot_before_user_entry(
        self,
    ) -> None:
        workflow = MediaWorkflowData(
            media_id=None,
            tmdb_id=42,
            tmdb_title="Сериал",
            tmdb_description=None,
            tmdb_poster_path=None,
            tmdb_original_title=None,
            tmdb_release_date=None,
            tmdb_rating=None,
            content_format="series",
            content_type="movie",
        )
        snapshot = SeriesReleaseSnapshot(
            number_of_seasons=1,
            number_of_episodes=12,
            seasons=(SeriesSeason(1, "Сезон 1", 12, 5),),
        )
        with (
            patch.object(
                planned_media,
                "fetch_tv_details",
                AsyncMock(return_value=snapshot),
            ) as fetch,
            patch.object(
                planned_media,
                "ensure_media",
                AsyncMock(return_value=7),
            ) as ensure,
            patch.object(
                planned_media,
                "update_media_series_release_info",
                AsyncMock(),
            ) as update,
            patch.object(
                planned_media,
                "save_user_media",
                AsyncMock(),
            ) as save,
            patch.object(planned_media, "connection_scope", connection_scope_stub),
        ):
            result = await planned_media.save_planned_media(123, workflow)

        fetch.assert_awaited_once_with(42, include_episode_availability=True)
        ensure.assert_awaited_once_with(
            workflow.to_fsm_dict(),
            "series",
            number_of_seasons=1,
            number_of_episodes=12,
            available_episode_count=5,
            is_released=True,
            connection=sentinel.connection,
        )
        update.assert_awaited_once_with(
            7,
            user_id=123,
            snapshot=snapshot,
            connection=sentinel.connection,
        )
        save.assert_awaited_once_with(
            user_id=123,
            media_id=7,
            status="planned",
            is_tracking=False,
            connection=sentinel.connection,
        )
        self.assertEqual(result.media_id, 7)
        self.assertIs(result.series_snapshot, snapshot)
        self.assertFalse(result.tracking_enabled)

    async def test_future_series_is_automatically_tracked(self) -> None:
        workflow = MediaWorkflowData(
            media_id=None,
            tmdb_id=42,
            tmdb_title="Будущий сериал",
            tmdb_description=None,
            tmdb_poster_path=None,
            tmdb_original_title=None,
            tmdb_release_date=None,
            tmdb_rating=None,
            content_format="series",
            content_type="movie",
            is_released=False,
        )
        snapshot = SeriesReleaseSnapshot(
            number_of_seasons=1,
            number_of_episodes=8,
            seasons=(SeriesSeason(1, "Сезон 1", 8, 0),),
            status="Planned",
            in_production=True,
        )
        with (
            patch.object(
                planned_media,
                "fetch_tv_details",
                AsyncMock(return_value=snapshot),
            ),
            patch.object(
                planned_media,
                "ensure_media",
                AsyncMock(return_value=7),
            ),
            patch.object(
                planned_media,
                "update_media_series_release_info",
                AsyncMock(),
            ),
            patch.object(planned_media, "save_user_media", AsyncMock()) as save,
            patch.object(planned_media, "connection_scope", connection_scope_stub),
        ):
            result = await planned_media.save_planned_media(123, workflow)

        save.assert_awaited_once_with(
            user_id=123,
            media_id=7,
            status="planned",
            is_tracking=True,
            connection=sentinel.connection,
        )
        self.assertTrue(result.tracking_enabled)

    async def test_movie_plan_does_not_request_series_metadata(self) -> None:
        workflow = MediaWorkflowData(
            media_id=7,
            tmdb_id=42,
            tmdb_title="Фильм",
            tmdb_description=None,
            tmdb_poster_path=None,
            tmdb_original_title=None,
            tmdb_release_date=None,
            tmdb_rating=None,
            content_format="full_length",
            content_type="movie",
        )
        with (
            patch.object(planned_media, "fetch_tv_details", AsyncMock()) as fetch,
            patch.object(planned_media, "ensure_media", AsyncMock(return_value=7)),
            patch.object(
                planned_media,
                "update_media_series_release_info",
                AsyncMock(),
            ) as update,
            patch.object(
                planned_media,
                "update_movie_release_availability",
                AsyncMock(),
            ) as update_movie,
            patch.object(planned_media, "save_user_media", AsyncMock()),
            patch.object(planned_media, "connection_scope", connection_scope_stub),
        ):
            result = await planned_media.save_planned_media(123, workflow)

        fetch.assert_not_awaited()
        update.assert_not_awaited()
        update_movie.assert_awaited_once_with(
            7,
            None,
            True,
            connection=sentinel.connection,
        )
        self.assertIsNone(result.series_snapshot)

    async def test_future_existing_movie_is_corrected_and_tracked(self) -> None:
        media_id = await self.create_media(
            tmdb_id=969681,
            content_format="full_length",
            content_type="movie",
            title="Человек-паук: Новый день",
            release_date="2026-07-28",
            is_released=True,
        )
        workflow = MediaWorkflowData(
            media_id=media_id,
            tmdb_id=969681,
            tmdb_title="Человек-паук: Новый день",
            tmdb_description=None,
            tmdb_poster_path=None,
            tmdb_original_title="Spider-Man: Brand New Day",
            tmdb_release_date="2999-08-06",
            tmdb_rating=None,
            content_format="full_length",
            content_type="movie",
            is_released=False,
        )

        await planned_media.save_planned_media(
            123,
            workflow,
            database_url=self.database_url,
        )

        media = await get_media_by_tmdb(
            969681,
            "full_length",
            "movie",
            database_url=self.database_url,
        )
        self.assertFalse(media["is_released"])
        self.assertEqual(media["release_date"], "2999-08-06")


class PlannedMediaTransactionTests(DatabaseTestCase):
    async def test_failure_rolls_back_catalogue_and_release_writes(self) -> None:
        workflow = MediaWorkflowData(
            media_id=None,
            tmdb_id=42,
            tmdb_title="Сериал",
            tmdb_description=None,
            tmdb_poster_path=None,
            tmdb_original_title=None,
            tmdb_release_date=None,
            tmdb_rating=None,
            content_format="series",
            content_type="movie",
        )
        snapshot = SeriesReleaseSnapshot(
            number_of_seasons=1,
            number_of_episodes=12,
            seasons=(SeriesSeason(1, "Сезон 1", 12, 5),),
        )
        with (
            patch.object(
                planned_media,
                "fetch_tv_details",
                AsyncMock(return_value=snapshot),
            ),
            patch.object(
                planned_media,
                "save_user_media",
                AsyncMock(side_effect=RuntimeError("forced failure")),
            ),
        ):
            with self.assertRaisesRegex(RuntimeError, "forced failure"):
                await planned_media.save_planned_media(
                    123,
                    workflow,
                    database_url=self.database_url,
                )

        media = await get_media_by_tmdb(
            42,
            "series",
            "movie",
            database_url=self.database_url,
        )
        self.assertIsNone(media)


if __name__ == "__main__":
    unittest.main()
