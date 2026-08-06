"""Redis locks used to prevent concurrent worker jobs."""

from __future__ import annotations

import asyncio
import logging
import secrets

from redis.asyncio import Redis

logger = logging.getLogger(__name__)


class JobAlreadyRunningError(RuntimeError):
    pass


class LockLostError(RuntimeError):
    pass


class RedisJobLock:
    """Token-owned Redis lock with renewal and compare-and-delete release."""

    _release_script = """
    if redis.call('get', KEYS[1]) == ARGV[1] then
        return redis.call('del', KEYS[1])
    end
    return 0
    """
    _renew_script = """
    if redis.call('get', KEYS[1]) == ARGV[1] then
        return redis.call('expire', KEYS[1], ARGV[2])
    end
    return 0
    """

    def __init__(self, redis: Redis, key: str, ttl_seconds: int) -> None:
        self.redis = redis
        self.key = key
        self.ttl_seconds = ttl_seconds
        self.token = secrets.token_urlsafe(32)
        self._renewal: asyncio.Task[None] | None = None
        self._owner: asyncio.Task[object] | None = None
        self._renewal_failure: Exception | None = None

    async def __aenter__(self) -> RedisJobLock:
        acquired = await self.redis.set(
            self.key,
            self.token,
            ex=self.ttl_seconds,
            nx=True,
        )
        if not acquired:
            raise JobAlreadyRunningError(self.key)
        self._owner = asyncio.current_task()
        self._renewal = asyncio.create_task(self._renew(), name=f"renew:{self.key}")
        return self

    async def __aexit__(self, *exc_info: object) -> None:
        if self._renewal is not None:
            self._renewal.cancel()
            await asyncio.gather(self._renewal, return_exceptions=True)
        try:
            await self.redis.eval(self._release_script, 1, self.key, self.token)
        except Exception:
            if self._renewal_failure is None:
                raise
            logger.exception("Failed to release lost media refresh lock: %s", self.key)
        if self._renewal_failure is not None:
            raise self._renewal_failure

    async def _renew(self) -> None:
        delay = max(1, self.ttl_seconds // 3)
        while True:
            await asyncio.sleep(delay)
            try:
                renewed = await self.redis.eval(
                    self._renew_script,
                    1,
                    self.key,
                    self.token,
                    self.ttl_seconds,
                )
            except Exception:
                self._stop_owner(
                    LockLostError(f"Failed to renew Redis lock: {self.key}")
                )
                logger.exception("Failed to renew media refresh lock: %s", self.key)
                return
            if not renewed:
                self._stop_owner(
                    LockLostError(f"Redis lock ownership was lost: {self.key}")
                )
                logger.error("Media refresh lock ownership was lost: %s", self.key)
                return

    def _stop_owner(self, failure: Exception) -> None:
        self._renewal_failure = failure
        if self._owner is not None:
            self._owner.cancel()
