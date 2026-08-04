"""Select one cinema news article and broadcast it to bot users."""

from __future__ import annotations

import asyncio
import html
import logging
import secrets
from dataclasses import dataclass, replace
from datetime import datetime, timedelta, timezone

import aiosqlite
from aiogram import Bot
from aiogram.exceptions import (
    TelegramAPIError,
    TelegramForbiddenError,
    TelegramRetryAfter,
)
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, Message
from redis.asyncio import Redis

from src.database.bot_users import get_news_recipients, mark_bot_user_inactive
from src.database.notification_delivery import record_notification_delivery
from src.news_api import (
    NewsApiAuthenticationError,
    NewsApiError,
    NewsApiRateLimitError,
    NewsArticle,
    fetch_article_text,
    fetch_news,
)

logger = logging.getLogger(__name__)
USER_BATCH_SIZE = 100
SEND_INTERVAL_SECONDS = 0.06
MAX_FILTERS_PER_RUN = 4
NEWS_LOOKBACK_DAYS = 7
SENT_NEWS_TTL_SECONDS = 8 * 86400


@dataclass(frozen=True)
class NewsFilter:
    name: str
    label: str
    search: str


@dataclass
class NewsBroadcastStats:
    selected: int = 0
    sent: int = 0
    failed: int = 0
    deactivated: int = 0
    article_uuid: str | None = None


# Every filter has the same chance. In particular, anime has the same priority
# as films and series, rather than being an occasional fallback.
NEWS_FILTERS = (
    NewsFilter(
        "films-series",
        "Кино и сериалы",
        "((фильм | кино | сериал | сезон) + "
        "(премьера | трейлер | вышел | выйдет | съемки | экранизация | продлили))",
    ),
    NewsFilter(
        "anime",
        "Аниме",
        "(аниме | манга | Crunchyroll | Ghibli)",
    ),
    NewsFilter(
        "animation",
        "Мультфильмы и анимация",
        "(мультфильм | мультсериал | анимация | анимационный)",
    ),
    NewsFilter(
        "cinema-people",
        "Люди кино",
        "((актер | актриса | режиссер | сценарист) + "
        "(фильм | кино | сериал | роль | съемки))",
    ),
    NewsFilter(
        "industry",
        "Киноиндустрия",
        "(кинопрокат | кинофестиваль | кинопремия | кассовые сборы)",
    ),
)


async def send_news_broadcast(
    redis: Redis,
    bot: Bot,
    now: datetime,
    *,
    database_url: str | None = None,
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

    selected = await select_news_article(redis, now)
    if selected is None:
        logger.warning("News broadcast skipped because no fresh article was found")
        return stats
    article_filter, article = selected
    if article.description.endswith(("...", "…")):
        expanded_text = await fetch_article_text(article.url)
        if expanded_text:
            article = replace(article, description=expanded_text)
    stats.article_uuid = article.uuid
    if not article.image_url:
        logger.warning("News broadcast skipped because selected article has no image")
        return stats
    photo = article.image_url
    after_user_id = 0
    batch = first_batch

    while batch:
        for user_id in batch:
            stats.selected += 1
            try:
                message = await _deliver_article(
                    bot,
                    user_id,
                    article,
                    photo,
                )
                photo = _telegram_photo_id(message) or photo
                stats.sent += 1
            except TelegramForbiddenError:
                stats.deactivated += 1
                await mark_bot_user_inactive(user_id, database_url=database_url)
                logger.info("News recipient deactivated: user_id=%s", user_id)
            except TelegramAPIError:
                stats.failed += 1
                logger.exception("News delivery failed: user_id=%s", user_id)
            await asyncio.sleep(SEND_INTERVAL_SECONDS)

        after_user_id = batch[-1]
        batch = await get_news_recipients(
            after_user_id=after_user_id,
            limit=USER_BATCH_SIZE,
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
    try:
        await record_notification_delivery(
            "news",
            selected=stats.selected,
            sent=stats.sent,
            failed=stats.failed,
            deactivated=stats.deactivated,
            database_url=database_url,
        )
    except aiosqlite.Error:
        logger.exception("Failed to persist news delivery statistics")
    return stats


async def select_news_article(
    redis: Redis,
    now: datetime,
) -> tuple[NewsFilter, NewsArticle] | None:
    local_now = now
    sent_key = "news:sent"
    cutoff = (local_now - timedelta(days=NEWS_LOOKBACK_DAYS)).timestamp()
    await redis.zremrangebyscore(sent_key, "-inf", cutoff)
    last_filter = await redis.get("news:last-filter")
    filters = [item for item in NEWS_FILTERS if item.name != last_filter]
    secrets.SystemRandom().shuffle(filters)
    filters.extend(item for item in NEWS_FILTERS if item.name == last_filter)
    published_after = (local_now - timedelta(days=NEWS_LOOKBACK_DAYS)).astimezone(
        timezone.utc
    )

    for article_filter in filters[:MAX_FILTERS_PER_RUN]:
        try:
            articles = await fetch_news(
                article_filter.search,
                published_after=published_after,
            )
        except (NewsApiAuthenticationError, NewsApiRateLimitError):
            raise
        except NewsApiError as exc:
            logger.warning(
                "News filter request failed: filter=%s error=%s",
                article_filter.name,
                exc,
            )
            continue

        for article in articles:
            if not article.image_url:
                continue
            if not await redis.zadd(
                sent_key,
                {article.uuid: local_now.timestamp()},
                nx=True,
            ):
                continue
            await redis.expire(sent_key, SENT_NEWS_TTL_SECONDS)
            await redis.set("news:last-filter", article_filter.name, ex=2 * 86400)
            return article_filter, article
    return None


async def _deliver_article(
    bot: Bot,
    user_id: int,
    article: NewsArticle,
    photo: str,
) -> Message:
    text = _article_text(article)
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Читать источник", url=article.url)]
        ]
    )
    return await _retry_after(
        bot.send_photo,
        chat_id=user_id,
        photo=photo,
        caption=text,
        parse_mode="HTML",
        reply_markup=keyboard,
    )


async def _retry_after(method, **kwargs) -> Message:
    for attempt in range(2):
        try:
            return await method(**kwargs)
        except TelegramRetryAfter as exc:
            if attempt:
                raise
            await asyncio.sleep(exc.retry_after)
    raise AssertionError("unreachable")


def _article_text(article: NewsArticle) -> str:
    source_text = article.source or "Источник"
    description_limit = max(
        0,
        1024 - len(article.title) - len(source_text) - len("\n\n\n\n"),
    )
    title = html.escape(article.title)
    description = html.escape(_truncate(article.description, description_limit))
    source = html.escape(source_text)
    parts = [f"<b>{title}</b>"]
    if description:
        parts.append(description)
    parts.append(source)
    return "\n\n".join(parts)


def _truncate(value: str, limit: int) -> str:
    if limit <= 0:
        return ""
    if len(value) <= limit:
        return value
    if limit == 1:
        return "…"
    return value[: limit - 1].rstrip() + "…"


def _telegram_photo_id(message: Message) -> str | None:
    if not message.photo:
        return None
    return message.photo[-1].file_id


__all__ = (
    "NEWS_FILTERS",
    "NewsBroadcastStats",
    "NewsFilter",
    "select_news_article",
    "send_news_broadcast",
)
