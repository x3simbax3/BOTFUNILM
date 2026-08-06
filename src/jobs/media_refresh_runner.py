"""Run scheduled and manual TMDB-backed media refreshes."""

from __future__ import annotations

import asyncio
import logging
import time
from contextlib import AsyncExitStack
from dataclasses import dataclass
from datetime import datetime

from redis.asyncio import Redis

from config.config import (
    MEDIA_REFRESH_BATCH_SIZE,
    MEDIA_REFRESH_CONCURRENCY,
    MEDIA_REFRESH_LOCK_TTL_SECONDS,
    MEDIA_REFRESH_RETRIES,
)
from src.jobs.media_refresh import (
    MediaChange,
    MediaRefreshCandidate,
    RefreshMode,
    mark_media_refresh_error,
    preview_media_refresh,
    save_media_refresh,
    save_movie_release_refresh,
    select_due_media_batch,
)
from src.jobs.media_worker_settings import validate_settings, worker_timezone
from src.jobs.worker_lock import RedisJobLock
from src.tmdb_client import get_tmdb_request_count, reset_tmdb_request_count
from src.tmdb_models import (
    TmdbAuthenticationError,
    TmdbError,
    TmdbNotFoundError,
    TmdbRateLimitError,
    TmdbUnavailableError,
)
from src.tmdb_movie import fetch_movie_details
from src.tmdb_series import fetch_tv_details

logger = logging.getLogger(__name__)
LOCK_PREFIX = "media-refresh"


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


async def run_refresh_job(
    mode: RefreshMode,
    redis: Redis,
    *,
    database_url: str | None = None,
) -> RefreshStats:
    """Refresh every due title for one schedule while holding Redis locks."""
    validate_settings()
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
            if candidate.content_format == "full_length":
                movie = await fetch_movie_details(candidate.tmdb_id)
                changes = await save_movie_release_refresh(
                    candidate.media_id,
                    movie,
                    today=datetime.now(worker_timezone()).date(),
                    database_url=database_url,
                )
            else:
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
