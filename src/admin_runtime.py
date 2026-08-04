"""Small Redis protocol shared by the bot and the media worker."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Literal

from redis.asyncio import Redis
from redis.exceptions import RedisError

from config.config import REDIS_URL

ADMIN_JOB_QUEUE = "botfunilm:admin:jobs"
MEDIA_WORKER_HEARTBEAT = "botfunilm:media-worker:heartbeat"
WORKER_HEARTBEAT_TTL_SECONDS = 20
AdminJob = Literal["daily", "weekly", "notifications", "news"]
ADMIN_JOBS: frozenset[str] = frozenset({"daily", "weekly", "notifications", "news"})


@dataclass(frozen=True)
class RuntimeStatus:
    redis_available: bool
    queued_jobs: int
    worker_state: str | None
    worker_job: str | None
    worker_updated_at: str | None


async def enqueue_admin_job(job: AdminJob, requested_by: int) -> None:
    if job not in ADMIN_JOBS:
        raise ValueError("Unknown admin job")
    redis = Redis.from_url(REDIS_URL, decode_responses=True)
    try:
        await redis.rpush(
            ADMIN_JOB_QUEUE,
            json.dumps(
                {
                    "job": job,
                    "requested_by": requested_by,
                    "requested_at": datetime.now(timezone.utc).isoformat(),
                }
            ),
        )
    finally:
        await redis.aclose()


async def get_runtime_status() -> RuntimeStatus:
    if not REDIS_URL:
        return RuntimeStatus(False, 0, None, None, None)
    redis = Redis.from_url(REDIS_URL, decode_responses=True)
    try:
        try:
            if not await redis.ping():
                return RuntimeStatus(False, 0, None, None, None)
            queued_jobs = int(await redis.llen(ADMIN_JOB_QUEUE))
            raw_heartbeat = await redis.get(MEDIA_WORKER_HEARTBEAT)
        except RedisError:
            return RuntimeStatus(False, 0, None, None, None)
    finally:
        await redis.aclose()

    try:
        heartbeat = json.loads(raw_heartbeat) if raw_heartbeat else {}
    except (json.JSONDecodeError, TypeError):
        heartbeat = {}
    return RuntimeStatus(
        True,
        queued_jobs,
        heartbeat.get("state"),
        heartbeat.get("job"),
        heartbeat.get("updated_at"),
    )


__all__ = (
    "ADMIN_JOB_QUEUE",
    "ADMIN_JOBS",
    "MEDIA_WORKER_HEARTBEAT",
    "WORKER_HEARTBEAT_TTL_SECONDS",
    "AdminJob",
    "RuntimeStatus",
    "enqueue_admin_job",
    "get_runtime_status",
)
