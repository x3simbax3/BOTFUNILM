"""Broadcast one admin-authored message to every active bot user."""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass

import aiosqlite
from aiogram import Bot
from aiogram.exceptions import (
    TelegramAPIError,
    TelegramForbiddenError,
    TelegramRetryAfter,
)

from src.database.bot_users import get_active_user_ids, mark_bot_user_inactive
from src.database.notification_delivery import record_notification_delivery

logger = logging.getLogger(__name__)
USER_BATCH_SIZE = 100
SEND_INTERVAL_SECONDS = 0.06


@dataclass
class CustomBroadcastStats:
    selected: int = 0
    sent: int = 0
    failed: int = 0
    deactivated: int = 0


async def send_custom_broadcast(
    bot: Bot,
    text: str,
    *,
    photo_file_id: str | None = None,
    database_url: str | None = None,
) -> CustomBroadcastStats:
    if not text or len(text) > (1024 if photo_file_id else 4096):
        raise ValueError("Invalid broadcast text length")

    stats = CustomBroadcastStats()
    after_user_id = 0
    while batch := await get_active_user_ids(
        after_user_id=after_user_id,
        limit=USER_BATCH_SIZE,
        database_url=database_url,
    ):
        for user_id in batch:
            stats.selected += 1
            try:
                if photo_file_id:
                    await _retry_after(
                        bot.send_photo,
                        chat_id=user_id,
                        photo=photo_file_id,
                        caption=text,
                        parse_mode=None,
                    )
                else:
                    await _retry_after(
                        bot.send_message,
                        chat_id=user_id,
                        text=text,
                        parse_mode=None,
                    )
                stats.sent += 1
            except TelegramForbiddenError:
                stats.deactivated += 1
                await mark_bot_user_inactive(user_id, database_url=database_url)
            except TelegramAPIError:
                stats.failed += 1
                logger.exception("Custom broadcast failed: user_id=%s", user_id)
            await asyncio.sleep(SEND_INTERVAL_SECONDS)
        after_user_id = batch[-1]

    try:
        await record_notification_delivery(
            "broadcast",
            selected=stats.selected,
            sent=stats.sent,
            failed=stats.failed,
            deactivated=stats.deactivated,
            database_url=database_url,
        )
    except aiosqlite.Error:
        logger.exception("Failed to persist custom broadcast statistics")
    return stats


async def _retry_after(method, **kwargs):
    for attempt in range(2):
        try:
            return await method(**kwargs)
        except TelegramRetryAfter as exc:
            if attempt:
                raise
            await asyncio.sleep(exc.retry_after)
    raise AssertionError("unreachable")


__all__ = ("CustomBroadcastStats", "send_custom_broadcast")
