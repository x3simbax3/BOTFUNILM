import unittest
from datetime import date

from src.release_availability import release_date_has_passed
from src.tmdb_parsing import regional_movie_release_date


class ReleaseAvailabilityTests(unittest.TestCase):
    def test_compares_iso_release_date(self) -> None:
        today = date(2026, 7, 30)

        self.assertTrue(release_date_has_passed("2026-07-30", today=today))
        self.assertFalse(release_date_has_passed("2026-07-31", today=today))

    def test_unknown_date_does_not_block_user(self) -> None:
        self.assertTrue(release_date_has_passed(None))
        self.assertTrue(release_date_has_passed("unknown"))

    def test_uses_regional_public_release_instead_of_world_premiere(self) -> None:
        data = {
            "release_dates": {
                "results": [
                    {
                        "iso_3166_1": "US",
                        "release_dates": [
                            {"release_date": "2026-07-27T00:00:00Z", "type": 1},
                            {"release_date": "2026-07-31T00:00:00Z", "type": 3},
                        ],
                    },
                    {
                        "iso_3166_1": "RU",
                        "release_dates": [
                            {"release_date": "2026-08-06T00:00:00Z", "type": 3}
                        ],
                    },
                ]
            }
        }

        self.assertEqual(regional_movie_release_date(data, "RU"), "2026-08-06")
