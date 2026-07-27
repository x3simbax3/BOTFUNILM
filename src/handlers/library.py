"""User library browsing and deep-link handlers."""

import aiosqlite
from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from src.callback_data import (
    parse_library_filter_callback,
    parse_library_page_callback,
    parse_library_sort_callback,
)
from src.database.library import (
    get_user_library_filters,
    get_user_library_item,
    list_user_library,
    update_user_library_filter,
)
from src.database.media import update_media_metadata
from src.fsm import MenuState
from src.handlers.common import CAPTION_ELLIPSIS, PHOTO_CAPTION_LIMIT, replace_message
from src.keyboards import (
    library_item_keyboard,
    library_keyboard,
    main_menu_keyboard,
)
from src.lang import (
    DESCRIPTION_NOT_FOUND,
    FILTER_SAVE_FAILED,
    INVALID_PAGE,
    ITEM_NOT_FOUND,
    ITEM_OPEN_FAILED,
    LIBRARY_OPEN_FAILED,
    UNKNOWN_FILTER,
    library_item_text,
    library_text,
)
from src.posters import poster_input
from src.tmdb import TmdbError, fetch_title_details

router = Router(name="library")
LIBRARY_PAGE_SIZE = 20


@router.callback_query(F.data == "menu:library")
async def open_library(callback: CallbackQuery, state: FSMContext) -> None:
    if callback.message:
        await state.update_data(library_sort="recent")
        await open_library_page(callback, state, 0)


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
    if sort_order not in {"recent", "rating"}:
        sort_order = "recent"

    try:
        filters = await get_user_library_filters(callback.from_user.id)
        items = await list_user_library(
            callback.from_user.id,
            filters,
            limit=LIBRARY_PAGE_SIZE + 1,
            offset=page * LIBRARY_PAGE_SIZE,
            sort_order=sort_order,
        )
        bot_user = await callback.bot.get_me()
        if not bot_user.username:
            raise RuntimeError("Bot username is unavailable")
    except (aiosqlite.Error, RuntimeError):
        await callback.answer(LIBRARY_OPEN_FAILED, show_alert=True)
        return

    visible_items = items[:LIBRARY_PAGE_SIZE]
    await state.update_data(library_page=page, library_sort=sort_order)
    await state.set_state(MenuState.viewing_library)
    await replace_message(
        callback.message,
        library_text(
            visible_items,
            bot_user.username,
            page * LIBRARY_PAGE_SIZE,
            sort_order,
        ),
        parse_mode="HTML",
        reply_markup=library_keyboard(
            filters,
            page,
            len(items) > LIBRARY_PAGE_SIZE,
            sort_order,
        ),
    )
    await callback.answer()


async def show_library_item(
    message: Message,
    state: FSMContext,
    user_id: int,
    media_id: int,
) -> None:
    try:
        item = await get_user_library_item(user_id, media_id)
    except aiosqlite.Error:
        await _show_library_error(message, state, ITEM_OPEN_FAILED)
        return

    if item is None:
        await _show_library_error(message, state, ITEM_NOT_FOUND)
        return

    item, photo = await _refresh_item_metadata(item)
    text = library_item_caption(item)
    send = message.answer_photo if photo else message.answer
    content = {"caption": text, "photo": photo} if photo else {"text": text}
    await send(
        **content,
        parse_mode="HTML",
        reply_markup=library_item_keyboard(),
    )
    await state.update_data(media_id=media_id, library_page=0)
    await state.set_state(MenuState.viewing_media)


async def _refresh_item_metadata(item):
    """Repair missing TMDB rating or poster when an old item is opened."""
    refreshed = dict(item)
    photo = poster_input(refreshed.get("poster_path"))
    if (
        refreshed.get("tmdb_id") in {None, 0}
        or (photo is not None and refreshed.get("rating") is not None)
    ):
        return refreshed, photo

    try:
        details = await fetch_title_details(
            int(refreshed["tmdb_id"]),
            refreshed["content_format"],
        )
    except (TmdbError, ValueError):
        return refreshed, photo

    poster_path = None
    if photo is None and details.poster_path:
        poster_path = details.poster_path
        refreshed["poster_path"] = poster_path
        photo = poster_input(poster_path)
    rating = None
    if refreshed.get("rating") is None and details.rating is not None:
        rating = details.rating
        refreshed["rating"] = rating
    if poster_path is not None or rating is not None:
        try:
            await update_media_metadata(
                int(refreshed["id"]),
                poster_path=poster_path,
                rating=rating,
            )
        except aiosqlite.Error:
            pass
    return refreshed, photo


async def _show_library_error(
    message: Message,
    state: FSMContext,
    text: str,
) -> None:
    await message.answer(text, reply_markup=main_menu_keyboard())
    await state.set_state(MenuState.choosing_action)


def media_id_from_start(text: str | None) -> int | None:
    if not text or not text.startswith("/start media_"):
        return None

    value = text.removeprefix("/start media_").strip()
    if not value.isdigit():
        return None
    media_id = int(value)
    return media_id if media_id > 0 else None


def library_item_caption(item) -> str:
    text = library_item_text(item)
    if len(text) <= PHOTO_CAPTION_LIMIT:
        return text

    description = item["description"] or DESCRIPTION_NOT_FOUND
    low, high = 0, len(description)
    best = library_item_text(item, CAPTION_ELLIPSIS)
    while low <= high:
        middle = (low + high) // 2
        clipped = description[:middle].rstrip()
        if middle < len(description):
            clipped += CAPTION_ELLIPSIS
        candidate = library_item_text(item, clipped)
        if len(candidate) <= PHOTO_CAPTION_LIMIT:
            best = candidate
            low = middle + 1
        else:
            high = middle - 1
    return best
