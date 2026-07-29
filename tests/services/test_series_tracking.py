import unittest
from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, patch, sentinel

from src.database.media import get_media_by_tmdb
from src.models import SeriesEpisode, SeriesReleaseSnapshot, SeriesSeason
from src.services import series_tracking
from tests.support.database import DatabaseTestCase


@asynccontextmanager
async def connection_scope_stub(*args, **kwargs):
    yield sentinel.connection


class SeriesTrackingServiceTests(unittest.IsolatedAsyncioTestCase):
    def test_restore_progress_keys_accepts_redis_json_and_rejects_aliases(self) -> None:
        self.assertEqual(
            series_tracking.restore_progress_keys({"1": 5, "2": 1}),
            {1: 5, 2: 1},
        )
        for invalid in ({"01": 5}, {"١": 5}, {True: 5}, []):
            with self.subTest(invalid=invalid):
                with self.assertRaises(series_tracking.SeriesProgressError):
                    series_tracking.restore_progress_keys(invalid)

    async def test_prepare_tracking_preserves_progress_above_fresh_tmdb_limit(
        self,
    ) -> None:
        snapshot = SeriesReleaseSnapshot(
            number_of_seasons=1,
            number_of_episodes=12,
            seasons=(SeriesSeason(1, "Сезон 1", 12, 5),),
            status="Returning Series",
        )
        with (
            patch.object(
                series_tracking,
                "get_user_season_progress",
                AsyncMock(return_value=[{"season_number": 1, "episodes_watched": 12}]),
            ),
            patch.object(
                series_tracking,
                "get_media_seasons",
                AsyncMock(
                    return_value=[
                        {
                            "season_number": 1,
                            "name": "Сезон 1",
                            "announced_episode_count": 12,
                            "available_episode_count": 10,
                        }
                    ]
                ),
            ),
        ):
            start = await series_tracking.prepare_series_tracking(
                {"media_id": 7},
                123,
                snapshot,
            )

        self.assertEqual(start.total_episodes, 12)
        self.assertEqual(start.watched, {1: 12})
        self.assertEqual(start.seasons_data[0]["episode_count"], 12)
        self.assertTrue(start.release_data["is_ongoing"])

    def test_tracking_limits_keep_cached_seasons_missing_from_tmdb(self) -> None:
        merged = series_tracking.merge_tracking_season_limits(
            [
                {
                    "season_number": 1,
                    "name": "Season 1",
                    "episode_count": 10,
                    "announced_episode_count": 10,
                }
            ],
            [
                {
                    "season_number": 2,
                    "name": "Season 2",
                    "available_episode_count": 2,
                    "announced_episode_count": 4,
                }
            ],
            {2: 3},
        )

        self.assertEqual(
            [(season["season_number"], season["episode_count"]) for season in merged],
            [(1, 10), (2, 3)],
        )

    async def test_save_tracking_orchestrates_catalogue_release_and_progress(
        self,
    ) -> None:
        fsm_data = {
            "tmdb_id": 42,
            "tmdb_title": "Сериал",
            "content_type": "movie",
            "total_seasons": 1,
            "total_episodes": 5,
            "announced_total_episodes": 12,
            "seasons_data": [
                {
                    "season_number": 1,
                    "name": "Сезон 1",
                    "episode_count": 5,
                    "announced_episode_count": 12,
                }
            ],
            "watched_by_season": {"1": 4},
            "rating_average": 8.6,
            "ratings": {"story": 9},
            "is_ongoing": True,
            "tmdb_series_status": "Returning Series",
            "tmdb_next_episode_season_number": 1,
            "tmdb_next_episode_number": 6,
            "tmdb_next_episode_air_date": "2026-08-01",
        }
        with (
            patch.object(
                series_tracking,
                "ensure_media",
                AsyncMock(return_value=7),
            ) as ensure,
            patch.object(
                series_tracking,
                "update_media_series_release_info",
                AsyncMock(),
            ) as update,
            patch.object(
                series_tracking,
                "save_user_series_progress",
                AsyncMock(),
            ) as save,
            patch.object(series_tracking, "connection_scope", connection_scope_stub),
        ):
            result = await series_tracking.save_series_tracking_result(fsm_data, 123)

        ensure.assert_awaited_once_with(
            fsm_data,
            "series",
            number_of_seasons=1,
            number_of_episodes=12,
            available_episode_count=5,
            connection=sentinel.connection,
        )
        update.assert_awaited_once()
        snapshot = update.await_args.kwargs["snapshot"]
        self.assertEqual(snapshot.next_episode, SeriesEpisode(1, 6, "2026-08-01"))
        save.assert_awaited_once_with(
            user_id=123,
            media_id=7,
            seasons={1: 4},
            total_episodes=5,
            is_ongoing=True,
            user_rating=9,
            rating_details={"story": 9},
            connection=sentinel.connection,
        )
        self.assertEqual(result.watched_total, 4)
        self.assertEqual(result.announced_episodes, 12)

    async def test_save_tracking_rejects_empty_progress_before_writes(self) -> None:
        with patch.object(series_tracking, "ensure_media", AsyncMock()) as ensure:
            with self.assertRaises(series_tracking.EmptySeriesProgressError):
                await series_tracking.save_series_tracking_result(
                    {
                        "total_episodes": 5,
                        "seasons_data": [
                            {
                                "season_number": 1,
                                "name": "Сезон 1",
                                "episode_count": 5,
                            }
                        ],
                        "watched_by_season": {},
                    },
                    123,
                )

        ensure.assert_not_awaited()


class SeriesTrackingTransactionTests(DatabaseTestCase):
    async def test_failure_rolls_back_catalogue_and_release_writes(self) -> None:
        fsm_data = {
            "tmdb_id": 42,
            "tmdb_title": "Сериал",
            "content_type": "movie",
            "total_seasons": 1,
            "total_episodes": 5,
            "announced_total_episodes": 12,
            "seasons_data": [
                {
                    "season_number": 1,
                    "name": "Сезон 1",
                    "episode_count": 5,
                    "announced_episode_count": 12,
                }
            ],
            "watched_by_season": {1: 4},
        }
        with patch.object(
            series_tracking,
            "save_user_series_progress",
            AsyncMock(side_effect=RuntimeError("forced failure")),
        ):
            with self.assertRaisesRegex(RuntimeError, "forced failure"):
                await series_tracking.save_series_tracking_result(
                    fsm_data,
                    123,
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
