import unittest
from datetime import date
from unittest.mock import AsyncMock, patch

from src import tmdb_series
from tests.support.tmdb import mock_tmdb_api


class TmdbSeriesTests(unittest.IsolatedAsyncioTestCase):
    async def test_tv_details_excludes_specials_from_trackable_seasons(self) -> None:
        data = {
            "number_of_seasons": 2,
            "number_of_episodes": 10,
            "status": "Returning Series",
            "in_production": True,
            "poster_path": "/poster.jpg",
            "vote_average": 8.7,
            "next_episode_to_air": {
                "season_number": 3,
                "episode_number": 1,
                "air_date": "2026-09-15",
            },
            "seasons": [
                {"season_number": 0, "name": "Specials", "episode_count": 25},
                {"season_number": 1, "name": "Season 1", "episode_count": 6},
                {"season_number": 2, "name": "Season 2", "episode_count": 4},
            ],
        }

        with mock_tmdb_api(data):
            details = await tmdb_series.fetch_tv_details(42)

        self.assertEqual(details.number_of_seasons, 2)
        self.assertEqual(details.number_of_episodes, 10)
        self.assertEqual(details.status, "Returning Series")
        self.assertTrue(details.in_production)
        self.assertEqual(details.next_episode_to_air.season_number, 3)
        self.assertEqual(details.next_episode_to_air.episode_number, 1)
        self.assertEqual(details.next_episode_to_air.air_date, "2026-09-15")
        self.assertEqual(details.poster_path, "/poster.jpg")
        self.assertEqual(details.rating, 8.7)
        self.assertEqual(
            [
                (season.season_number, season.episode_count)
                for season in details.seasons
            ],
            [(1, 6), (2, 4)],
        )

    async def test_active_series_counts_only_aired_episodes(self) -> None:
        series_data = {
            "number_of_seasons": 1,
            "number_of_episodes": 12,
            "status": "Returning Series",
            "in_production": True,
            "last_episode_to_air": {
                "season_number": 1,
                "episode_number": 5,
                "air_date": "2026-07-20",
            },
            "next_episode_to_air": {
                "season_number": 1,
                "episode_number": 6,
                "air_date": "2026-08-03",
            },
            "seasons": [{"season_number": 1, "name": "Season 1", "episode_count": 12}],
        }
        season_data = {
            "episodes": [
                {"episode_number": episode, "air_date": "2026-07-20"}
                for episode in range(1, 6)
            ]
            + [
                {"episode_number": episode, "air_date": "2026-08-03"}
                for episode in range(6, 13)
            ]
        }
        fetch = AsyncMock(side_effect=[series_data, season_data])

        with (
            mock_tmdb_api(fetch=fetch),
            patch.object(tmdb_series, "date") as mocked_date,
        ):
            mocked_date.today.return_value = date(2026, 7, 28)
            mocked_date.fromisoformat.side_effect = date.fromisoformat
            details = await tmdb_series.fetch_tv_details(
                42,
                include_episode_availability=True,
            )

        self.assertEqual(details.number_of_episodes, 12)
        self.assertEqual(details.seasons[0].episode_count, 12)
        self.assertEqual(details.seasons[0].available_episode_count, 5)
