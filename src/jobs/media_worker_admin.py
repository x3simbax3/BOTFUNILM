"""Admin queue and heartbeat handling for the media worker."""

from __future__ import annotations

import json
import logging
from datetime import datetime
from zoneinfo import ZoneInfo

from aiogram import Bot
from redis.asyncio import Redis

from config.config import THENEWSAPI_KEY
from src.admin_runtime import (
    ADMIN_JOB_QUEUE,
    ADMIN_JOBS,
    MEDIA_WORKER_HEARTBEAT,
    WORKER_HEARTBEAT_TTL_SECONDS,
)
from src.jobs.custom_broadcast import send_custom_broadcast
from src.jobs.media_worker_jobs import (
    news_result_text,
    run_news_locked_or_log,
    run_notifications_locked_or_log,
    run_refresh_locked_or_log,
    send_admin_job_result,
)

logger = logging.getLogger(__name__)


async def run_admin_job_listener(
    redis: Redis,
    bot: Bot,
    *,
    database_url: str | None = None,
) -> None:
    """Consume the fixed set of commands confirmed in the Telegram admin UI."""
    while True:
        await set_worker_heartbeat(redis, "idle")
        item = await redis.blpop(ADMIN_JOB_QUEUE, timeout=5)
        if item is None:
            continue
        job: str | None = None
        payload: dict[str, object] = {}
        try:
            payload = json.loads(item[1])
            job = payload.get("job")
            if job not in ADMIN_JOBS:
                raise ValueError("Unknown admin job")
            await set_worker_heartbeat(redis, "running", job)
            if job in {"daily", "weekly"}:
                await run_refresh_locked_or_log(job, redis, database_url=database_url)
            elif job == "notifications":
                await run_notifications_locked_or_log(redis, bot, database_url=database_url)
            elif job == "news":
                if not THENEWSAPI_KEY:
                    raise RuntimeError("THENEWSAPI_KEY is required")
                stats = await run_news_locked_or_log(redis, bot, database_url=database_url)
                await send_admin_job_result(
                    bot,
                    payload.get("requested_by"),
                    news_result_text(stats),
                )
            else:
                text = payload.get("text")
                photo_file_id = payload.get("photo_file_id")
                if not isinstance(text, str) or (
                    photo_file_id is not None and not isinstance(photo_file_id, str)
                ):
                    raise ValueError("Invalid custom broadcast payload")
                stats = await send_custom_broadcast(
                    bot,
                    text,
                    photo_file_id=photo_file_id,
                    database_url=database_url,
                )
                await send_admin_job_result(
                    bot,
                    payload.get("requested_by"),
                    "Рассылка завершена: "
                    f"отправлено {stats.sent} из {stats.selected}, "
                    f"ошибок {stats.failed}.",
                )
        except Exception:
            logger.exception("Admin worker job failed")
            await set_worker_heartbeat(redis, "failed", job)
            await send_admin_job_result(
                bot,
                payload.get("requested_by"),
                "Задача не выполнена. Проверьте состояние воркера в статистике.",
            )


async def set_worker_heartbeat(
    redis: Redis, state: str, job: str | None = None
) -> None:
    await redis.set(
        MEDIA_WORKER_HEARTBEAT,
        json.dumps(
            {
                "state": state,
                "job": job,
                "updated_at": datetime.now(ZoneInfo("UTC")).isoformat(),
            }
        ),
        ex=WORKER_HEARTBEAT_TTL_SECONDS,
    )
