import unittest
from unittest.mock import AsyncMock, patch

from src.models import MediaWorkflowData, SeriesReleaseSnapshot, SeriesSeason
from src.services import planned_media


class PlannedMediaServiceTests(unittest.IsolatedAsyncioTestCase):
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
        ):
            result = await planned_media.save_planned_media(123, workflow)

        fetch.assert_awaited_once_with(42, include_episode_availability=True)
        ensure.assert_awaited_once_with(
            workflow.to_fsm_dict(),
            "series",
            number_of_seasons=1,
            number_of_episodes=12,
            available_episode_count=5,
        )
        update.assert_awaited_once_with(7, user_id=123, snapshot=snapshot)
        save.assert_awaited_once_with(user_id=123, media_id=7, status="planned")
        self.assertEqual(result.media_id, 7)
        self.assertIs(result.series_snapshot, snapshot)

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
            patch.object(planned_media, "save_user_media", AsyncMock()),
        ):
            result = await planned_media.save_planned_media(123, workflow)

        fetch.assert_not_awaited()
        update.assert_not_awaited()
        self.assertIsNone(result.series_snapshot)


if __name__ == "__main__":
    unittest.main()
