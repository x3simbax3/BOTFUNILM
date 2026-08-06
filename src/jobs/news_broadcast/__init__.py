"""Select and broadcast one cinema news article."""

from __future__ import annotations

import logging
from datetime import datetime

from aiogram import Bot
from redis.asyncio import Redis

from src.database.bot_users import get_news_recipients
from src.jobs.news_broadcast.delivery import deliver_news_article
from src.jobs.news_broadcast.message import _article_text
from src.jobs.news_broadcast.models import (
    NEWS_FILTERS,
    USER_BATCH_SIZE,
    NewsBroadcastStats,
    NewsFilter,
)
from src.jobs.news_broadcast.selection import select_news_article
from src.news_provider import NewsProvider

logger = logging.getLogger(__name__)


async def send_news_broadcast(
    redis: Redis,
    bot: Bot,
    now: datetime,
    *,
    database_url: str | None = None,
    provider: NewsProvider | None = None,
) -> NewsBroadcastStats:
    """Select and broadcast one article, returning without work if no users exist."""
    first_batch = await get_news_recipients(
        limit=USER_BATCH_SIZE,
        database_url=database_url,
    )
    stats = NewsBroadcastStats()
    if not first_batch:
        logger.info("News broadcast skipped because there are no opted-in users")
        return stats

    selected = await select_news_article(
        redis,
        now,
        database_url=database_url,
        provider=provider,
    )
    if selected is None:
        logger.warning("News broadcast skipped because no fresh article was found")
        return stats
    article_filter, article, image = selected
    stats = await deliver_news_article(
        bot,
        article,
        image,
        database_url=database_url,
    )
    logger.info(
        "News broadcast completed: uuid=%s filter=%s selected=%s sent=%s "
        "failed=%s deactivated=%s",
        article.uuid,
        article_filter.name,
        stats.selected,
        stats.sent,
        stats.failed,
        stats.deactivated,
    )
    return stats


__all__ = (
    "NEWS_FILTERS",
    "NewsBroadcastStats",
    "NewsFilter",
    "select_news_article",
    "send_news_broadcast",
)
