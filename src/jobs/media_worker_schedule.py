"""Schedules for media refreshes, notifications, and news broadcasts."""

from __future__ import annotations

import asyncio
import logging
import secrets
from collections.abc import Sequence
from datetime import date, datetime, timedelta
from datetime import time as datetime_time
from typing import Literal
from zoneinfo import ZoneInfo

from aiogram import Bot
from redis.asyncio import Redis

from config.config import THENEWSAPI_KEY
from src.database.admin import is_feature_enabled
from src.jobs.media_refresh import has_due_media
from src.jobs.media_worker_jobs import (
    run_news_locked_or_log,
    run_notifications_locked_or_log,
    run_refresh_locked_or_log,
)
from src.jobs.media_worker_settings import worker_timezone

logger = logging.getLogger(__name__)
REFRESH_HOUR = 2
NOTIFICATION_HOUR = 12
NEWS_HOURS = tuple(range(10, 23, 2))
NEWS_JITTER_SECONDS = 5 * 60
ScheduledJob = Literal["daily", "weekly", "notifications"]


def next_scheduled_run(
    now: datetime, timezone: ZoneInfo
) -> tuple[datetime, ScheduledJob]:
    local_now = now.astimezone(timezone)
    refresh_target = datetime.combine(
        local_now.date(),
        datetime_time(hour=REFRESH_HOUR),
        tzinfo=timezone,
    )
    notification_target = datetime.combine(
        local_now.date(),
        datetime_time(hour=NOTIFICATION_HOUR),
        tzinfo=timezone,
    )
    candidates: list[tuple[datetime, ScheduledJob]] = []
    if refresh_target > local_now:
        candidates.append(
            (
                refresh_target,
                "weekly" if refresh_target.weekday() == 0 else "daily",
            )
        )
    if notification_target > local_now:
        candidates.append((notification_target, "notifications"))
    if not candidates:
        refresh_target += timedelta(days=1)
        candidates.append(
            (
                refresh_target,
                "weekly" if refresh_target.weekday() == 0 else "daily",
            )
        )
    return min(candidates, key=lambda candidate: candidate[0])


async def run_worker(
    redis: Redis,
    bot: Bot,
    *,
    database_url: str | None = None,
) -> None:
    timezone = worker_timezone()
    refresh_enabled = await is_feature_enabled(
        "media_refresh", database_url=database_url
    )
    if refresh_enabled and await has_due_media("weekly", database_url=database_url):
        await run_refresh_locked_or_log("weekly", redis, database_url=database_url)
    if refresh_enabled and await has_due_media("daily", database_url=database_url):
        await run_refresh_locked_or_log("daily", redis, database_url=database_url)
    if (
        await is_feature_enabled("notifications", database_url=database_url)
        and datetime.now(timezone).hour >= NOTIFICATION_HOUR
    ):
        await run_notifications_locked_or_log(redis, bot, database_url=database_url)

    while True:
        target, job = next_scheduled_run(datetime.now(timezone), timezone)
        delay = max(0.0, (target - datetime.now(timezone)).total_seconds())
        logger.info(
            "Next media worker job scheduled: job=%s at=%s sleep_seconds=%s",
            job,
            target.isoformat(),
            round(delay),
        )
        await asyncio.sleep(delay)
        if job == "notifications" and await is_feature_enabled(
            "notifications", database_url=database_url
        ):
            await run_notifications_locked_or_log(redis, bot, database_url=database_url)
        elif job != "notifications" and await is_feature_enabled(
            "media_refresh", database_url=database_url
        ):
            await run_refresh_locked_or_log(job, redis, database_url=database_url)
            if job == "weekly" and await has_due_media(
                "daily", database_url=database_url
            ):
                await run_refresh_locked_or_log(
                    "daily", redis, database_url=database_url
                )
            if (
                await is_feature_enabled("notifications", database_url=database_url)
                and datetime.now(timezone).hour >= NOTIFICATION_HOUR
            ):
                await run_notifications_locked_or_log(
                    redis, bot, database_url=database_url
                )


def daily_news_targets(
    day: date,
    timezone: ZoneInfo,
    *,
    offsets: Sequence[int] | None = None,
) -> tuple[datetime, ...]:
    if offsets is None:
        offsets = (
            secrets.randbelow(NEWS_JITTER_SECONDS + 1),
            *(
                secrets.randbelow(2 * NEWS_JITTER_SECONDS + 1) - NEWS_JITTER_SECONDS
                for _ in NEWS_HOURS[1:]
            ),
        )
    if len(offsets) != len(NEWS_HOURS):
        raise ValueError("One news jitter offset is required for every news hour")

    targets = []
    for hour, offset in zip(NEWS_HOURS, offsets, strict=True):
        if not -NEWS_JITTER_SECONDS <= offset <= NEWS_JITTER_SECONDS:
            raise ValueError("News jitter offset is outside the allowed range")
        nominal = datetime.combine(day, datetime_time(hour=hour), tzinfo=timezone)
        target = nominal + timedelta(seconds=offset)
        if hour == NEWS_HOURS[0] and target < nominal:
            target = nominal
        targets.append(target)
    return tuple(targets)


async def run_news_scheduler(
    redis: Redis,
    bot: Bot,
    *,
    database_url: str | None = None,
) -> None:
    if not THENEWSAPI_KEY:
        raise RuntimeError("THENEWSAPI_KEY is required for news broadcasts")
    timezone = worker_timezone()
    scheduled_day: date | None = None
    targets: tuple[datetime, ...] = ()

    while True:
        now = datetime.now(timezone)
        if scheduled_day != now.date():
            scheduled_day = now.date()
            targets = daily_news_targets(scheduled_day, timezone)
        target = next((item for item in targets if item > now), None)
        if target is None:
            scheduled_day = now.date() + timedelta(days=1)
            targets = daily_news_targets(scheduled_day, timezone)
            target = targets[0]

        delay = max(0.0, (target - datetime.now(timezone)).total_seconds())
        logger.info(
            "Next news broadcast scheduled: at=%s sleep_seconds=%s",
            target.isoformat(),
            round(delay),
        )
        await asyncio.sleep(delay)
        if await is_feature_enabled("news", database_url=database_url):
            await run_news_locked_or_log(redis, bot, database_url=database_url)
