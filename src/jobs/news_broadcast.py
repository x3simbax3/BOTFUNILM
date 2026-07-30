"""Select one cinema news article and broadcast it to bot users."""

from __future__ import annotations

import asyncio
import html
import logging
import secrets
from dataclasses import dataclass
from datetime import datetime, time, timedelta, timezone

from aiogram import Bot
from aiogram.exceptions import (
    TelegramAPIError,
    TelegramBadRequest,
    TelegramForbiddenError,
    TelegramRetryAfter,
)
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, Message
from redis.asyncio import Redis

from src.database.bot_users import get_active_bot_users, mark_bot_user_inactive
from src.news_api import (
    NewsApiAuthenticationError,
    NewsApiError,
    NewsApiRateLimitError,
    NewsArticle,
    fetch_news,
)

logger = logging.getLogger(__name__)
USER_BATCH_SIZE = 100
SEND_INTERVAL_SECONDS = 0.06
MAX_FILTERS_PER_RUN = 4


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
    first_batch = await get_active_bot_users(
        limit=USER_BATCH_SIZE,
        database_url=database_url,
    )
    stats = NewsBroadcastStats()
    if not first_batch:
        logger.info("News broadcast skipped because there are no active users")
        return stats

    selected = await select_news_article(redis, now)
    if selected is None:
        logger.warning("News broadcast skipped because no fresh article was found")
        return stats
    article_filter, article = selected
    stats.article_uuid = article.uuid
    photo = article.image_url
    after_user_id = 0
    batch = first_batch

    while batch:
        for user_id in batch:
            stats.selected += 1
            try:
                message, used_photo = await _deliver_article(
                    bot,
                    user_id,
                    article_filter.label,
                    article,
                    photo,
                )
                if used_photo:
                    photo = _telegram_photo_id(message) or photo
                else:
                    photo = None
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
        batch = await get_active_bot_users(
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
    return stats


async def select_news_article(
    redis: Redis,
    now: datetime,
) -> tuple[NewsFilter, NewsArticle] | None:
    local_now = now
    sent_key = f"news:sent:{local_now.date().isoformat()}"
    last_filter = await redis.get("news:last-filter")
    filters = [item for item in NEWS_FILTERS if item.name != last_filter]
    secrets.SystemRandom().shuffle(filters)
    filters.extend(item for item in NEWS_FILTERS if item.name == last_filter)
    published_after = datetime.combine(
        local_now.date(),
        time.min,
        tzinfo=local_now.tzinfo,
    ).astimezone(timezone.utc)

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
            if not await redis.sadd(sent_key, article.uuid):
                continue
            expires_at = datetime.combine(
                local_now.date(),
                time(hour=22, minute=15),
                tzinfo=local_now.tzinfo,
            )
            if expires_at <= local_now:
                expires_at += timedelta(days=1)
            await redis.expireat(sent_key, expires_at)
            await redis.set("news:last-filter", article_filter.name, ex=2 * 86400)
            return article_filter, article
    return None


async def _deliver_article(
    bot: Bot,
    user_id: int,
    category: str,
    article: NewsArticle,
    photo: str | None,
) -> tuple[Message, bool]:
    text = _article_text(category, article)
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Читать источник", url=article.url)]
        ]
    )
    if photo:
        try:
            message = await _retry_after(
                bot.send_photo,
                chat_id=user_id,
                photo=photo,
                caption=text,
                parse_mode="HTML",
                reply_markup=keyboard,
            )
            return message, True
        except TelegramBadRequest:
            logger.info(
                "News image rejected; falling back to text: uuid=%s",
                article.uuid,
            )

    message = await _retry_after(
        bot.send_message,
        chat_id=user_id,
        text=text,
        parse_mode="HTML",
        reply_markup=keyboard,
    )
    return message, False


async def _retry_after(method, **kwargs) -> Message:
    for attempt in range(2):
        try:
            return await method(**kwargs)
        except TelegramRetryAfter as exc:
            if attempt:
                raise
            await asyncio.sleep(exc.retry_after)
    raise AssertionError("unreachable")


def _article_text(category: str, article: NewsArticle) -> str:
    title = html.escape(_truncate(article.title, 220))
    description = html.escape(_truncate(article.description, 620))
    source = html.escape(article.source or "Источник")
    parts = [f"<b>Новости · {html.escape(category)}</b>", f"<b>{title}</b>"]
    if description:
        parts.append(description)
    parts.append(source)
    return "\n\n".join(parts)


def _truncate(value: str, limit: int) -> str:
    if len(value) <= limit:
        return value
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
