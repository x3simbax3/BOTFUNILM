"""Persist coarse user activity for admin statistics."""

import logging
from collections.abc import Awaitable, Callable
from typing import Any

import aiosqlite
from aiogram import BaseMiddleware
from aiogram.types import TelegramObject, User

from src.database.bot_users import touch_bot_user
from src.database.user_activity import record_user_event

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
                await touch_bot_user(
                    user.id,
                    username=user.username,
                    display_name=user.full_name,
                )
            except aiosqlite.Error:
                logger.exception("Failed to update user activity: user_id=%s", user.id)
        return await handler(event, data)


async def track_user_event(user_id: int, event_type: str) -> None:
    """Record analytics without allowing it to break a user action."""
    try:
        await record_user_event(user_id, event_type)
    except (aiosqlite.Error, ValueError):
        logger.exception(
            "Failed to record user event: user_id=%s event_type=%s",
            user_id,
            event_type,
        )


__all__ = ("UserActivityMiddleware", "track_user_event")
