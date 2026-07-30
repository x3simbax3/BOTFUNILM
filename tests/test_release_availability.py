import unittest
from datetime import date

from src.release_availability import release_date_has_passed


class ReleaseAvailabilityTests(unittest.TestCase):
    def test_compares_iso_release_date(self) -> None:
        today = date(2026, 7, 30)

        self.assertTrue(release_date_has_passed("2026-07-30", today=today))
        self.assertFalse(release_date_has_passed("2026-07-31", today=today))

    def test_unknown_date_does_not_block_user(self) -> None:
        self.assertTrue(release_date_has_passed(None))
        self.assertTrue(release_date_has_passed("unknown"))
