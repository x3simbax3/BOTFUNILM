import unittest
from datetime import datetime
from zoneinfo import ZoneInfo

from src.jobs.media_worker import next_scheduled_run


class MediaWorkerScheduleTests(unittest.TestCase):
    timezone = ZoneInfo("Europe/Moscow")

    def test_tuesday_schedules_daily_at_two(self) -> None:
        now = datetime(2026, 7, 28, 1, 30, tzinfo=self.timezone)

        target, mode = next_scheduled_run(now, self.timezone)

        self.assertEqual(target, datetime(2026, 7, 28, 2, 0, tzinfo=self.timezone))
        self.assertEqual(mode, "daily")

    def test_sunday_night_schedules_weekly_instead_of_daily(self) -> None:
        now = datetime(2026, 8, 2, 23, 0, tzinfo=self.timezone)

        target, mode = next_scheduled_run(now, self.timezone)

        self.assertEqual(target, datetime(2026, 8, 3, 2, 0, tzinfo=self.timezone))
        self.assertEqual(mode, "weekly")

    def test_after_two_schedules_notifications_at_noon(self) -> None:
        now = datetime(2026, 7, 28, 5, 0, tzinfo=self.timezone)

        target, mode = next_scheduled_run(now, self.timezone)

        self.assertEqual(target, datetime(2026, 7, 28, 12, 0, tzinfo=self.timezone))
        self.assertEqual(mode, "notifications")

    def test_after_noon_schedules_next_refresh(self) -> None:
        now = datetime(2026, 7, 28, 13, 0, tzinfo=self.timezone)

        target, mode = next_scheduled_run(now, self.timezone)

        self.assertEqual(target, datetime(2026, 7, 29, 2, 0, tzinfo=self.timezone))
        self.assertEqual(mode, "daily")


if __name__ == "__main__":
    unittest.main()
