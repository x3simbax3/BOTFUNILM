"""Library item display and metadata repair helpers."""

import aiosqlite
from aiogram.exceptions import TelegramBadRequest
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from src.database.library import get_user_library_item
from src.database.media import (
    clear_media_telegram_poster_file_id,
    update_media_metadata,
    update_media_telegram_poster_file_id,
)
from src.fsm import MenuState
from src.handlers.common import CAPTION_ELLIPSIS, PHOTO_CAPTION_LIMIT, edit_message
from src.handlers.navigation import reset_to_main, user_main_menu_keyboard
from src.keyboards import library_item_keyboard
from src.lang import (
    DESCRIPTION_NOT_FOUND,
    ITEM_ACTION_FAILED,
    ITEM_NOT_FOUND,
    ITEM_OPEN_FAILED,
    library_item_text,
)
from src.models import current_media_id, is_active_series, is_library_item_editable
from src.posters import poster_input, sent_photo_file_id
from src.tmdb import TmdbError, fetch_title_details


async def show_library_item(
    message: Message,
    state: FSMContext,
    user_id: int,
    media_id: int,
) -> bool:
    try:
        item = await get_user_library_item(user_id, media_id)
    except aiosqlite.Error:
        await _show_library_error(message, state, ITEM_OPEN_FAILED)
        return False

    if item is None:
        await _show_library_error(message, state, ITEM_NOT_FOUND)
        return False

    item, fallback_photo = await _refresh_item_metadata(item)
    text = library_item_caption(item)
    cached_file_id = item.get("telegram_poster_file_id")
    photo = cached_file_id or fallback_photo
    keyboard = library_item_keyboard_for(item)
    if photo:
        try:
            sent_message = await message.answer_photo(
                photo=photo, caption=text, parse_mode="HTML", reply_markup=keyboard
            )
        except TelegramBadRequest:
            if cached_file_id:
                item["telegram_poster_file_id"] = None
                try:
                    await clear_media_telegram_poster_file_id(media_id)
                except aiosqlite.Error:
                    pass
            if cached_file_id and fallback_photo:
                try:
                    sent_message = await message.answer_photo(
                        photo=fallback_photo,
                        caption=text,
                        parse_mode="HTML",
                        reply_markup=keyboard,
                    )
                except TelegramBadRequest:
                    sent_message = await message.answer(
                        text=text, parse_mode="HTML", reply_markup=keyboard
                    )
            else:
                sent_message = await message.answer(
                    text=text, parse_mode="HTML", reply_markup=keyboard
                )
        file_id = sent_photo_file_id(sent_message)
        if file_id and file_id != cached_file_id:
            try:
                await update_media_telegram_poster_file_id(media_id, file_id)
            except aiosqlite.Error:
                pass
    else:
        await message.answer(text=text, parse_mode="HTML", reply_markup=keyboard)
    await state.update_data(media_id=media_id, library_page=0)
    await state.set_state(MenuState.viewing_media)
    return True


async def current_library_item(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    media_id = current_media_id(data)
    if media_id is None:
        await callback.answer(ITEM_NOT_FOUND, show_alert=True)
        return None
    try:
        item = await get_user_library_item(callback.from_user.id, media_id)
    except aiosqlite.Error:
        await callback.answer(ITEM_ACTION_FAILED, show_alert=True)
        return None
    if item is None:
        await callback.answer(ITEM_NOT_FOUND, show_alert=True)
    return item


async def edit_library_item_message(message: Message, item) -> None:
    await edit_message(
        message,
        library_item_caption(item),
        parse_mode="HTML",
        reply_markup=library_item_keyboard_for(item),
    )


def library_item_keyboard_for(item):
    return library_item_keyboard(
        planned=item["user_status"] == "planned",
        released=bool(dict(item).get("is_released", True)),
        editable=is_library_item_editable(item),
        tracking_available=(
            item["content_format"] == "series"
            and is_active_series(item["tmdb_status"], item["tmdb_in_production"])
        ),
        tracking_enabled=bool(dict(item).get("is_tracking", False)),
    )


async def _refresh_item_metadata(item):
    """Repair missing movie artwork without refreshing series on card open."""
    refreshed = dict(item)
    photo = poster_input(refreshed.get("poster_path"))
    has_photo = bool(refreshed.get("telegram_poster_file_id")) or photo is not None
    if refreshed.get("tmdb_id") in {None, 0}:
        return refreshed, photo

    if refreshed.get("content_format") != "series" and (
        not has_photo or refreshed.get("rating") is None
    ):
        try:
            details = await fetch_title_details(
                int(refreshed["tmdb_id"]), refreshed["content_format"]
            )
        except (TmdbError, ValueError):
            pass
        else:
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
                        int(refreshed["id"]), poster_path=poster_path, rating=rating
                    )
                except aiosqlite.Error:
                    pass
    return refreshed, photo


async def _show_library_error(message: Message, state: FSMContext, text: str) -> None:
    await message.answer(
        text, reply_markup=await user_main_menu_keyboard(message.from_user.id)
    )
    await reset_to_main(state)


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
