"""Select one cinema news article and broadcast it to bot users."""

from __future__ import annotations

import asyncio
import html
import logging
from dataclasses import dataclass, replace
from datetime import datetime, timedelta, timezone
from urllib.parse import urlsplit

import aiosqlite
from aiogram import Bot
from aiogram.exceptions import (
    TelegramAPIError,
    TelegramBadRequest,
    TelegramForbiddenError,
    TelegramRetryAfter,
)
from aiogram.types import (
    BufferedInputFile,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
)
from redis.asyncio import Redis

from config.config import (
    NEWS_ALLOWED_DOMAINS,
    NEWS_API_DAILY_BUDGET,
    NEWS_MAX_AGE_HOURS,
    NEWS_RETENTION_DAYS,
)
from src.database.bot_users import get_news_recipients, mark_bot_user_inactive
from src.database.news_api_usage import (
    NewsApiDailyBudgetError,
    reserve_news_api_request,
    update_news_api_quota,
)
from src.database.news_articles import (
    claim_news_candidate,
    delete_old_news_articles,
    finish_news_candidate,
    record_news_delivery,
    save_news_candidate,
)
from src.database.notification_delivery import record_notification_delivery
from src.news_api import (
    NewsApiAuthenticationError,
    NewsApiError,
    NewsApiRateLimitError,
    TheNewsApiProvider,
)
from src.news_models import NewsArticle, NewsImage
from src.news_provider import NewsProvider

logger = logging.getLogger(__name__)
USER_BATCH_SIZE = 100
SEND_INTERVAL_SECONDS = 0.06
TELEGRAM_CAPTION_LIMIT = 1024


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


NEWS_FILTERS = (
    NewsFilter(
        "trusted-cinema",
        "Проверенные новости кино",
        "единый запрос TheNewsAPI",
    ),
)


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
    stats.article_uuid = article.uuid
    photo: str | BufferedInputFile = BufferedInputFile(
        image.data,
        filename=image.filename,
    )
    after_user_id = 0
    batch = await get_news_recipients(
        article_uuid=article.uuid,
        limit=USER_BATCH_SIZE,
        database_url=database_url,
    )
    photo_rejected = False

    while batch and not photo_rejected:
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
                await record_news_delivery(
                    article.uuid,
                    user_id,
                    "sent",
                    database_url=database_url,
                )
            except TelegramForbiddenError:
                stats.deactivated += 1
                await mark_bot_user_inactive(user_id, database_url=database_url)
                await record_news_delivery(
                    article.uuid,
                    user_id,
                    "deactivated",
                    database_url=database_url,
                )
                logger.info("News recipient deactivated: user_id=%s", user_id)
            except TelegramBadRequest:
                stats.failed += 1
                if isinstance(photo, BufferedInputFile):
                    photo_rejected = True
                    logger.exception(
                        "Validated news image was rejected by Telegram: uuid=%s",
                        article.uuid,
                    )
                    break
                logger.exception("News delivery failed: user_id=%s", user_id)
            except TelegramAPIError:
                stats.failed += 1
                logger.exception("News delivery failed: user_id=%s", user_id)
            await asyncio.sleep(SEND_INTERVAL_SECONDS)

        after_user_id = batch[-1]
        batch = await get_news_recipients(
            article_uuid=article.uuid,
            after_user_id=after_user_id,
            limit=USER_BATCH_SIZE,
            database_url=database_url,
        )

    if photo_rejected:
        await finish_news_candidate(
            article.uuid,
            "rejected",
            rejection_reason="telegram-image-rejected",
            database_url=database_url,
        )
    elif stats.failed:
        await finish_news_candidate(
            article.uuid,
            "candidate",
            database_url=database_url,
        )
    else:
        await finish_news_candidate(
            article.uuid,
            "sent",
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
    *,
    database_url: str | None = None,
    provider: NewsProvider | None = None,
) -> tuple[NewsFilter, NewsArticle, NewsImage] | None:
    _ = redis  # The outer Redis lock serializes manual and scheduled broadcasts.
    provider = provider or TheNewsApiProvider()
    await delete_old_news_articles(
        now - timedelta(days=NEWS_RETENTION_DAYS),
        database_url=database_url,
    )
    published_after = (now - timedelta(hours=NEWS_MAX_AGE_HOURS)).astimezone(
        timezone.utc
    )
    fetch_error: NewsApiError | NewsApiDailyBudgetError | None = None
    try:
        await _refresh_news_candidates(
            now,
            published_after=published_after,
            database_url=database_url,
            provider=provider,
        )
    except (NewsApiAuthenticationError, NewsApiRateLimitError):
        raise
    except (NewsApiError, NewsApiDailyBudgetError) as exc:
        fetch_error = exc
        logger.warning(
            "News fetch failed; trying cached candidates: error=%s",
            exc,
        )

    for _ in range(20):
        article = await claim_news_candidate(
            published_after,
            database_url=database_url,
        )
        if article is None:
            if fetch_error is not None:
                raise fetch_error
            return None
        rejection = _article_rejection_reason(article, now)
        if rejection:
            await finish_news_candidate(
                article.uuid,
                "rejected",
                rejection_reason=rejection,
                database_url=database_url,
            )
            continue
        image = await provider.fetch_image(article.image_url or "")
        if image is None:
            await finish_news_candidate(
                article.uuid,
                "rejected",
                rejection_reason="invalid-image",
                database_url=database_url,
            )
            logger.info(
                "News candidate rejected: uuid=%s source=%s reason=invalid-image",
                article.uuid,
                article.source,
            )
            continue
        return NEWS_FILTERS[0], article, image
    if fetch_error is not None:
        raise fetch_error
    return None


async def _refresh_news_candidates(
    now: datetime,
    *,
    published_after: datetime,
    database_url: str | None,
    provider: NewsProvider,
) -> None:
    async def reserve_request() -> None:
        await reserve_news_api_request(
            now.date(),
            NEWS_API_DAILY_BUDGET,
            database_url=database_url,
        )

    result = await provider.fetch_news(
        published_after=published_after,
        before_request=reserve_request,
    )
    await update_news_api_quota(
        now.date(),
        api_limit=result.api_limit,
        api_remaining=result.api_remaining,
        database_url=database_url,
    )

    articles = sorted(
        result.articles,
        key=lambda article: (
            _published_at(article) or datetime.min.replace(tzinfo=timezone.utc)
        ),
        reverse=True,
    )
    for article in articles:
        rejection = _article_rejection_reason(article, now)
        if rejection == "truncated-description":
            complete_description = await provider.fetch_description(article.url)
            if complete_description:
                article = replace(article, description=complete_description)
                rejection = _article_rejection_reason(article, now)
        if rejection:
            logger.info(
                "News candidate rejected: uuid=%s source=%s reason=%s",
                article.uuid,
                article.source,
                rejection,
            )
            continue
        await save_news_candidate(article, database_url=database_url)


async def _deliver_article(
    bot: Bot,
    user_id: int,
    article: NewsArticle,
    photo: str | BufferedInputFile,
) -> Message:
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Читать источник", url=article.url)]
        ]
    )
    return await _retry_after(
        bot.send_photo,
        chat_id=user_id,
        photo=photo,
        caption=_article_text(article),
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
    source_text = _truncate_caption_part(source_text, TELEGRAM_CAPTION_LIMIT - 4)
    title_limit = TELEGRAM_CAPTION_LIMIT - len(source_text) - 4
    title_text = _truncate_caption_part(article.title, title_limit)
    description_limit = TELEGRAM_CAPTION_LIMIT - len(title_text) - len(source_text) - 4
    description_text = _truncate_caption_part(
        article.description,
        description_limit,
    )
    title = html.escape(title_text)
    description = html.escape(description_text)
    source = html.escape(source_text)
    return "\n\n".join((f"<b>{title}</b>", description, source))


def _truncate_caption_part(value: str, limit: int) -> str:
    if len(value) <= limit:
        return value
    if limit <= 0:
        return ""
    if limit == 1:
        return "…"
    return f"{value[: limit - 1].rstrip()}…"


def _article_rejection_reason(article: NewsArticle, now: datetime) -> str | None:
    published_at = _published_at(article)
    utc_now = now.astimezone(timezone.utc)
    if published_at is None:
        return "invalid-published-at"
    if published_at > utc_now + timedelta(minutes=10):
        return "future-published-at"
    if published_at < utc_now - timedelta(hours=NEWS_MAX_AGE_HOURS):
        return "stale"
    if not any(
        article.source == domain or article.source.endswith(f".{domain}")
        for domain in NEWS_ALLOWED_DOMAINS
    ):
        return "untrusted-source"
    if not article.description:
        return "missing-description"
    if article.description.endswith(("...", "…")):
        return "truncated-description"
    if not article.image_url:
        return "missing-image"
    if "favicon" in urlsplit(article.image_url).path.lower():
        return "favicon-image"
    return None


def _published_at(article: NewsArticle) -> datetime | None:
    try:
        value = datetime.fromisoformat(article.published_at.replace("Z", "+00:00"))
    except ValueError:
        return None
    if value.tzinfo is None:
        return None
    return value.astimezone(timezone.utc)


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
