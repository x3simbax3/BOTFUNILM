import unittest
from unittest.mock import AsyncMock, patch

import aiosqlite
from aiogram.types import Update, User

from src import user_activity


class UserActivityMiddlewareTests(unittest.IsolatedAsyncioTestCase):
    async def test_touches_user_before_handler(self) -> None:
        middleware = user_activity.UserActivityMiddleware()
        handler = AsyncMock(return_value="handled")
        event = Update(update_id=1)
        user = User(id=123, is_bot=False, first_name="Test")

        with patch.object(user_activity, "touch_bot_user", new=AsyncMock()) as touch:
            result = await middleware(handler, event, {"event_from_user": user})

        self.assertEqual(result, "handled")
        touch.assert_awaited_once_with(123)
        handler.assert_awaited_once()

    async def test_database_error_does_not_drop_update(self) -> None:
        middleware = user_activity.UserActivityMiddleware()
        handler = AsyncMock(return_value="handled")
        event = Update(update_id=1)
        user = User(id=123, is_bot=False, first_name="Test")

        with patch.object(
            user_activity,
            "touch_bot_user",
            new=AsyncMock(side_effect=aiosqlite.OperationalError("unavailable")),
        ):
            result = await middleware(handler, event, {"event_from_user": user})

        self.assertEqual(result, "handled")

    async def test_bypasses_update_without_user(self) -> None:
        middleware = user_activity.UserActivityMiddleware()
        handler = AsyncMock(return_value="handled")
        event = Update(update_id=1)

        with patch.object(user_activity, "touch_bot_user", new=AsyncMock()) as touch:
            result = await middleware(handler, event, {})

        self.assertEqual(result, "handled")
        touch.assert_not_awaited()


if __name__ == "__main__":
    unittest.main()
