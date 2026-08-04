"""Read-only Telegram admin overview."""

from collections.abc import Collection

import aiosqlite
from aiogram import F, Router
from aiogram.enums import ChatType
from aiogram.filters import Command, Filter
from aiogram.types import CallbackQuery, Message, TelegramObject

from config.config import ADMIN_USER_IDS
from src.database.admin import AdminOverview, get_admin_overview
from src.handlers.common import edit_message
from src.keyboards import admin_overview_keyboard
from src.lang import (
    ADMIN_ACCESS_DENIED,
    ADMIN_CALLBACK_DENIED,
    ADMIN_OVERVIEW_FAILED,
    admin_overview_text,
)

router = Router(name="admin")


class AdminFilter(Filter):
    def __init__(self, user_ids: Collection[int]) -> None:
        self.user_ids = frozenset(user_ids)

    async def __call__(self, event: TelegramObject) -> bool:
        user = getattr(event, "from_user", None)
        return user is not None and user.id in self.user_ids


admin_filter = AdminFilter(ADMIN_USER_IDS)


def _overview_text(overview: AdminOverview) -> str:
    return admin_overview_text(
        **{
            field: getattr(overview, field)
            for field in (
                "total_users",
                "active_users",
                "inactive_users",
                "new_24h",
                "new_7d",
                "new_30d",
                "active_24h",
                "active_7d",
                "active_30d",
                "activated_users",
                "activation_percent",
                "library_items",
                "average_library_items",
                "rated_items",
                "tracked_series",
                "news_users",
                "generated_at",
            )
        }
    )


@router.message(Command("admin"), F.chat.type == ChatType.PRIVATE, admin_filter)
async def show_admin_overview(message: Message) -> None:
    try:
        overview = await get_admin_overview()
    except aiosqlite.Error:
        await message.answer(ADMIN_OVERVIEW_FAILED)
        return

    await message.answer(
        _overview_text(overview),
        parse_mode="HTML",
        reply_markup=admin_overview_keyboard(),
    )


@router.message(Command("admin"))
async def deny_admin_overview(message: Message) -> None:
    await message.answer(ADMIN_ACCESS_DENIED)


@router.callback_query(F.data == "admin:overview", admin_filter)
async def refresh_admin_overview(callback: CallbackQuery) -> None:
    if not callback.message:
        await callback.answer()
        return
    try:
        overview = await get_admin_overview()
    except aiosqlite.Error:
        await callback.answer(ADMIN_OVERVIEW_FAILED, show_alert=True)
        return

    await edit_message(
        callback.message,
        _overview_text(overview),
        parse_mode="HTML",
        reply_markup=admin_overview_keyboard(),
    )
    await callback.answer("Обновлено")


@router.callback_query(F.data.startswith("admin:"))
async def deny_admin_callback(callback: CallbackQuery) -> None:
    await callback.answer(ADMIN_CALLBACK_DENIED, show_alert=True)


__all__ = (
    "AdminFilter",
    "deny_admin_callback",
    "deny_admin_overview",
    "refresh_admin_overview",
    "router",
    "show_admin_overview",
)
