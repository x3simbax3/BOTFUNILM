"""Deliver selected cinema news to subscribed users."""

from __future__ import annotations

import asyncio
import logging

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

from src.database.bot_users import get_news_recipients, mark_bot_user_inactive
from src.database.news_articles import finish_news_candidate, record_news_delivery
from src.database.notification_delivery import record_notification_delivery
from src.jobs.news_broadcast.message import _article_text, _telegram_photo_id
from src.jobs.news_broadcast.models import (
    SEND_INTERVAL_SECONDS,
    USER_BATCH_SIZE,
    NewsBroadcastStats,
)
from src.news_models import NewsArticle, NewsImage

logger = logging.getLogger(__name__)


async def deliver_news_article(
    bot: Bot,
    article: NewsArticle,
    image: NewsImage,
    *,
    database_url: str | None,
) -> NewsBroadcastStats:
    stats = NewsBroadcastStats(article_uuid=article.uuid)
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
                message = await _deliver_article(bot, user_id, article, photo)
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
            except TelegramBadRequest as exc:
                stats.failed += 1
                if _is_telegram_image_error(exc):
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


def _is_telegram_image_error(exc: TelegramBadRequest) -> bool:
    message = exc.message.lower()
    return any(
        marker in message
        for marker in (
            "failed to get http url content",
            "image_process_failed",
            "photo_invalid_dimensions",
            "wrong file identifier/http url specified",
        )
    )


__all__ = ("deliver_news_article",)
