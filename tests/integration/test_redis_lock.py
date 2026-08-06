import asyncio
import os
import unittest

from redis.asyncio import Redis

from src.jobs.worker_lock import JobAlreadyRunningError, LockLostError, RedisJobLock


@unittest.skipUnless(os.getenv("REDIS_URL"), "REDIS_URL is required")
class RedisJobLockIntegrationTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self.redis = Redis.from_url(os.environ["REDIS_URL"], decode_responses=True)
        await self.redis.flushdb()

    async def asyncTearDown(self) -> None:
        await self.redis.flushdb()
        await self.redis.aclose()

    async def test_lock_is_exclusive_and_released_by_its_owner(self) -> None:
        first = RedisJobLock(self.redis, "test:exclusive", 3)
        async with first:
            with self.assertRaises(JobAlreadyRunningError):
                async with RedisJobLock(self.redis, "test:exclusive", 3):
                    pass
        self.assertIsNone(await self.redis.get("test:exclusive"))

    async def test_lock_is_renewed_before_ttl_expires(self) -> None:
        async with RedisJobLock(self.redis, "test:renew", 3):
            await asyncio.sleep(2.2)
            self.assertGreater(await self.redis.ttl("test:renew"), 0)

    async def test_lost_ownership_cancels_the_owner(self) -> None:
        async def hold_lock() -> None:
            async with RedisJobLock(self.redis, "test:lost", 3):
                await self.redis.set("test:lost", "another-owner", ex=10)
                await asyncio.sleep(5)

        with self.assertRaises(LockLostError):
            await hold_lock()
        self.assertEqual(await self.redis.get("test:lost"), "another-owner")
