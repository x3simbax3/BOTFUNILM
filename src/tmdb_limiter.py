"""In-process concurrency and request-rate limits for the TMDB transport."""

from __future__ import annotations

import asyncio
import secrets
from collections import deque
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass

from redis.asyncio import Redis

from config.config import (
    REDIS_URL,
    TMDB_MAX_CONCURRENCY,
    TMDB_MAX_REQUESTS_PER_SECOND,
    TMDB_QUEUE_TIMEOUT_SECONDS,
)
from src.tmdb_models import TmdbRateLimitError


@dataclass(frozen=True)
class TmdbLimiterSettings:
    max_concurrency: int = TMDB_MAX_CONCURRENCY
    max_requests: int = TMDB_MAX_REQUESTS_PER_SECOND
    window_seconds: float = 1.0
    queue_timeout_seconds: float = TMDB_QUEUE_TIMEOUT_SECONDS


class TmdbRequestLimiter:
    """Queue TMDB calls behind concurrency, sliding-window and cooldown limits."""

    def __init__(self, settings: TmdbLimiterSettings | None = None) -> None:
        self.settings = settings or TmdbLimiterSettings()
        if (
            self.settings.max_concurrency <= 0
            or self.settings.max_requests <= 0
            or self.settings.window_seconds <= 0
            or self.settings.queue_timeout_seconds <= 0
        ):
            raise ValueError("TMDB limiter settings must be positive")

        self._semaphore = asyncio.Semaphore(self.settings.max_concurrency)
        self._rate_lock = asyncio.Lock()
        self._request_times: deque[float] = deque()
        self._cooldown_until = 0.0
        self._redis: Redis | None = None
        self._member_prefix = secrets.token_hex(16)
        self._member_sequence = 0

    @asynccontextmanager
    async def request(self) -> AsyncIterator[None]:
        """Wait for capacity and release the concurrency slot after the call."""
        try:
            await asyncio.wait_for(
                self._acquire(),
                timeout=self.settings.queue_timeout_seconds,
            )
        except asyncio.TimeoutError:
            raise TmdbRateLimitError from None
        try:
            yield
        finally:
            self._semaphore.release()

    async def penalize(self, delay_seconds: float) -> None:
        """Pause all new calls after TMDB responds with HTTP 429."""
        delay = max(0.0, delay_seconds)
        loop = asyncio.get_running_loop()
        async with self._rate_lock:
            self._cooldown_until = max(self._cooldown_until, loop.time() + delay)
        if REDIS_URL and delay > 0:
            redis = self._redis_client()
            await redis.set(
                "tmdb:rate-limit:cooldown",
                "1",
                px=max(1, round(delay * 1000)),
            )

    async def _acquire(self) -> None:
        await self._semaphore.acquire()
        try:
            await self._wait_for_rate_slot()
        except BaseException:
            self._semaphore.release()
            raise

    async def _wait_for_rate_slot(self) -> None:
        if REDIS_URL:
            await self._wait_for_distributed_rate_slot()
        loop = asyncio.get_running_loop()
        while True:
            async with self._rate_lock:
                now = loop.time()
                window_start = now - self.settings.window_seconds
                while self._request_times and self._request_times[0] <= window_start:
                    self._request_times.popleft()

                cooldown_wait = max(0.0, self._cooldown_until - now)
                if (
                    cooldown_wait == 0
                    and len(self._request_times) < self.settings.max_requests
                ):
                    self._request_times.append(now)
                    return

                rate_wait = 0.0
                if len(self._request_times) >= self.settings.max_requests:
                    rate_wait = max(
                        0.0,
                        self._request_times[0] + self.settings.window_seconds - now,
                    )
                wait_seconds = max(cooldown_wait, rate_wait, 0.001)

            await asyncio.sleep(wait_seconds)

    async def _wait_for_distributed_rate_slot(self) -> None:
        redis = self._redis_client()
        window_ms = max(1, round(self.settings.window_seconds * 1000))
        while True:
            self._member_sequence += 1
            member = f"{self._member_prefix}:{self._member_sequence}"
            wait_ms = int(
                await redis.eval(
                    _DISTRIBUTED_RATE_LIMIT_SCRIPT,
                    2,
                    "tmdb:rate-limit:requests",
                    "tmdb:rate-limit:cooldown",
                    window_ms,
                    self.settings.max_requests,
                    member,
                )
            )
            if wait_ms <= 0:
                return
            await asyncio.sleep(max(0.001, wait_ms / 1000))

    def _redis_client(self) -> Redis:
        if self._redis is None:
            self._redis = Redis.from_url(REDIS_URL, decode_responses=True)
        return self._redis

    async def close(self) -> None:
        if self._redis is not None:
            await self._redis.aclose()
            self._redis = None


_DISTRIBUTED_RATE_LIMIT_SCRIPT = """
local cooldown = redis.call('pttl', KEYS[2])
if cooldown > 0 then
    return cooldown
end
local redis_time = redis.call('time')
local now = redis_time[1] * 1000 + math.floor(redis_time[2] / 1000)
local window = tonumber(ARGV[1])
redis.call('zremrangebyscore', KEYS[1], '-inf', now - window)
local count = redis.call('zcard', KEYS[1])
if count < tonumber(ARGV[2]) then
    redis.call('zadd', KEYS[1], now, ARGV[3])
    redis.call('pexpire', KEYS[1], window)
    return 0
end
local oldest = redis.call('zrange', KEYS[1], 0, 0, 'withscores')
return math.max(1, tonumber(oldest[2]) + window - now)
"""


_limiter: TmdbRequestLimiter | None = None
_limiter_loop: asyncio.AbstractEventLoop | None = None


def get_tmdb_request_limiter() -> TmdbRequestLimiter:
    """Return one limiter for the current event loop."""
    global _limiter, _limiter_loop

    loop = asyncio.get_running_loop()
    if _limiter is None or _limiter_loop is not loop:
        _limiter = TmdbRequestLimiter()
        _limiter_loop = loop
    return _limiter


async def close_tmdb_request_limiter() -> None:
    global _limiter, _limiter_loop
    if _limiter is not None:
        await _limiter.close()
    _limiter = None
    _limiter_loop = None


__all__ = (
    "TmdbLimiterSettings",
    "TmdbRequestLimiter",
    "close_tmdb_request_limiter",
    "get_tmdb_request_limiter",
)
