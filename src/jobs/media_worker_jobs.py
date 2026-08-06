"""Locked executions and result delivery for media worker jobs."""

from __future__ import annotations

import logging
import traceback
from datetime import datetime

from aiogram import Bot
from aiogram.exceptions import TelegramAPIError
from redis.asyncio import Redis

from config.config import ADMIN_USER_IDS, MEDIA_REFRESH_LOCK_TTL_SECONDS
from src.database.news_api_usage import NewsApiDailyBudgetError
from src.jobs.media_refresh import RefreshMode
from src.jobs.media_refresh_runner import run_refresh_job
from src.jobs.media_worker_settings import worker_timezone
from src.jobs.news_broadcast import NewsBroadcastStats, send_news_broadcast
from src.jobs.series_notifications import send_release_notifications
from src.jobs.worker_lock import JobAlreadyRunningError, RedisJobLock
from src.logging_config import safe_exception_info
from src.news_api import (
    NewsApiAuthenticationError,
    NewsApiError,
    NewsApiRateLimitError,
    NewsApiUnavailableError,
)
from src.tmdb_models import TmdbAuthenticationError

logger = logging.getLogger(__name__)


async def run_refresh_locked_or_log(
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


async def run_notifications_locked_or_log(
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


async def run_news_locked_or_log(
    redis: Redis,
    bot: Bot,
    *,
    database_url: str | None,
) -> NewsBroadcastStats | None:
    try:
        async with RedisJobLock(
            redis,
            "news-broadcast",
            MEDIA_REFRESH_LOCK_TTL_SECONDS,
        ):
            return await send_news_broadcast(
                redis,
                bot,
                datetime.now(worker_timezone()),
                database_url=database_url,
            )
    except JobAlreadyRunningError:
        logger.warning("News broadcast skipped because lock is held")
    except NewsApiAuthenticationError as exc:
        logger.error("News broadcast stopped because TheNewsAPI key is invalid")
        await notify_admins_about_news_failure(bot, exc)
    except NewsApiRateLimitError as exc:
        logger.error("News broadcast stopped because TheNewsAPI limit was reached")
        await notify_admins_about_news_failure(bot, exc)
    except NewsApiUnavailableError as exc:
        logger.error("News broadcast skipped because TheNewsAPI is unavailable")
        await notify_admins_about_news_failure(bot, exc)
    except NewsApiError as exc:
        logger.exception(
            "News broadcast skipped because TheNewsAPI response is invalid"
        )
        await notify_admins_about_news_failure(bot, exc)
    except NewsApiDailyBudgetError as exc:
        logger.info("News broadcast skipped because the daily API budget is exhausted")
        await notify_admins_about_news_failure(bot, exc)
    except Exception as exc:
        logger.exception("News broadcast failed without stopping the media worker")
        await notify_admins_about_news_failure(bot, exc)
    return None


async def notify_admins_about_news_failure(bot: Bot, exception: Exception) -> None:
    text = "Новости не отправлены.\n\n" + short_traceback(exception)
    for admin_id in sorted(ADMIN_USER_IDS):
        try:
            await bot.send_message(admin_id, text)
        except TelegramAPIError:
            logger.exception(
                "Failed to notify admin about news failure: user_id=%s", admin_id
            )


def short_traceback(exception: Exception) -> str:
    _, sanitized, traceback_value = safe_exception_info(exception)
    frames = traceback.extract_tb(traceback_value, limit=2)
    locations = "\n".join(
        f'  File "{frame.filename}", line {frame.lineno}, in {frame.name}'
        for frame in frames
    )
    return (f"Traceback (most recent call last):\n{locations}\n{sanitized}")[:1500]


async def send_admin_job_result(
    bot: Bot,
    requested_by: object,
    text: str,
) -> None:
    if type(requested_by) is not int:
        return
    try:
        await bot.send_message(requested_by, text)
    except TelegramAPIError:
        logger.exception("Failed to send admin job result: user_id=%s", requested_by)


def news_result_text(stats: NewsBroadcastStats | None) -> str:
    if stats is None:
        return "Новость не отправлена: воркер не смог выполнить задачу."
    if stats.article_uuid is None:
        return "Новость не отправлена: свежая статья не найдена или нет подписчиков."
    return (
        f"Новость отправлена: {stats.sent} из {stats.selected}, ошибок {stats.failed}."
    )
