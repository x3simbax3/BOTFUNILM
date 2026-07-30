"""Series subscription lists, toggles and notification pagination."""

from __future__ import annotations

import aiosqlite
from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, LinkPreviewOptions

from src.database.library import get_user_library_item
from src.database.series_subscriptions import (
    SeriesSubscriptionLimitError,
    SeriesSubscriptionNotFoundError,
    SeriesSubscriptionUnavailableError,
    get_notification_batch,
    list_tracked_series,
    set_series_subscription,
)
from src.fsm import MenuState
from src.handlers.common import edit_message, replace_message
from src.keyboards import (
    library_item_keyboard,
    notification_keyboard,
    post_add_tracking_keyboard,
    tracked_series_keyboard,
)
from src.lang import (
    INVALID_PAGE,
    ITEM_NOT_FOUND,
    NOTIFICATION_NOT_FOUND,
    TRACKED_OPEN_FAILED,
    TRACKING_DISABLED,
    TRACKING_ENABLED,
    TRACKING_LIMIT_REACHED,
    TRACKING_SAVE_FAILED,
    TRACKING_UNAVAILABLE,
    release_notification_text,
    replace_tracking_status,
    tracked_series_text,
)
from src.models import current_media_id, is_active_series

router = Router(name="tracking")
TRACKED_PAGE_SIZE = 10
NOTIFICATION_PAGE_SIZE = 10
MAX_PAGE = 100_000


@router.callback_query(F.data == "menu:tracked")
async def open_tracked_series(callback: CallbackQuery, state: FSMContext) -> None:
    await _open_tracked_page(callback, state, 0)


@router.callback_query(F.data.startswith("tracked:page:"))
async def change_tracked_page(callback: CallbackQuery, state: FSMContext) -> None:
    page = _positive_page(callback.data, "tracked:page:")
    if page is None:
        await callback.answer(INVALID_PAGE, show_alert=True)
        return
    await _open_tracked_page(callback, state, page)


async def _open_tracked_page(
    callback: CallbackQuery,
    state: FSMContext,
    page: int,
) -> None:
    if not callback.message:
        return
    try:
        items = await list_tracked_series(
            callback.from_user.id,
            limit=TRACKED_PAGE_SIZE + 1,
            offset=page * TRACKED_PAGE_SIZE,
        )
        bot_user = await callback.bot.me()
        if not bot_user.username:
            raise RuntimeError("Bot username is unavailable")
    except (aiosqlite.Error, RuntimeError):
        await callback.answer(TRACKED_OPEN_FAILED, show_alert=True)
        return

    visible_items = items[:TRACKED_PAGE_SIZE]
    await replace_message(
        callback.message,
        tracked_series_text(
            visible_items,
            bot_user.username,
            page * TRACKED_PAGE_SIZE,
        ),
        parse_mode="HTML",
        reply_markup=tracked_series_keyboard(
            page,
            len(items) > TRACKED_PAGE_SIZE,
        ),
        link_preview_options=LinkPreviewOptions(is_disabled=True),
    )
    await state.set_state(MenuState.viewing_tracked)
    await state.update_data(tracked_page=page)
    await callback.answer()


@router.callback_query(F.data == "series:tracking:toggle")
async def toggle_library_subscription(
    callback: CallbackQuery,
    state: FSMContext,
) -> None:
    if not callback.message:
        return
    media_id = current_media_id(await state.get_data())
    if media_id is None:
        await callback.answer(ITEM_NOT_FOUND, show_alert=True)
        return
    item = await _toggle(callback, media_id)
    if item is None:
        return
    source_text = getattr(callback.message, "html_text", None)
    if not isinstance(source_text, str):
        return
    await edit_message(
        callback.message,
        source_text,
        parse_mode="HTML",
        reply_markup=library_item_keyboard(
            planned=item["user_status"] == "planned",
            released=bool(dict(item).get("is_released", True)),
            tracking_available=is_active_series(
                item["tmdb_status"], item["tmdb_in_production"]
            ),
            tracking_enabled=bool(item["is_tracking"]),
        ),
    )


@router.callback_query(F.data.startswith("series:tracking:add:"))
async def toggle_post_add_subscription(callback: CallbackQuery) -> None:
    if not callback.message or not callback.data:
        return
    value = callback.data.removeprefix("series:tracking:add:")
    if not value.isdigit() or int(value) <= 0:
        await callback.answer(ITEM_NOT_FOUND, show_alert=True)
        return
    item = await _toggle(callback, int(value))
    if item is None:
        return
    source_text = getattr(callback.message, "html_text", None)
    if not isinstance(source_text, str):
        source_text = callback.message.text or ""
    await edit_message(
        callback.message,
        replace_tracking_status(source_text, bool(item["is_tracking"])),
        parse_mode="HTML",
        reply_markup=post_add_tracking_keyboard(
            int(item["id"]),
            bool(item["is_tracking"]),
        ),
    )


@router.callback_query(F.data == "series:tracking:status")
async def tracking_status_noop(callback: CallbackQuery) -> None:
    await callback.answer()


async def _toggle(callback: CallbackQuery, media_id: int):
    try:
        item = await get_user_library_item(callback.from_user.id, media_id)
        if item is None:
            raise SeriesSubscriptionNotFoundError
        enabled = await set_series_subscription(
            callback.from_user.id,
            media_id,
            not bool(item["is_tracking"]),
        )
        refreshed = await get_user_library_item(callback.from_user.id, media_id)
        if refreshed is None:
            raise SeriesSubscriptionNotFoundError
    except SeriesSubscriptionNotFoundError:
        await callback.answer(ITEM_NOT_FOUND, show_alert=True)
        return None
    except SeriesSubscriptionUnavailableError:
        await callback.answer(TRACKING_UNAVAILABLE, show_alert=True)
        return None
    except SeriesSubscriptionLimitError:
        await callback.answer(TRACKING_LIMIT_REACHED, show_alert=True)
        return None
    except aiosqlite.Error:
        await callback.answer(TRACKING_SAVE_FAILED, show_alert=True)
        return None
    await callback.answer(TRACKING_ENABLED if enabled else TRACKING_DISABLED)
    return refreshed


@router.callback_query(F.data.startswith("series:notifications:"))
async def change_notification_page(callback: CallbackQuery) -> None:
    if not callback.message or not callback.data:
        return
    if callback.data == "series:notifications:noop":
        await callback.answer()
        return
    values = callback.data.removeprefix("series:notifications:").split(":")
    if len(values) != 2 or not all(value.isdigit() for value in values):
        await callback.answer(NOTIFICATION_NOT_FOUND, show_alert=True)
        return
    batch_id, page = map(int, values)
    try:
        items = await get_notification_batch(batch_id, callback.from_user.id)
    except aiosqlite.Error:
        await callback.answer(TRACKING_SAVE_FAILED, show_alert=True)
        return
    if items is None or not items:
        await callback.answer(NOTIFICATION_NOT_FOUND, show_alert=True)
        return
    total_pages = (len(items) + NOTIFICATION_PAGE_SIZE - 1) // NOTIFICATION_PAGE_SIZE
    if page >= total_pages:
        await callback.answer(INVALID_PAGE, show_alert=True)
        return
    first = page * NOTIFICATION_PAGE_SIZE
    await callback.message.edit_text(
        release_notification_text(
            items[first : first + NOTIFICATION_PAGE_SIZE],
            page,
            total_pages,
        ),
        parse_mode="HTML",
        reply_markup=notification_keyboard(batch_id, page, total_pages),
    )
    await callback.answer()


def _positive_page(data: str | None, prefix: str) -> int | None:
    if not data or not data.startswith(prefix):
        return None
    value = data.removeprefix(prefix)
    if not value.isdigit():
        return None
    page = int(value)
    return page if page <= MAX_PAGE else None


__all__ = ("router",)
