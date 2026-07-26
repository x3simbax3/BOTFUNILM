import unittest
from unittest.mock import patch

from aiogram.fsm.storage.memory import MemoryStorage, SimpleEventIsolation
from aiogram.fsm.storage.redis import RedisEventIsolation, RedisStorage

from src import bot


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


if __name__ == "__main__":
    unittest.main()
