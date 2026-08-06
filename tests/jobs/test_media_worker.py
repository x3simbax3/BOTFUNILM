import unittest
from asyncio import sleep as yield_to_event_loop
from datetime import date, datetime
from unittest.mock import AsyncMock, patch
from zoneinfo import ZoneInfo

from src.jobs.media_worker import (
    LockLostError,
    RedisJobLock,
    _news_result_text,
    _notify_admins_about_news_failure,
    _send_admin_job_result,
    _short_traceback,
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

    def test_news_targets_run_every_two_hours_with_bounded_jitter(self) -> None:
        targets = daily_news_targets(
            date(2026, 7, 30),
            self.timezone,
            offsets=(-300, -1, 0, 0, 0, 1, 300),
        )

        self.assertEqual(len(targets), 7)
        self.assertEqual(targets[0].hour, 10)
        self.assertEqual(targets[0].minute, 0)
        self.assertEqual(targets[1].hour, 11)
        self.assertEqual(targets[1].minute, 59)
        self.assertEqual(targets[-1].hour, 22)
        self.assertEqual(targets[-1].minute, 5)
        self.assertLess(targets[-1], datetime(2026, 7, 30, 23, tzinfo=self.timezone))

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

    async def test_notifies_all_admins_with_short_safe_news_traceback(self) -> None:
        bot = AsyncMock()
        try:
            raise ValueError("secret details")
        except ValueError as exception:
            traceback_text = _short_traceback(exception)
            with patch(
                "src.jobs.media_worker.ADMIN_USER_IDS",
                frozenset({42, 7}),
            ):
                await _notify_admins_about_news_failure(bot, exception)

        self.assertIn("Traceback", traceback_text)
        self.assertIn("ValueError", traceback_text)
        self.assertIn("details redacted", traceback_text)
        self.assertNotIn("secret details", traceback_text)
        self.assertEqual(
            [call.args[0] for call in bot.send_message.await_args_list],
            [7, 42],
        )
        self.assertTrue(
            all(
                call.args[1].startswith("Новости не отправлены.")
                for call in bot.send_message.await_args_list
            )
        )


class RedisJobLockTests(unittest.IsolatedAsyncioTestCase):
    async def test_stops_owner_when_lock_ownership_is_lost(self) -> None:
        redis = AsyncMock()
        redis.set.return_value = True
        redis.eval.return_value = 0

        with patch("src.jobs.media_worker.asyncio.sleep", new_callable=AsyncMock):
            with self.assertRaisesRegex(LockLostError, "ownership was lost"):
                async with RedisJobLock(redis, "test-lock", 30):
                    await yield_to_event_loop(0)
                    await yield_to_event_loop(0)

    async def test_stops_owner_when_renewal_fails(self) -> None:
        redis = AsyncMock()
        redis.set.return_value = True
        redis.eval.side_effect = ConnectionError("Redis is unavailable")

        with patch("src.jobs.media_worker.asyncio.sleep", new_callable=AsyncMock):
            with self.assertRaisesRegex(LockLostError, "Failed to renew"):
                async with RedisJobLock(redis, "test-lock", 30):
                    await yield_to_event_loop(0)
                    await yield_to_event_loop(0)


if __name__ == "__main__":
    unittest.main()
