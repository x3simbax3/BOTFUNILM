import unittest
from unittest.mock import AsyncMock, patch

from src.models import SeriesReleaseSnapshot, SeriesSeason
from src.services import series_metadata


class SeriesMetadataServiceTests(unittest.IsolatedAsyncioTestCase):
    async def test_existing_catalogue_series_uses_cached_seasons(self) -> None:
        rows = [
            {
                "season_number": 1,
                "name": "Сезон 1",
                "announced_episode_count": 12,
                "available_episode_count": 5,
            }
        ]
        with (
            patch.object(
                series_metadata,
                "get_media_by_id",
                AsyncMock(
                    return_value={
                        "number_of_seasons": 1,
                        "number_of_episodes": 12,
                        "tmdb_status": "Returning Series",
                        "tmdb_in_production": 1,
                        "next_episode_air_date": None,
                        "next_episode_season_number": 1,
                        "next_episode_number": 6,
                        "poster_path": None,
                        "rating": None,
                    }
                ),
            ) as media,
            patch.object(
                series_metadata,
                "get_media_seasons",
                AsyncMock(return_value=rows),
            ) as cached,
            patch.object(series_metadata, "fetch_tv_details", AsyncMock()) as remote,
        ):
            snapshot = await series_metadata.load_series_release_snapshot(
                {
                    "media_id": "7",
                }
            )

        media.assert_awaited_once_with(7, database_url=None)
        cached.assert_awaited_once_with(7, database_url=None)
        remote.assert_not_awaited()
        self.assertEqual(snapshot.available_episode_count, 5)
        self.assertEqual(snapshot.number_of_episodes, 12)

    async def test_new_tracking_loads_fresh_tmdb_snapshot(self) -> None:
        expected = SeriesReleaseSnapshot(
            number_of_seasons=1,
            number_of_episodes=8,
            seasons=(SeriesSeason(1, "Сезон 1", 8),),
        )
        with patch.object(
            series_metadata,
            "fetch_tv_details",
            AsyncMock(return_value=expected),
        ) as fetch:
            result = await series_metadata.load_series_release_snapshot({"tmdb_id": 42})

        fetch.assert_awaited_once_with(42, include_episode_availability=True)
        self.assertIs(result, expected)

    async def test_library_edit_rejects_missing_cached_seasons(self) -> None:
        with (
            patch.object(
                series_metadata,
                "get_media_by_id",
                AsyncMock(return_value={"number_of_seasons": 1}),
            ),
            patch.object(
                series_metadata,
                "get_media_seasons",
                AsyncMock(return_value=[]),
            ),
        ):
            with self.assertRaises(series_metadata.SeriesMetadataError):
                await series_metadata.load_series_release_snapshot(
                    {"library_progress_edit": True, "media_id": 7}
                )


if __name__ == "__main__":
    unittest.main()
