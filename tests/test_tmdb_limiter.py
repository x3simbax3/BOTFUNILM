import asyncio
import unittest

from src.tmdb_limiter import TmdbLimiterSettings, TmdbRequestLimiter
from src.tmdb_models import TmdbRateLimitError


class TmdbRequestLimiterTests(unittest.IsolatedAsyncioTestCase):
    async def test_limits_concurrent_requests(self) -> None:
        limiter = TmdbRequestLimiter(
            TmdbLimiterSettings(
                max_concurrency=2,
                max_requests=100,
                queue_timeout_seconds=1,
            )
        )
        active = 0
        maximum_active = 0

        async def request() -> None:
            nonlocal active, maximum_active
            async with limiter.request():
                active += 1
                maximum_active = max(maximum_active, active)
                await asyncio.sleep(0.02)
                active -= 1

        await asyncio.gather(*(request() for _ in range(6)))

        self.assertEqual(maximum_active, 2)

    async def test_queues_requests_above_window_budget(self) -> None:
        limiter = TmdbRequestLimiter(
            TmdbLimiterSettings(
                max_concurrency=3,
                max_requests=2,
                window_seconds=0.05,
                queue_timeout_seconds=1,
            )
        )
        started = asyncio.get_running_loop().time()

        for _ in range(3):
            async with limiter.request():
                pass

        elapsed = asyncio.get_running_loop().time() - started
        self.assertGreaterEqual(elapsed, 0.04)

    async def test_rejects_request_when_queue_wait_expires(self) -> None:
        limiter = TmdbRequestLimiter(
            TmdbLimiterSettings(
                max_concurrency=1,
                max_requests=100,
                queue_timeout_seconds=0.01,
            )
        )

        async def blocked_request() -> None:
            async with limiter.request():
                pass

        async with limiter.request():
            with self.assertRaises(TmdbRateLimitError):
                await blocked_request()

    async def test_penalty_pauses_new_requests(self) -> None:
        limiter = TmdbRequestLimiter(
            TmdbLimiterSettings(
                max_concurrency=1,
                max_requests=100,
                queue_timeout_seconds=1,
            )
        )
        await limiter.penalize(0.05)
        started = asyncio.get_running_loop().time()

        async with limiter.request():
            pass

        elapsed = asyncio.get_running_loop().time() - started
        self.assertGreaterEqual(elapsed, 0.04)


if __name__ == "__main__":
    unittest.main()
