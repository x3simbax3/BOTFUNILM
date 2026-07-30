"""Telegram delivery for persisted series release notifications."""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass

from aiogram import Bot
from aiogram.exceptions import TelegramAPIError

from src.database.series_subscriptions import (
    get_notification_batch,
    mark_notification_batch_sent,
    prepare_notification_batches,
)
from src.keyboards import notification_keyboard
from src.lang import release_notification_text

logger = logging.getLogger(__name__)
NOTIFICATION_PAGE_SIZE = 10
SEND_INTERVAL_SECONDS = 0.05


@dataclass
class NotificationStats:
    selected: int = 0
    sent: int = 0
    failed: int = 0


async def send_release_notifications(
    bot: Bot,
    *,
    database_url: str | None = None,
) -> NotificationStats:
    """Send one first-page message for every user with pending releases."""
    batches = await prepare_notification_batches(database_url=database_url)
    stats = NotificationStats(selected=len(batches))
    for batch in batches:
        items = await get_notification_batch(
            batch.batch_id,
            batch.user_id,
            database_url=database_url,
        )
        if not items:
            await mark_notification_batch_sent(
                batch.batch_id,
                database_url=database_url,
            )
            continue
        total_pages = (
            len(items) + NOTIFICATION_PAGE_SIZE - 1
        ) // NOTIFICATION_PAGE_SIZE
        try:
            await bot.send_message(
                chat_id=batch.user_id,
                text=release_notification_text(
                    items[:NOTIFICATION_PAGE_SIZE],
                    0,
                    total_pages,
                ),
                parse_mode="HTML",
                reply_markup=notification_keyboard(batch.batch_id, 0, total_pages),
            )
        except TelegramAPIError:
            stats.failed += 1
            logger.exception(
                "Series notification delivery failed: batch_id=%s user_id=%s",
                batch.batch_id,
                batch.user_id,
            )
            continue
        await mark_notification_batch_sent(
            batch.batch_id,
            database_url=database_url,
        )
        stats.sent += 1
        await asyncio.sleep(SEND_INTERVAL_SECONDS)

    logger.info(
        "Series notifications completed: selected=%s sent=%s failed=%s",
        stats.selected,
        stats.sent,
        stats.failed,
    )
    return stats


__all__ = ("NotificationStats", "send_release_notifications")
