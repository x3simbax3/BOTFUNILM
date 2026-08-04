"""Persist coarse user activity for admin statistics."""

import logging
from collections.abc import Awaitable, Callable
from typing import Any

import aiosqlite
from aiogram import BaseMiddleware
from aiogram.types import TelegramObject, User

from src.database.bot_users import touch_bot_user

logger = logging.getLogger(__name__)


class UserActivityMiddleware(BaseMiddleware):
    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        user = data.get("event_from_user")
        if isinstance(user, User):
            try:
                await touch_bot_user(user.id)
            except aiosqlite.Error:
                logger.exception("Failed to update user activity: user_id=%s", user.id)
        return await handler(event, data)


__all__ = ("UserActivityMiddleware",)
