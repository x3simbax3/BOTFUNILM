"""Library item editing, progress and deletion handlers."""

import aiosqlite
from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery

from src.callback_data import parse_badge_callback
from src.database.library import get_user_library_item
from src.database.user_media import (
    delete_user_media,
    set_user_media_status,
    update_user_media_badge,
)
from src.fsm import MenuState
from src.handlers.common import delete_message_safely, edit_message, replace_message
from src.handlers.navigation import reset_to_main, user_main_menu_keyboard
from src.handlers.series import start_series_tracking
from src.keyboards import (
    badge_keyboard,
    library_delete_keyboard,
    library_edit_keyboard,
    rating_keyboard,
)
from src.lang import (
    BADGE_UPDATED,
    INVALID_BADGE,
    ITEM_ACTION_FAILED,
    ITEM_DELETE_PROMPT,
    ITEM_DELETED,
    ITEM_EDIT_PROMPT,
    ITEM_MARKED_WATCHED,
    ITEM_NOT_FOUND,
    UNRELEASED_TITLE,
    badge_prompt_text,
    rating_categories,
    rating_prompt_text,
)
from src.models import (
    MediaWorkflowData,
    SeriesReleaseSnapshot,
    current_media_id,
    is_library_item_editable,
)

from .item import current_library_item, edit_library_item_message

router = Router(name="library_actions")


@router.callback_query(MenuState.viewing_media, F.data == "library:item:edit")
async def open_library_item_edit(callback: CallbackQuery, state: FSMContext) -> None:
    if not callback.message:
        return
    item = await current_library_item(callback, state)
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
    item = await current_library_item(callback, state)
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
    item = await current_library_item(callback, state)
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
        refreshed = await get_user_library_item(callback.from_user.id, int(item["id"]))
    except (aiosqlite.Error, RuntimeError, ValueError):
        await callback.answer(ITEM_ACTION_FAILED, show_alert=True)
        return
    if refreshed is None:
        await callback.answer(ITEM_NOT_FOUND, show_alert=True)
        return
    await edit_library_item_message(callback.message, refreshed)
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
    item = await current_library_item(callback, state)
    if item is None:
        return
    await edit_library_item_message(callback.message, item)
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
    item = await current_library_item(callback, state)
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
    item = await current_library_item(callback, state)
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
            callback.from_user.id, int(item["id"]), "completed"
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
    await edit_library_item_message(callback.message, refreshed)
    await callback.answer(ITEM_MARKED_WATCHED)


@router.callback_query(MenuState.viewing_media, F.data == "library:item:delete")
async def confirm_library_item_delete(
    callback: CallbackQuery,
    state: FSMContext,
) -> None:
    if not callback.message:
        return
    if await current_library_item(callback, state) is None:
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
        reply_markup=await user_main_menu_keyboard(callback.from_user.id),
    )
    await reset_to_main(state)
    await callback.answer()
