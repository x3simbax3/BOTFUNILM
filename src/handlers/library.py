"""User library browsing and deep-link handlers."""

import aiosqlite
from aiogram import F, Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, LinkPreviewOptions, Message

from src.callback_data import (
    parse_badge_callback,
    parse_library_filter_callback,
    parse_library_filter_group_callback,
    parse_library_page_callback,
    parse_library_sort_callback,
)
from src.database.library import (
    get_user_library_filters,
    get_user_library_item,
    list_user_library,
    update_user_library_filter,
)
from src.database.media import (
    clear_media_telegram_poster_file_id,
    update_media_metadata,
    update_media_telegram_poster_file_id,
)
from src.database.user_media import (
    delete_user_media,
    set_user_media_status,
    update_user_media_badge,
)
from src.fsm import MenuState
from src.handlers.common import (
    CAPTION_ELLIPSIS,
    PHOTO_CAPTION_LIMIT,
    delete_message_safely,
    edit_message,
    replace_message,
)
from src.handlers.navigation import reset_to_main
from src.handlers.series import start_series_tracking
from src.keyboards import (
    badge_keyboard,
    library_delete_keyboard,
    library_edit_keyboard,
    library_item_keyboard,
    library_keyboard,
    main_menu_keyboard,
    rating_keyboard,
)
from src.lang import (
    BADGE_UPDATED,
    DESCRIPTION_NOT_FOUND,
    FILTER_SAVE_FAILED,
    INVALID_BADGE,
    INVALID_PAGE,
    ITEM_ACTION_FAILED,
    ITEM_DELETE_PROMPT,
    ITEM_DELETED,
    ITEM_EDIT_PROMPT,
    ITEM_MARKED_WATCHED,
    ITEM_NOT_FOUND,
    ITEM_OPEN_FAILED,
    LIBRARY_OPEN_FAILED,
    UNKNOWN_FILTER,
    UNRELEASED_TITLE,
    badge_prompt_text,
    library_item_text,
    library_text,
    rating_categories,
    rating_prompt_text,
)
from src.models import (
    MediaWorkflowData,
    SeriesReleaseSnapshot,
    current_media_id,
    is_active_series,
    is_library_item_editable,
)
from src.posters import poster_input, sent_photo_file_id
from src.tmdb import TmdbError, fetch_title_details

router = Router(name="library")
LIBRARY_PAGE_SIZE = 10


@router.callback_query(F.data == "menu:library")
async def open_library(callback: CallbackQuery, state: FSMContext) -> None:
    if callback.message:
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
    keyboard = library_item_keyboard(
        planned=item["user_status"] == "planned",
        released=bool(dict(item).get("is_released", True)),
        editable=is_library_item_editable(item),
        tracking_available=(
            item["content_format"] == "series"
            and is_active_series(item["tmdb_status"], item["tmdb_in_production"])
        ),
        tracking_enabled=bool(dict(item).get("is_tracking", False)),
    )
    if photo:
        try:
            sent_message = await message.answer_photo(
                photo=photo,
                caption=text,
                parse_mode="HTML",
                reply_markup=keyboard,
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
                        text=text,
                        parse_mode="HTML",
                        reply_markup=keyboard,
                    )
            else:
                sent_message = await message.answer(
                    text=text,
                    parse_mode="HTML",
                    reply_markup=keyboard,
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


@router.callback_query(MenuState.viewing_media, F.data == "library:item:edit")
async def open_library_item_edit(callback: CallbackQuery, state: FSMContext) -> None:
    if not callback.message:
        return
    item = await _current_library_item(callback, state)
    if item is None:
        return
    if not is_library_item_editable(item):
        await callback.answer(ITEM_ACTION_FAILED, show_alert=True)
        return
    await edit_message(
        callback.message,
        ITEM_EDIT_PROMPT,
        reply_markup=library_edit_keyboard(
            series=item["content_format"] == "series",
            released=bool(dict(item).get("is_released", True)),
        ),
    )
    await callback.answer()


@router.callback_query(
    MenuState.viewing_media,
    F.data == "library:item:edit:badge",
)
async def open_library_item_badge(callback: CallbackQuery, state: FSMContext) -> None:
    if not callback.message:
        return
    item = await _current_library_item(callback, state)
    if item is None:
        return
    if not is_library_item_editable(item):
        await callback.answer(ITEM_ACTION_FAILED, show_alert=True)
        return
    await edit_message(
        callback.message,
        badge_prompt_text(item["title"]),
        parse_mode="HTML",
        reply_markup=badge_keyboard("library_badge"),
    )
    await state.set_state(MenuState.choosing_badge)
    await callback.answer()


@router.callback_query(
    MenuState.choosing_badge,
    F.data.startswith("library_badge:"),
)
async def change_library_item_badge(
    callback: CallbackQuery,
    state: FSMContext,
) -> None:
    if not callback.data or not callback.message:
        return
    item = await _current_library_item(callback, state)
    if item is None:
        return
    if not is_library_item_editable(item):
        await callback.answer(ITEM_ACTION_FAILED, show_alert=True)
        return

    value = parse_badge_callback(callback.data)
    if value is None:
        await callback.answer(INVALID_BADGE, show_alert=True)
        return
    if value == "back":
        await edit_message(
            callback.message,
            ITEM_EDIT_PROMPT,
            reply_markup=library_edit_keyboard(
                series=item["content_format"] == "series",
                released=bool(dict(item).get("is_released", True)),
            ),
        )
        await state.set_state(MenuState.viewing_media)
        await callback.answer()
        return

    badge = None if value == "none" else value
    try:
        updated = await update_user_media_badge(
            callback.from_user.id,
            int(item["id"]),
            badge,
        )
        if not updated:
            raise RuntimeError("Library item disappeared")
        refreshed = await get_user_library_item(
            callback.from_user.id,
            int(item["id"]),
        )
    except (aiosqlite.Error, RuntimeError, ValueError):
        await callback.answer(ITEM_ACTION_FAILED, show_alert=True)
        return
    if refreshed is None:
        await callback.answer(ITEM_NOT_FOUND, show_alert=True)
        return
    await _edit_library_item_message(callback.message, refreshed)
    await state.set_state(MenuState.viewing_media)
    await callback.answer(BADGE_UPDATED)


@router.callback_query(
    MenuState.viewing_media,
    F.data == "library:item:edit:back",
)
async def back_from_library_item_edit(
    callback: CallbackQuery,
    state: FSMContext,
) -> None:
    if not callback.message:
        return
    item = await _current_library_item(callback, state)
    if item is None:
        return
    await _edit_library_item_message(callback.message, item)
    await callback.answer()


@router.callback_query(
    MenuState.viewing_media,
    F.data == "library:item:edit:rating",
)
async def edit_library_item_rating(
    callback: CallbackQuery,
    state: FSMContext,
) -> None:
    if not callback.message:
        return
    item = await _current_library_item(callback, state)
    if item is None:
        return
    if not is_library_item_editable(item) or not bool(
        dict(item).get("is_released", True)
    ):
        await callback.answer(UNRELEASED_TITLE, show_alert=True)
        return
    categories = rating_categories(item["content_type"])
    await state.update_data(
        **MediaWorkflowData.from_library_item(item).to_fsm_dict(),
        ratings={},
        rating_index=0,
        library_rating_edit=True,
    )
    await state.set_state(MenuState.rating_category)
    await replace_message(
        callback.message,
        rating_prompt_text(item["title"], categories[0][1], 1, len(categories)),
        parse_mode="HTML",
        reply_markup=rating_keyboard(),
    )
    await callback.answer()


@router.callback_query(
    MenuState.viewing_media,
    F.data.in_({"library:item:watched", "library:item:edit:progress"}),
)
async def change_library_item_progress(
    callback: CallbackQuery,
    state: FSMContext,
) -> None:
    if not callback.message:
        return
    item = await _current_library_item(callback, state)
    if item is None:
        return
    if not bool(dict(item).get("is_released", True)):
        await callback.answer(UNRELEASED_TITLE, show_alert=True)
        return
    if callback.data == "library:item:edit:progress" and not is_library_item_editable(
        item
    ):
        await callback.answer(ITEM_ACTION_FAILED, show_alert=True)
        return

    if item["content_format"] == "series":
        await state.update_data(
            **MediaWorkflowData.from_library_item(item).to_fsm_dict(),
            **SeriesReleaseSnapshot.from_library_item(item).to_fsm_dict(),
            rating_average=item["user_rating"],
            library_rating_edit=False,
            library_progress_edit=True,
        )
        await delete_message_safely(callback.message)
        await start_series_tracking(callback, state)
        await callback.answer()
        return

    if callback.data != "library:item:watched" or item["user_status"] != "planned":
        await callback.answer(ITEM_ACTION_FAILED, show_alert=True)
        return
    try:
        updated = await set_user_media_status(
            callback.from_user.id,
            int(item["id"]),
            "completed",
        )
        if not updated:
            raise RuntimeError("Library item disappeared")
        refreshed = await get_user_library_item(callback.from_user.id, int(item["id"]))
    except (aiosqlite.Error, RuntimeError, ValueError):
        await callback.answer(ITEM_ACTION_FAILED, show_alert=True)
        return
    if refreshed is None:
        await callback.answer(ITEM_NOT_FOUND, show_alert=True)
        return
    await _edit_library_item_message(callback.message, refreshed)
    await callback.answer(ITEM_MARKED_WATCHED)


@router.callback_query(MenuState.viewing_media, F.data == "library:item:delete")
async def confirm_library_item_delete(
    callback: CallbackQuery,
    state: FSMContext,
) -> None:
    if not callback.message:
        return
    if await _current_library_item(callback, state) is None:
        return
    await edit_message(
        callback.message,
        ITEM_DELETE_PROMPT,
        reply_markup=library_delete_keyboard(),
    )
    await callback.answer()


@router.callback_query(
    MenuState.viewing_media,
    F.data == "library:item:delete:cancel",
)
async def cancel_library_item_delete(
    callback: CallbackQuery,
    state: FSMContext,
) -> None:
    await back_from_library_item_edit(callback, state)


@router.callback_query(
    MenuState.viewing_media,
    F.data == "library:item:delete:confirm",
)
async def delete_library_item(callback: CallbackQuery, state: FSMContext) -> None:
    if not callback.message:
        return
    data = await state.get_data()
    media_id = current_media_id(data)
    if media_id is None:
        await callback.answer(ITEM_NOT_FOUND, show_alert=True)
        return
    try:
        deleted = await delete_user_media(callback.from_user.id, media_id)
    except aiosqlite.Error:
        await callback.answer(ITEM_ACTION_FAILED, show_alert=True)
        return
    if not deleted:
        await callback.answer(ITEM_NOT_FOUND, show_alert=True)
        return
    await replace_message(
        callback.message,
        ITEM_DELETED,
        reply_markup=main_menu_keyboard(),
    )
    await reset_to_main(state)
    await callback.answer()


async def _current_library_item(callback: CallbackQuery, state: FSMContext):
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


async def _edit_library_item_message(message: Message, item) -> None:
    await edit_message(
        message,
        library_item_caption(item),
        parse_mode="HTML",
        reply_markup=library_item_keyboard(
            planned=item["user_status"] == "planned",
            released=bool(dict(item).get("is_released", True)),
            editable=is_library_item_editable(item),
            tracking_available=(
                item["content_format"] == "series"
                and is_active_series(item["tmdb_status"], item["tmdb_in_production"])
            ),
            tracking_enabled=bool(dict(item).get("is_tracking", False)),
        ),
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
                int(refreshed["tmdb_id"]),
                refreshed["content_format"],
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
