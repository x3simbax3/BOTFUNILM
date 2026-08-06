"""Small Redis protocol shared by the bot and the media worker."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Literal

from redis.asyncio import Redis

from config.config import REDIS_URL

ADMIN_JOB_QUEUE = "botfunilm:admin:jobs"
MEDIA_WORKER_HEARTBEAT = "botfunilm:media-worker:heartbeat"
WORKER_HEARTBEAT_TTL_SECONDS = 20
AdminJob = Literal["daily", "weekly", "notifications", "news", "broadcast"]
ADMIN_JOBS: frozenset[str] = frozenset(
    {"daily", "weekly", "notifications", "news", "broadcast"}
)


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


async def enqueue_custom_broadcast(
    requested_by: int,
    text: str,
    *,
    photo_file_id: str | None = None,
) -> None:
    if not text or len(text) > (1024 if photo_file_id else 4096):
        raise ValueError("Invalid broadcast text length")
    redis = Redis.from_url(REDIS_URL, decode_responses=True)
    try:
        await redis.rpush(
            ADMIN_JOB_QUEUE,
            json.dumps(
                {
                    "job": "broadcast",
                    "requested_by": requested_by,
                    "requested_at": datetime.now(timezone.utc).isoformat(),
                    "text": text,
                    "photo_file_id": photo_file_id,
                },
                ensure_ascii=False,
            ),
        )
    finally:
        await redis.aclose()


__all__ = (
    "ADMIN_JOB_QUEUE",
    "ADMIN_JOBS",
    "MEDIA_WORKER_HEARTBEAT",
    "WORKER_HEARTBEAT_TTL_SECONDS",
    "AdminJob",
    "enqueue_admin_job",
    "enqueue_custom_broadcast",
)
