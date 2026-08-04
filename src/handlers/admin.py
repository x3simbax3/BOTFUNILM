"""Read-only Telegram admin overview."""

from collections.abc import Collection
from dataclasses import asdict

import aiosqlite
from aiogram import F, Router
from aiogram.enums import ChatType
from aiogram.filters import Command, Filter
from aiogram.types import CallbackQuery, Message, TelegramObject

from config.config import ADMIN_USER_IDS
from src.database.admin import (
    AdminActivity,
    AdminOverview,
    AdminUserDetails,
    AdminUserSummary,
    get_admin_activity,
    get_admin_overview,
    get_admin_user,
    get_admin_users,
)
from src.handlers.common import edit_message
from src.keyboards import (
    admin_activity_keyboard,
    admin_overview_keyboard,
    admin_user_keyboard,
    admin_users_keyboard,
)
from src.lang import (
    ADMIN_ACCESS_DENIED,
    ADMIN_ACTIVITY_FAILED,
    ADMIN_CALLBACK_DENIED,
    ADMIN_INVALID_CALLBACK,
    ADMIN_OVERVIEW_FAILED,
    ADMIN_USER_NOT_FOUND,
    ADMIN_USERS_FAILED,
    admin_activity_text,
    admin_overview_text,
    admin_user_text,
    admin_users_text,
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


def _user_button_label(user: AdminUserSummary) -> str:
    name = user.display_name or (f"@{user.username}" if user.username else None)
    normalized_name = " ".join(name.split()) if name else str(user.user_id)
    status = "●" if user.is_active else "○"
    return f"{status} {normalized_name[:42]} · {user.library_items}"


def _user_text(user: AdminUserDetails) -> str:
    return admin_user_text(**asdict(user))


def _positive_int(value: str) -> int | None:
    if not value.isascii() or not value.isdigit():
        return None
    parsed = int(value)
    return parsed if parsed > 0 else None


def _activity_text(activity: AdminActivity) -> str:
    return admin_activity_text(
        days=activity.days,
        dau=activity.dau,
        wau=activity.wau,
        mau=activity.mau,
        new_users=activity.new_users,
        returning_users=activity.returning_users,
        searches=activity.searches,
        library_opens=activity.library_opens,
        media_added=activity.media_added,
        ratings_set=activity.ratings_set,
        progress_updates=activity.progress_updates,
        daily=tuple(
            (
                day.event_date,
                day.active_users,
                day.new_users,
                day.returning_users,
            )
            for day in activity.daily
        ),
        generated_at=activity.generated_at,
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


@router.callback_query(F.data.startswith("admin:users:"), admin_filter)
async def show_admin_users(callback: CallbackQuery) -> None:
    if not callback.message or not callback.data:
        await callback.answer()
        return
    page = _positive_int(callback.data.removeprefix("admin:users:"))
    if page is None:
        await callback.answer(ADMIN_INVALID_CALLBACK, show_alert=True)
        return
    try:
        user_page = await get_admin_users(page)
    except aiosqlite.Error:
        await callback.answer(ADMIN_USERS_FAILED, show_alert=True)
        return

    await edit_message(
        callback.message,
        admin_users_text(
            total_users=user_page.total_users,
            page=user_page.page,
            total_pages=user_page.total_pages,
        ),
        parse_mode="HTML",
        reply_markup=admin_users_keyboard(
            [(user.user_id, _user_button_label(user)) for user in user_page.users],
            page=user_page.page,
            total_pages=user_page.total_pages,
        ),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("admin:user:"), admin_filter)
async def show_admin_user(callback: CallbackQuery) -> None:
    if not callback.message or not callback.data:
        await callback.answer()
        return
    parts = callback.data.split(":")
    if len(parts) != 4:
        await callback.answer(ADMIN_INVALID_CALLBACK, show_alert=True)
        return
    user_id = _positive_int(parts[2])
    page = _positive_int(parts[3])
    if user_id is None or page is None:
        await callback.answer(ADMIN_INVALID_CALLBACK, show_alert=True)
        return
    try:
        user = await get_admin_user(user_id)
    except aiosqlite.Error:
        await callback.answer(ADMIN_USERS_FAILED, show_alert=True)
        return
    if user is None:
        await callback.answer(ADMIN_USER_NOT_FOUND, show_alert=True)
        return

    await edit_message(
        callback.message,
        _user_text(user),
        parse_mode="HTML",
        reply_markup=admin_user_keyboard(page),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("admin:activity:"), admin_filter)
async def show_admin_activity(callback: CallbackQuery) -> None:
    if not callback.message or not callback.data:
        await callback.answer()
        return
    days = _positive_int(callback.data.removeprefix("admin:activity:"))
    if days not in {7, 30}:
        await callback.answer(ADMIN_INVALID_CALLBACK, show_alert=True)
        return
    try:
        activity = await get_admin_activity(days)
    except aiosqlite.Error:
        await callback.answer(ADMIN_ACTIVITY_FAILED, show_alert=True)
        return

    await edit_message(
        callback.message,
        _activity_text(activity),
        parse_mode="HTML",
        reply_markup=admin_activity_keyboard(days),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("admin:"))
async def deny_admin_callback(callback: CallbackQuery) -> None:
    await callback.answer(ADMIN_CALLBACK_DENIED, show_alert=True)


__all__ = (
    "AdminFilter",
    "deny_admin_callback",
    "deny_admin_overview",
    "refresh_admin_overview",
    "router",
    "show_admin_user",
    "show_admin_users",
    "show_admin_activity",
    "show_admin_overview",
)
