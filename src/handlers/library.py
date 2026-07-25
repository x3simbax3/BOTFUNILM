"""User library browsing and deep-link handlers."""

import aiosqlite
from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from src.callback_data import (
    parse_library_filter_callback,
    parse_library_page_callback,
)
from src.database.library import (
    get_user_library_filters,
    get_user_library_item,
    list_user_library,
    update_user_library_filter,
)
from src.fsm import MenuState
from src.handlers.common import CAPTION_ELLIPSIS, PHOTO_CAPTION_LIMIT, replace_message
from src.keyboards import (
    library_item_keyboard,
    library_keyboard,
    main_menu_keyboard,
)
from src.posters import poster_input
from src.texts import library_item_text, library_text


router = Router(name="library")
LIBRARY_PAGE_SIZE = 20


@router.callback_query(F.data == "menu:library")
async def open_library(callback: CallbackQuery, state: FSMContext) -> None:
    if callback.message:
        await open_library_page(callback, state, 0)


@router.callback_query(F.data.startswith("library:filter:"))
async def change_library_filter(callback: CallbackQuery, state: FSMContext) -> None:
    if not callback.data or not callback.message:
        return

    filter_name = parse_library_filter_callback(callback.data)
    if filter_name is None:
        await callback.answer("Неизвестный фильтр", show_alert=True)
        return
    try:
        await update_user_library_filter(callback.from_user.id, filter_name)
    except ValueError:
        await callback.answer("Неизвестный фильтр", show_alert=True)
        return
    except (aiosqlite.Error, RuntimeError):
        await callback.answer("Не удалось сохранить фильтр", show_alert=True)
        return

    await open_library_page(callback, state, 0)


@router.callback_query(F.data.startswith("library:page:"))
async def change_library_page(callback: CallbackQuery, state: FSMContext) -> None:
    if not callback.data or not callback.message:
        return

    page = parse_library_page_callback(callback.data)
    if page is None:
        await callback.answer("Некорректная страница", show_alert=True)
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

    try:
        filters = await get_user_library_filters(callback.from_user.id)
        items = await list_user_library(
            callback.from_user.id,
            filters,
            limit=LIBRARY_PAGE_SIZE + 1,
            offset=page * LIBRARY_PAGE_SIZE,
        )
        bot_user = await callback.bot.get_me()
        if not bot_user.username:
            raise RuntimeError("Bot username is unavailable")
    except (aiosqlite.Error, RuntimeError):
        await callback.answer("Не удалось открыть библиотеку", show_alert=True)
        return

    visible_items = items[:LIBRARY_PAGE_SIZE]
    await state.update_data(library_page=page)
    await state.set_state(MenuState.viewing_library)
    await replace_message(
        callback.message,
        library_text(visible_items, bot_user.username, page * LIBRARY_PAGE_SIZE),
        parse_mode="HTML",
        reply_markup=library_keyboard(
            filters,
            page,
            len(items) > LIBRARY_PAGE_SIZE,
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
        await _show_library_error(message, state, "Не удалось открыть тайтл. Попробуй ещё раз.")
        return

    if item is None:
        await _show_library_error(message, state, "Тайтл не найден в твоей библиотеке.")
        return

    text = library_item_caption(item)
    photo = poster_input(item["poster_path"])
    send = message.answer_photo if photo else message.answer
    content = {"caption": text, "photo": photo} if photo else {"text": text}
    await send(
        **content,
        parse_mode="HTML",
        reply_markup=library_item_keyboard(),
    )
    await state.update_data(media_id=media_id, library_page=0)
    await state.set_state(MenuState.viewing_media)


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

    description = item["description"] or "Описание не найдено."
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
