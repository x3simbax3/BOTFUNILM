import unittest
from datetime import date, datetime
from unittest.mock import AsyncMock
from zoneinfo import ZoneInfo

from src.jobs.media_worker import (
    _news_result_text,
    _send_admin_job_result,
    daily_news_targets,
    next_scheduled_run,
)
from src.jobs.news_broadcast import NewsBroadcastStats


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

    def test_news_targets_have_two_hour_slots_and_bounded_jitter(self) -> None:
        targets = daily_news_targets(
            date(2026, 7, 30),
            self.timezone,
            offsets=(-300, -1, 0, 60, 300, -300, 300),
        )

        self.assertEqual(targets[0].hour, 9)
        self.assertEqual(targets[0].minute, 0)
        self.assertEqual(targets[1].hour, 10)
        self.assertEqual(targets[1].minute, 59)
        self.assertEqual(targets[-1].hour, 21)
        self.assertEqual(targets[-1].minute, 5)
        self.assertLess(targets[-1], datetime(2026, 7, 30, 22, tzinfo=self.timezone))

    def test_admin_news_result_explains_empty_and_successful_runs(self) -> None:
        self.assertIn("не найдена", _news_result_text(NewsBroadcastStats()))
        self.assertEqual(
            _news_result_text(
                NewsBroadcastStats(
                    selected=3,
                    sent=2,
                    failed=1,
                    article_uuid="article-id",
                )
            ),
            "Новость отправлена: 2 из 3, ошибок 1.",
        )


class MediaWorkerAdminResultTests(unittest.IsolatedAsyncioTestCase):
    async def test_sends_job_result_only_for_valid_admin_id(self) -> None:
        bot = AsyncMock()

        await _send_admin_job_result(bot, 123, "Готово")
        await _send_admin_job_result(bot, "123", "Не отправлять")

        bot.send_message.assert_awaited_once_with(123, "Готово")


if __name__ == "__main__":
    unittest.main()
