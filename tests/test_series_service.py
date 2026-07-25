import unittest

from src.services.series import (
    SeriesProgressError,
    apply_episode_selection,
    validate_series_progress,
)


SEASONS = [
    {"season_number": 0, "episode_count": 2},
    {"season_number": 1, "episode_count": 8},
]


class SeriesProgressServiceTests(unittest.TestCase):
    def test_validates_progress_against_each_season(self) -> None:
        self.assertEqual(
            validate_series_progress({0: 1, 1: 8}, SEASONS, 10),
            {0: 1, 1: 8},
        )

    def test_rejects_negative_and_excess_progress(self) -> None:
        invalid_progress = (
            ({-1: 1}, 10),
            ({1: -1}, 10),
            ({1: 9}, 10),
            ({2: 1}, 10),
            ({1: 1}, 9),
        )
        for seasons, total in invalid_progress:
            with self.subTest(seasons=seasons, total=total):
                with self.assertRaises(SeriesProgressError):
                    validate_series_progress(seasons, SEASONS, total)

    def test_rejects_boolean_values_as_episode_numbers(self) -> None:
        with self.assertRaises(SeriesProgressError):
            validate_series_progress({1: True}, SEASONS, 10)

    def test_applies_selection_only_to_current_season(self) -> None:
        updated = apply_episode_selection(
            {1: 3},
            SEASONS,
            10,
            current_season=1,
            season_number=1,
            episodes_watched=5,
        )
        self.assertEqual(updated, {1: 5})

        with self.assertRaises(SeriesProgressError):
            apply_episode_selection(
                {1: 3},
                SEASONS,
                10,
                current_season=0,
                season_number=1,
                episodes_watched=5,
            )


if __name__ == "__main__":
    unittest.main()
