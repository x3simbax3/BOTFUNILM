import unittest
from unittest.mock import AsyncMock

from aiogram.types import Update, User

from src.update_throttling import UserThrottleMiddleware


class UserThrottleMiddlewareTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        self.now = 100.0
        self.middleware = UserThrottleMiddleware(
            max_updates=2,
            period_seconds=1.0,
            max_users=2,
            clock=lambda: self.now,
        )
        self.event = Update(update_id=1)
        self.user = User(id=123, is_bot=False, first_name="Test")

    async def test_drops_updates_over_user_limit(self) -> None:
        handler = AsyncMock(return_value="handled")
        data = {"event_from_user": self.user}

        self.assertEqual(await self.middleware(handler, self.event, data), "handled")
        self.assertEqual(await self.middleware(handler, self.event, data), "handled")
        self.assertIsNone(await self.middleware(handler, self.event, data))
        self.assertEqual(handler.await_count, 2)

    async def test_allows_user_again_after_window(self) -> None:
        handler = AsyncMock(return_value="handled")
        data = {"event_from_user": self.user}
        await self.middleware(handler, self.event, data)
        await self.middleware(handler, self.event, data)

        self.now += 1.0

        self.assertEqual(await self.middleware(handler, self.event, data), "handled")

    async def test_bounds_tracked_user_state(self) -> None:
        handler = AsyncMock()
        for user_id in range(3):
            user = User(id=user_id, is_bot=False, first_name="Test")
            await self.middleware(handler, self.event, {"event_from_user": user})

        self.assertEqual(list(self.middleware._users), [1, 2])

    async def test_bypasses_updates_without_user(self) -> None:
        handler = AsyncMock(return_value="handled")

        result = await self.middleware(handler, self.event, {})

        self.assertEqual(result, "handled")
        handler.assert_awaited_once_with(self.event, {})

    def test_rejects_invalid_limits(self) -> None:
        with self.assertRaisesRegex(ValueError, "MAX_UPDATES"):
            UserThrottleMiddleware(0, 1.0, 1)
        with self.assertRaisesRegex(ValueError, "PERIOD_SECONDS"):
            UserThrottleMiddleware(1, 0, 1)
        with self.assertRaisesRegex(ValueError, "MAX_USERS"):
            UserThrottleMiddleware(1, 1.0, 0)


if __name__ == "__main__":
    unittest.main()
