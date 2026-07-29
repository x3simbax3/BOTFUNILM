import unittest
from dataclasses import FrozenInstanceError

from src.models import SeriesEpisode, SeriesReleaseSnapshot, SeriesSeason
from src.tmdb_models import TmdbEpisodeAirInfo


class SeriesModelTests(unittest.TestCase):
    def test_snapshot_freezes_seasons_and_uses_shared_episode_type(self) -> None:
        source = [SeriesSeason(1, "Сезон 1", 12, 5)]
        episode = TmdbEpisodeAirInfo(1, 6, "2026-08-01")
        snapshot = SeriesReleaseSnapshot(
            number_of_seasons=1,
            number_of_episodes=12,
            seasons=source,
            next_episode_to_air=episode,
        )
        source.append(SeriesSeason(2, "Сезон 2", 8))

        self.assertIsInstance(snapshot.seasons, tuple)
        self.assertEqual(len(snapshot.seasons), 1)
        self.assertIsInstance(snapshot.next_episode, SeriesEpisode)
        with self.assertRaises(FrozenInstanceError):
            snapshot.next_episode.episode_number = 7

    def test_fsm_snapshot_restores_availability_and_release_fields(self) -> None:
        snapshot = SeriesReleaseSnapshot.from_fsm(
            {
                "total_seasons": 2,
                "announced_total_episodes": 16,
                "seasons_data": [
                    {
                        "season_number": 0,
                        "name": "Спецвыпуски",
                        "episode_count": 3,
                    },
                    {
                        "season_number": 1,
                        "name": "Сезон 1",
                        "episode_count": 5,
                        "announced_episode_count": 12,
                    },
                ],
                "tmdb_series_status": "Returning Series",
                "tmdb_series_in_production": True,
                "tmdb_next_episode_season_number": 1,
                "tmdb_next_episode_number": 6,
                "tmdb_next_episode_air_date": "2026-08-01",
            }
        )

        self.assertEqual(snapshot.available_episode_count, 5)
        self.assertEqual(snapshot.announced_episode_count, 16)
        self.assertTrue(snapshot.active)
        self.assertEqual(snapshot.next_episode, SeriesEpisode(1, 6, "2026-08-01"))
        self.assertEqual(
            [season.season_number for season in snapshot.regular_seasons], [1]
        )

    def test_snapshot_serialization_contains_no_transport_objects(self) -> None:
        snapshot = SeriesReleaseSnapshot(
            number_of_seasons=1,
            number_of_episodes=12,
            seasons=(SeriesSeason(1, "Сезон 1", 12, 5),),
            status="Returning Series",
            next_episode_to_air=SeriesEpisode(1, 6, None),
        )

        self.assertEqual(
            snapshot.to_fsm_dict(),
            {
                "total_seasons": 1,
                "announced_total_episodes": 12,
                "is_ongoing": True,
                "tmdb_series_status": "Returning Series",
                "tmdb_series_in_production": None,
                "tmdb_next_episode_air_date": None,
                "tmdb_next_episode_season_number": 1,
                "tmdb_next_episode_number": 6,
            },
        )


if __name__ == "__main__":
    unittest.main()
