"""Persistent scheduler and CLI for TMDB-backed series catalogue refreshes."""

from __future__ import annotations

import argparse
import asyncio
import logging
import os
import secrets
import time
from contextlib import AsyncExitStack
from dataclasses import dataclass
from datetime import datetime, timedelta
from datetime import time as datetime_time
from typing import Literal
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from aiogram import Bot
from redis.asyncio import Redis

from config.config import (
    BOT_TOKEN,
    DATABASE_URL,
    DEBUG,
    MEDIA_REFRESH_BATCH_SIZE,
    MEDIA_REFRESH_CONCURRENCY,
    MEDIA_REFRESH_LOCK_TTL_SECONDS,
    MEDIA_REFRESH_RETRIES,
    MEDIA_WORKER_TIMEZONE,
    REDIS_URL,
)
from src.database.connection import connect_database
from src.http_client import close_http_session
from src.jobs.media_refresh import (
    MediaChange,
    MediaRefreshCandidate,
    RefreshMode,
    get_media_candidate,
    get_tmdb_candidates,
    has_due_media,
    mark_media_refresh_error,
    preview_media_refresh,
    save_media_refresh,
    select_due_media_batch,
)
from src.jobs.series_notifications import send_release_notifications
from src.logging_config import configure_logging
from src.tmdb_client import get_tmdb_request_count, reset_tmdb_request_count
from src.tmdb_limiter import close_tmdb_request_limiter
from src.tmdb_models import (
    TmdbAuthenticationError,
    TmdbError,
    TmdbNotFoundError,
    TmdbRateLimitError,
    TmdbUnavailableError,
)
from src.tmdb_series import fetch_tv_details

logger = logging.getLogger(__name__)
LOCK_PREFIX = "media-refresh"
REFRESH_HOUR = 2
NOTIFICATION_HOUR = 12
ScheduledJob = Literal["daily", "weekly", "notifications"]


@dataclass
class RefreshStats:
    selected: int = 0
    updated: int = 0
    unchanged: int = 0
    failed: int = 0


@dataclass(frozen=True)
class TitleResult:
    status: str
    changes: tuple[MediaChange, ...] = ()
    authentication_failed: bool = False


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

    async def __aenter__(self) -> RedisJobLock:
        acquired = await self.redis.set(
            self.key,
            self.token,
            ex=self.ttl_seconds,
            nx=True,
        )
        if not acquired:
            raise JobAlreadyRunningError(self.key)
        self._renewal = asyncio.create_task(self._renew(), name=f"renew:{self.key}")
        return self

    async def __aexit__(self, *exc_info: object) -> None:
        if self._renewal is not None:
            self._renewal.cancel()
            await asyncio.gather(self._renewal, return_exceptions=True)
        await self.redis.eval(self._release_script, 1, self.key, self.token)

    async def _renew(self) -> None:
        delay = max(1, self.ttl_seconds // 3)
        while True:
            await asyncio.sleep(delay)
            renewed = await self.redis.eval(
                self._renew_script,
                1,
                self.key,
                self.token,
                self.ttl_seconds,
            )
            if not renewed:
                logger.error("Media refresh lock ownership was lost: %s", self.key)
                return


class JobAlreadyRunningError(RuntimeError):
    pass


async def run_refresh_job(
    mode: RefreshMode,
    redis: Redis,
    *,
    database_url: str | None = None,
) -> RefreshStats:
    """Refresh every due title for one schedule while holding Redis locks."""
    _validate_settings()
    started = time.monotonic()
    reset_tmdb_request_count()
    stats = RefreshStats()
    authentication_failed = False
    async with AsyncExitStack() as stack:
        await stack.enter_async_context(
            RedisJobLock(redis, f"{LOCK_PREFIX}:global", MEDIA_REFRESH_LOCK_TTL_SECONDS)
        )
        await stack.enter_async_context(
            RedisJobLock(redis, f"{LOCK_PREFIX}:{mode}", MEDIA_REFRESH_LOCK_TTL_SECONDS)
        )
        after_id = 0
        while not authentication_failed:
            batch = await select_due_media_batch(
                mode,
                after_id=after_id,
                limit=MEDIA_REFRESH_BATCH_SIZE,
                database_url=database_url,
            )
            if not batch:
                break
            after_id = batch[-1].media_id
            stats.selected += len(batch)
            for offset in range(0, len(batch), MEDIA_REFRESH_CONCURRENCY):
                chunk = batch[offset : offset + MEDIA_REFRESH_CONCURRENCY]
                results = await asyncio.gather(
                    *(
                        _refresh_candidate(candidate, mode, database_url=database_url)
                        for candidate in chunk
                    )
                )
                for result in results:
                    if result.status == "updated":
                        stats.updated += 1
                    elif result.status == "unchanged":
                        stats.unchanged += 1
                    else:
                        stats.failed += 1
                    authentication_failed |= result.authentication_failed
                if authentication_failed:
                    break

    duration = round(time.monotonic() - started)
    if authentication_failed:
        logger.error(
            "%s media refresh aborted: TMDB authentication failed; "
            "selected=%s updated=%s unchanged=%s failed=%s requests=%s duration=%ss",
            mode.capitalize(),
            stats.selected,
            stats.updated,
            stats.unchanged,
            stats.failed,
            get_tmdb_request_count(),
            duration,
        )
        raise TmdbAuthenticationError
    logger.info(
        "%s media refresh completed: selected=%s updated=%s unchanged=%s "
        "failed=%s requests=%s duration=%ss",
        mode.capitalize(),
        stats.selected,
        stats.updated,
        stats.unchanged,
        stats.failed,
        get_tmdb_request_count(),
        duration,
    )
    return stats


async def run_manual_refresh(
    candidates: list[MediaRefreshCandidate],
    redis: Redis,
    *,
    dry_run: bool,
    database_url: str | None = None,
) -> list[TitleResult]:
    if not candidates:
        raise ValueError("Series was not found in the catalogue")
    reset_tmdb_request_count()
    async with RedisJobLock(
        redis,
        f"{LOCK_PREFIX}:global",
        MEDIA_REFRESH_LOCK_TTL_SECONDS,
    ):
        results = []
        for candidate in candidates:
            result = await _refresh_candidate(
                candidate,
                "weekly",
                dry_run=dry_run,
                database_url=database_url,
            )
            results.append(result)
            _print_manual_result(candidate, result, dry_run=dry_run)
            if result.authentication_failed:
                raise TmdbAuthenticationError
        return results


async def _refresh_candidate(
    candidate: MediaRefreshCandidate,
    mode: RefreshMode,
    *,
    dry_run: bool = False,
    database_url: str | None = None,
) -> TitleResult:
    for attempt in range(MEDIA_REFRESH_RETRIES):
        try:
            snapshot = await fetch_tv_details(
                candidate.tmdb_id,
                include_episode_availability=True,
            )
            if dry_run:
                changes = await preview_media_refresh(
                    candidate.media_id,
                    snapshot,
                    database_url=database_url,
                )
            else:
                changes = await save_media_refresh(
                    candidate.media_id,
                    snapshot,
                    mode,
                    database_url=database_url,
                )
            return TitleResult("updated" if changes else "unchanged", tuple(changes))
        except TmdbAuthenticationError:
            logger.error(
                "TMDB authentication failed while refreshing media_id=%s",
                candidate.media_id,
            )
            return TitleResult("failed", authentication_failed=True)
        except TmdbNotFoundError:
            logger.error(
                "TMDB series not found: media_id=%s tmdb_id=%s",
                candidate.media_id,
                candidate.tmdb_id,
            )
            if not dry_run:
                await mark_media_refresh_error(
                    candidate.media_id,
                    mode,
                    "not_found",
                    database_url=database_url,
                )
            return TitleResult("failed")
        except (TmdbRateLimitError, TmdbUnavailableError) as exc:
            if attempt + 1 < MEDIA_REFRESH_RETRIES:
                await asyncio.sleep(2**attempt)
                continue
            error = type(exc).__name__
        except TmdbError as exc:
            error = f"{type(exc).__name__}: {exc}"
        except Exception:
            logger.exception(
                "Unexpected media refresh failure media_id=%s", candidate.media_id
            )
            error = "unexpected_error"

        logger.error(
            "Media refresh failed: media_id=%s tmdb_id=%s error=%s",
            candidate.media_id,
            candidate.tmdb_id,
            error,
        )
        if not dry_run:
            await mark_media_refresh_error(
                candidate.media_id,
                mode,
                error,
                database_url=database_url,
            )
        return TitleResult("failed")
    raise AssertionError("unreachable")


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
    timezone = _worker_timezone()
    if await has_due_media("weekly", database_url=database_url):
        await _run_locked_or_log("weekly", redis, database_url=database_url)
    elif await has_due_media("daily", database_url=database_url):
        await _run_locked_or_log("daily", redis, database_url=database_url)
    if datetime.now(timezone).hour >= NOTIFICATION_HOUR:
        await _run_notifications_locked_or_log(
            redis,
            bot,
            database_url=database_url,
        )

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
        if job == "notifications":
            await _run_notifications_locked_or_log(
                redis,
                bot,
                database_url=database_url,
            )
        else:
            await _run_locked_or_log(job, redis, database_url=database_url)
            if datetime.now(timezone).hour >= NOTIFICATION_HOUR:
                await _run_notifications_locked_or_log(
                    redis,
                    bot,
                    database_url=database_url,
                )


async def _run_notifications_locked_or_log(
    redis: Redis,
    bot: Bot,
    *,
    database_url: str | None,
) -> None:
    try:
        async with RedisJobLock(
            redis,
            "series-notifications",
            MEDIA_REFRESH_LOCK_TTL_SECONDS,
        ):
            await send_release_notifications(bot, database_url=database_url)
    except JobAlreadyRunningError:
        logger.warning("Series notifications skipped because lock is held")


async def _run_locked_or_log(
    mode: RefreshMode,
    redis: Redis,
    *,
    database_url: str | None,
) -> None:
    try:
        await run_refresh_job(mode, redis, database_url=database_url)
    except JobAlreadyRunningError as exc:
        logger.warning("Media refresh skipped because lock is held: %s", exc)
    except TmdbAuthenticationError:
        logger.error(
            "Scheduled media refresh stopped because TMDB credentials are invalid"
        )


def _print_manual_result(
    candidate: MediaRefreshCandidate,
    result: TitleResult,
    *,
    dry_run: bool,
) -> None:
    print(f"Media {candidate.media_id}: {result.status}")
    for change in result.changes:
        print(f"{_field_label(change.field)}: {change.before} -> {change.after}")
    print(f"database write: {'skipped' if dry_run else 'committed'}")


def _field_label(field: str) -> str:
    labels = {
        "available_episode_count": "available episodes",
        "next_episode_number": "next episode number",
        "next_episode_air_date": "next air date",
        "description": "description",
    }
    return labels.get(field, field.replace("_", " "))


def _validate_settings() -> None:
    values = {
        "MEDIA_REFRESH_BATCH_SIZE": MEDIA_REFRESH_BATCH_SIZE,
        "MEDIA_REFRESH_CONCURRENCY": MEDIA_REFRESH_CONCURRENCY,
        "MEDIA_REFRESH_LOCK_TTL_SECONDS": MEDIA_REFRESH_LOCK_TTL_SECONDS,
        "MEDIA_REFRESH_RETRIES": MEDIA_REFRESH_RETRIES,
    }
    for name, value in values.items():
        if value <= 0:
            raise ValueError(f"{name} must be positive")
    if not REDIS_URL:
        raise RuntimeError("REDIS_URL is required for media refresh jobs")
    if not BOT_TOKEN:
        raise RuntimeError("BOT_TOKEN is required for series notifications")


def _worker_timezone() -> ZoneInfo:
    try:
        return ZoneInfo(MEDIA_WORKER_TIMEZONE)
    except ZoneInfoNotFoundError as exc:
        raise ValueError(
            f"Unknown media worker timezone: {MEDIA_WORKER_TIMEZONE}"
        ) from exc


async def _verify_dependencies(redis: Redis, database_url: str | None) -> None:
    connection = await connect_database(database_url)
    await connection.close()
    if not await redis.ping():
        raise RuntimeError("Redis ping failed")


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command")
    run = subparsers.add_parser("run", help="run one refresh immediately")
    run.add_argument("mode", choices=("daily", "weekly"))
    single = subparsers.add_parser("single", help="refresh one catalogue row")
    selector = single.add_mutually_exclusive_group(required=True)
    selector.add_argument("--id", type=int, dest="media_id")
    selector.add_argument("--tmdb-id", type=int)
    single.add_argument("--dry-run", action="store_true")
    subparsers.add_parser("notify", help="send pending series notifications now")
    return parser


async def async_main(arguments: list[str] | None = None) -> None:
    _validate_settings()
    parser = _parser()
    options = parser.parse_args(arguments)
    redis = Redis.from_url(REDIS_URL, decode_responses=True)
    try:
        await _verify_dependencies(redis, DATABASE_URL)
        async with Bot(BOT_TOKEN) as bot:
            if options.command == "run":
                await run_refresh_job(options.mode, redis)
            elif options.command == "single":
                if options.media_id is not None:
                    candidate = await get_media_candidate(options.media_id)
                    candidates = [candidate] if candidate is not None else []
                else:
                    candidates = await get_tmdb_candidates(options.tmdb_id)
                await run_manual_refresh(candidates, redis, dry_run=options.dry_run)
            elif options.command == "notify":
                await _run_notifications_locked_or_log(
                    redis,
                    bot,
                    database_url=DATABASE_URL,
                )
            else:
                logger.info(
                    "Media worker startup completed timezone=%s", MEDIA_WORKER_TIMEZONE
                )
                await run_worker(redis, bot)
    finally:
        await close_http_session()
        try:
            await close_tmdb_request_limiter()
        finally:
            await redis.aclose()


def main() -> None:
    configure_logging(debug=DEBUG)
    os.umask(0o077)
    asyncio.run(async_main())


if __name__ == "__main__":
    main()
