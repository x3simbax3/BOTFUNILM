"""CLI entry point for the persistent media worker."""

from __future__ import annotations

import argparse
import asyncio
import logging
import os

from aiogram import Bot
from redis.asyncio import Redis

from config.config import (
    BOT_TOKEN,
    DATABASE_URL,
    DEBUG,
    MEDIA_WORKER_TIMEZONE,
    REDIS_URL,
    THENEWSAPI_KEY,
)
from src.database.connection import connect_database
from src.http_client import close_http_session
from src.jobs.media_refresh import get_media_candidate, get_tmdb_candidates
from src.jobs.media_refresh_runner import run_manual_refresh, run_refresh_job
from src.jobs.media_worker_admin import run_admin_job_listener
from src.jobs.media_worker_jobs import (
    run_news_locked_or_log,
    run_notifications_locked_or_log,
)
from src.jobs.media_worker_schedule import run_news_scheduler, run_worker
from src.jobs.media_worker_settings import validate_settings
from src.logging_config import configure_logging
from src.observability import ObservabilityServer
from src.tmdb_limiter import close_tmdb_request_limiter

logger = logging.getLogger(__name__)


async def verify_dependencies(redis: Redis, database_url: str | None) -> None:
    connection = await connect_database(database_url)
    await connection.close()
    if not await redis.ping():
        raise RuntimeError("Redis ping failed")


def parser() -> argparse.ArgumentParser:
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
    subparsers.add_parser("news", help="broadcast one cinema news article now")
    return parser


async def async_main(arguments: list[str] | None = None) -> None:
    validate_settings()
    options = parser().parse_args(arguments)
    redis = Redis.from_url(REDIS_URL, decode_responses=True)
    try:
        await verify_dependencies(redis, DATABASE_URL)
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
                await run_notifications_locked_or_log(
                    redis,
                    bot,
                    database_url=DATABASE_URL,
                )
            elif options.command == "news":
                if not THENEWSAPI_KEY:
                    raise RuntimeError("THENEWSAPI_KEY is required for news broadcasts")
                await run_news_locked_or_log(redis, bot, database_url=DATABASE_URL)
            else:
                logger.info(
                    "Media worker startup completed timezone=%s", MEDIA_WORKER_TIMEZONE
                )
                await asyncio.gather(
                    run_worker(redis, bot),
                    run_news_scheduler(redis, bot),
                    run_admin_job_listener(redis, bot),
                )
    finally:
        await close_http_session()
        try:
            await close_tmdb_request_limiter()
        finally:
            await redis.aclose()


def main() -> None:
    configure_logging(debug=DEBUG)
    os.umask(0o077)

    async def run() -> None:
        observability = ObservabilityServer("media-worker")
        await observability.start()
        try:
            await async_main()
        finally:
            await observability.close()

    asyncio.run(run())


if __name__ == "__main__":
    main()
