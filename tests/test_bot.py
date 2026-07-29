import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from aiogram.fsm.storage.memory import MemoryStorage, SimpleEventIsolation
from aiogram.fsm.storage.redis import RedisEventIsolation, RedisStorage

from src import bot
from src.update_throttling import UserThrottleMiddleware


class DispatcherStorageTests(unittest.IsolatedAsyncioTestCase):
    async def test_uses_isolated_memory_storage_without_redis_url(self) -> None:
        with patch.object(bot, "REDIS_URL", ""):
            dispatcher = bot.create_dispatcher()

        self.assertIsInstance(dispatcher.fsm.storage, MemoryStorage)
        self.assertIsInstance(
            dispatcher.fsm.events_isolation,
            SimpleEventIsolation,
        )
        await dispatcher.fsm.close()

    async def test_throttles_before_accessing_fsm_storage(self) -> None:
        with patch.object(bot, "REDIS_URL", ""):
            dispatcher = bot.create_dispatcher()

        middlewares = dispatcher.update.outer_middleware._middlewares
        throttle_index = next(
            index
            for index, middleware in enumerate(middlewares)
            if isinstance(middleware, UserThrottleMiddleware)
        )
        self.assertEqual(middlewares[throttle_index + 1], dispatcher.fsm)
        await dispatcher.fsm.close()

    async def test_uses_redis_storage_with_ttl_and_event_isolation(self) -> None:
        with (
            patch.object(bot, "REDIS_URL", "redis://localhost:6379/0"),
            patch.object(bot, "FSM_TTL_SECONDS", 3600),
        ):
            dispatcher = bot.create_dispatcher()

        storage = dispatcher.fsm.storage
        self.assertIsInstance(storage, RedisStorage)
        self.assertEqual(storage.state_ttl, 3600)
        self.assertEqual(storage.data_ttl, 3600)
        self.assertIsInstance(
            dispatcher.fsm.events_isolation,
            RedisEventIsolation,
        )
        await dispatcher.fsm.close()

    async def test_rejects_non_positive_fsm_ttl(self) -> None:
        with (
            patch.object(bot, "REDIS_URL", "redis://localhost:6379/0"),
            patch.object(bot, "FSM_TTL_SECONDS", 0),
        ):
            with self.assertRaisesRegex(ValueError, "FSM_TTL_SECONDS"):
                bot.create_dispatcher()


class PollingTests(unittest.IsolatedAsyncioTestCase):
    async def test_limits_concurrent_update_tasks(self) -> None:
        telegram_bot = MagicMock()
        telegram_bot.me = AsyncMock()
        telegram_bot.session.close = AsyncMock()
        dispatcher = MagicMock()
        dispatcher.start_polling = AsyncMock()

        with (
            patch.object(bot, "BOT_TOKEN", "123:test"),
            patch.object(bot, "UPDATE_TASKS_CONCURRENCY_LIMIT", 7),
            patch.object(bot, "Bot", return_value=telegram_bot),
            patch.object(bot, "create_dispatcher", return_value=dispatcher),
            patch.object(bot, "close_http_session", new=AsyncMock()),
            patch.object(bot, "verify_private_files"),
            patch.object(bot, "backfill_media_search_index", new=AsyncMock()),
        ):
            await bot.main()

        dispatcher.start_polling.assert_awaited_once_with(
            telegram_bot,
            tasks_concurrency_limit=7,
        )

    async def test_closes_sessions_when_bot_identity_request_fails(self) -> None:
        telegram_bot = MagicMock()
        telegram_bot.me = AsyncMock(side_effect=RuntimeError("Telegram unavailable"))
        telegram_bot.session.close = AsyncMock()

        with (
            patch.object(bot, "BOT_TOKEN", "123:test"),
            patch.object(bot, "Bot", return_value=telegram_bot),
            patch.object(bot, "close_http_session", new=AsyncMock()) as close_http,
            patch.object(bot, "verify_private_files"),
            patch.object(bot, "backfill_media_search_index", new=AsyncMock()),
            self.assertRaisesRegex(RuntimeError, "Telegram unavailable"),
        ):
            await bot.main()

        close_http.assert_awaited_once()
        telegram_bot.session.close.assert_awaited_once()


if __name__ == "__main__":
    unittest.main()
