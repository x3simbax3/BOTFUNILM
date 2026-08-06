"""Library list filters, sorting and pagination handlers."""

import aiosqlite
from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, LinkPreviewOptions

from src.callback_data import (
    parse_library_filter_callback,
    parse_library_filter_group_callback,
    parse_library_page_callback,
    parse_library_sort_callback,
)
from src.database.library import (
    get_user_library_filters,
    list_user_library,
    update_user_library_filter,
)
from src.fsm import MenuState
from src.handlers.common import replace_message
from src.keyboards import library_keyboard
from src.lang import (
    FILTER_SAVE_FAILED,
    INVALID_PAGE,
    LIBRARY_OPEN_FAILED,
    UNKNOWN_FILTER,
    library_text,
)
from src.user_activity import track_user_event

router = Router(name="library_listing")
LIBRARY_PAGE_SIZE = 10


@router.callback_query(MenuState.choosing_library_action, F.data == "menu:library:all")
async def open_library(callback: CallbackQuery, state: FSMContext) -> None:
    if callback.message:
        await track_user_event(callback.from_user.id, "library_open")
        await state.update_data(library_sort="recent", library_filter_group=None)
        await open_library_page(callback, state, 0)


@router.callback_query(F.data.startswith("library:filters:"))
async def open_library_filter_group(
    callback: CallbackQuery,
    state: FSMContext,
) -> None:
    if not callback.data or not callback.message:
        return

    group = parse_library_filter_group_callback(callback.data)
    if group is None:
        await callback.answer(UNKNOWN_FILTER, show_alert=True)
        return
    await state.update_data(library_filter_group=None if group == "back" else group)
    data = await state.get_data()
    await open_library_page(callback, state, int(data.get("library_page", 0)))


@router.callback_query(F.data.startswith("library:filter:"))
async def change_library_filter(callback: CallbackQuery, state: FSMContext) -> None:
    if not callback.data or not callback.message:
        return

    filter_name = parse_library_filter_callback(callback.data)
    if filter_name is None:
        await callback.answer(UNKNOWN_FILTER, show_alert=True)
        return
    try:
        await update_user_library_filter(callback.from_user.id, filter_name)
    except ValueError:
        await callback.answer(UNKNOWN_FILTER, show_alert=True)
        return
    except (aiosqlite.Error, RuntimeError):
        await callback.answer(FILTER_SAVE_FAILED, show_alert=True)
        return

    if filter_name == "all":
        await state.update_data(library_sort="recent", library_filter_group=None)
    await open_library_page(callback, state, 0)


@router.callback_query(F.data.startswith("library:sort:"))
async def change_library_sort(callback: CallbackQuery, state: FSMContext) -> None:
    if not callback.data or not callback.message:
        return

    sort_name = parse_library_sort_callback(callback.data)
    if sort_name is None:
        await callback.answer(UNKNOWN_FILTER, show_alert=True)
        return

    await state.update_data(library_sort=sort_name)
    await open_library_page(callback, state, 0)


@router.callback_query(F.data.startswith("library:page:"))
async def change_library_page(callback: CallbackQuery, state: FSMContext) -> None:
    if not callback.data or not callback.message:
        return

    page = parse_library_page_callback(callback.data)
    if page is None:
        await callback.answer(INVALID_PAGE, show_alert=True)
        return

    await open_library_page(callback, state, page)


@router.callback_query(F.data == "library:back")
async def back_to_library(callback: CallbackQuery, state: FSMContext) -> None:
    if not callback.message:
        return

    data = await state.get_data()
    await open_library_page(callback, state, int(data.get("library_page", 0)))


async def open_library_page(
    callback: CallbackQuery,
    state: FSMContext,
    page: int,
) -> None:
    if not callback.message:
        return

    data = await state.get_data()
    sort_order = data.get("library_sort", "recent")
    if sort_order not in {"recent", "rating", "tmdb_rating", "title"}:
        sort_order = "recent"
    filter_group = data.get("library_filter_group")
    if filter_group not in {"format", "category", "status", "sort"}:
        filter_group = None

    try:
        filters = await get_user_library_filters(callback.from_user.id)
        items = await list_user_library(
            callback.from_user.id,
            filters,
            limit=LIBRARY_PAGE_SIZE + 1,
            offset=page * LIBRARY_PAGE_SIZE,
            sort_order=sort_order,
        )
        library_is_empty = not items and page == 0 and all(filters.values())
        bot_user = await callback.bot.me()
        if not bot_user.username:
            raise RuntimeError("Bot username is unavailable")
    except (aiosqlite.Error, RuntimeError):
        await callback.answer(LIBRARY_OPEN_FAILED, show_alert=True)
        return

    visible_items = items[:LIBRARY_PAGE_SIZE]
    await state.set_state(MenuState.viewing_library)
    library_message = await replace_message(
        callback.message,
        library_text(
            visible_items,
            bot_user.username,
            page * LIBRARY_PAGE_SIZE,
            sort_order,
            library_is_empty=library_is_empty,
        ),
        parse_mode="HTML",
        reply_markup=library_keyboard(
            filters,
            page,
            len(items) > LIBRARY_PAGE_SIZE,
            sort_order,
            filter_group,
        ),
        link_preview_options=LinkPreviewOptions(is_disabled=True),
    )
    await state.update_data(
        library_page=page,
        library_sort=sort_order,
        library_message_id=library_message.message_id,
        library_filter_group=filter_group,
    )
    await callback.answer()
