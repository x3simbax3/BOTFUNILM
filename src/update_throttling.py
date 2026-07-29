"""Bounded per-user throttling for incoming Telegram updates."""

import asyncio
import time
from collections import OrderedDict, deque
from collections.abc import Awaitable, Callable
from typing import Any

from aiogram import BaseMiddleware
from aiogram.types import TelegramObject, User


class UserThrottleMiddleware(BaseMiddleware):
    """Drop updates when a user exceeds a bounded sliding-window rate limit."""

    def __init__(
        self,
        max_updates: int,
        period_seconds: float,
        max_users: int,
        *,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        if max_updates <= 0:
            raise ValueError("USER_THROTTLE_MAX_UPDATES must be positive")
        if period_seconds <= 0:
            raise ValueError("USER_THROTTLE_PERIOD_SECONDS must be positive")
        if max_users <= 0:
            raise ValueError("USER_THROTTLE_MAX_USERS must be positive")

        self.max_updates = max_updates
        self.period_seconds = period_seconds
        self.max_users = max_users
        self._clock = clock
        self._users: OrderedDict[int, deque[float]] = OrderedDict()
        self._lock = asyncio.Lock()

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        user = data.get("event_from_user")
        if not isinstance(user, User):
            return await handler(event, data)
        if await self._is_throttled(user.id):
            return None
        return await handler(event, data)

    async def _is_throttled(self, user_id: int) -> bool:
        now = self._clock()
        cutoff = now - self.period_seconds

        async with self._lock:
            timestamps = self._users.pop(user_id, deque())
            while timestamps and timestamps[0] <= cutoff:
                timestamps.popleft()

            throttled = len(timestamps) >= self.max_updates
            if not throttled:
                timestamps.append(now)

            self._users[user_id] = timestamps
            while len(self._users) > self.max_users:
                self._users.popitem(last=False)

        return throttled
