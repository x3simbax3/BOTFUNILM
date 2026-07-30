"""Main menu, content selection and backward navigation handlers."""

from aiogram import F, Router
from aiogram.exceptions import TelegramAPIError
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from src.callback_data import (
    parse_back_callback,
    parse_format_callback,
    parse_type_callback,
)
from src.database.bot_users import register_bot_user
from src.fsm import MenuState
from src.handlers.common import replace_message
from src.handlers.library import media_id_from_start, show_library_item
from src.handlers.navigation import reset_to_main
from src.keyboards import (
    content_type_keyboard,
    format_keyboard,
    main_menu_keyboard,
    selected_type_keyboard,
)
from src.lang import (
    BACK_FAILED,
    ENTER_TITLE_AGAIN,
    INVALID_SELECTION,
    SELECTION_SAVED,
    START_TEXT,
    UNKNOWN_STEP,
    action_text,
    content_type_text,
    selected_type_text,
)

router = Router(name="menu")

MENU_TREE = {
    "main": {
        "state": MenuState.choosing_action,
        "clear_fields": ("action", "content_format", "content_type"),
        "required_fields": (),
        "param_fields": (),
        "text": lambda data: START_TEXT,
        "keyboard": lambda data: main_menu_keyboard(),
    },
    "format": {
        "state": MenuState.choosing_format,
        "clear_fields": ("content_format", "content_type"),
        "required_fields": ("action",),
        "param_fields": ("action",),
        "text": lambda data: action_text(data["action"]),
        "keyboard": lambda data: format_keyboard(data["action"]),
    },
    "content_type": {
        "state": MenuState.choosing_content_type,
        "clear_fields": ("content_type",),
        "required_fields": ("action", "content_format"),
        "param_fields": ("action", "content_format"),
        "text": lambda data: content_type_text(data["action"], data["content_format"]),
        "keyboard": lambda data: content_type_keyboard(
            data["action"],
            data["content_format"],
        ),
    },
}


@router.message(CommandStart())
async def start(message: Message, state: FSMContext) -> None:
    await register_bot_user(message.from_user.id)
    previous_data = dict(await state.get_data())
    media_id = media_id_from_start(message.text)
    if media_id is not None:
        await state.clear()
        opened = await show_library_item(message, state, message.from_user.id, media_id)
        library_message_id = previous_data.get("library_message_id")
        if opened and type(library_message_id) is int and library_message_id > 0:
            try:
                await message.bot.delete_message(
                    chat_id=message.chat.id,
                    message_id=library_message_id,
                )
            except TelegramAPIError:
                pass
        return

    await reset_to_main(state)
    await message.answer(
        START_TEXT,
        parse_mode="HTML",
        reply_markup=main_menu_keyboard(),
    )


@router.callback_query(F.data == "menu:add")
async def choose_action(callback: CallbackQuery, state: FSMContext) -> None:
    if not callback.data or not callback.message:
        return

    action = "add"
    await state.update_data(action=action)
    await state.set_state(MenuState.choosing_format)
    await callback.message.edit_text(
        action_text(action),
        parse_mode="HTML",
        reply_markup=format_keyboard(action),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("format:"))
async def choose_format(callback: CallbackQuery, state: FSMContext) -> None:
    if not callback.data or not callback.message:
        return

    parsed = parse_format_callback(callback.data)
    if parsed is None:
        await callback.answer(INVALID_SELECTION, show_alert=True)
        return
    action, content_format = parsed.action, parsed.content_format
    await state.update_data(action=action, content_format=content_format)
    await state.set_state(MenuState.choosing_content_type)
    await callback.message.edit_text(
        content_type_text(action, content_format),
        parse_mode="HTML",
        reply_markup=content_type_keyboard(action, content_format),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("type:"))
async def choose_content_type(callback: CallbackQuery, state: FSMContext) -> None:
    if not callback.data or not callback.message:
        return

    parsed = parse_type_callback(callback.data)
    if parsed is None:
        await callback.answer(INVALID_SELECTION, show_alert=True)
        return
    action = parsed.action
    content_format = parsed.content_format
    content_type = parsed.content_type
    await state.update_data(
        action=action,
        content_format=content_format,
        content_type=content_type,
    )
    await state.set_state(MenuState.waiting_title)
    await callback.message.edit_text(
        selected_type_text(action, content_format, content_type),
        parse_mode="HTML",
        reply_markup=selected_type_keyboard(action, content_format),
    )
    await callback.answer(SELECTION_SAVED)


@router.callback_query(MenuState.choosing_tmdb_retry, F.data == "title:retry")
async def retry_title(callback: CallbackQuery, state: FSMContext) -> None:
    if not callback.message:
        return

    await state.set_state(MenuState.waiting_title)
    await replace_message(callback.message, ENTER_TITLE_AGAIN)
    await callback.answer()


@router.callback_query(F.data.startswith("back:"))
async def go_back(callback: CallbackQuery, state: FSMContext) -> None:
    if not callback.data or not callback.message:
        return

    parsed = parse_back_callback(callback.data)
    if parsed is None:
        await callback.answer(UNKNOWN_STEP, show_alert=True)
        return
    target_step, params = parsed.target_step, parsed.params
    step = MENU_TREE.get(target_step)
    if not step:
        await callback.answer(UNKNOWN_STEP, show_alert=True)
        return

    data = await state.get_data()
    data.update(zip(step["param_fields"], params, strict=False))
    clear_step_data(data, target_step)
    if any(not data.get(field) for field in step["required_fields"]):
        await callback.answer(BACK_FAILED, show_alert=True)
        return

    await state.set_data(data)
    await state.set_state(step["state"])
    await replace_message(
        callback.message,
        step["text"](data),
        parse_mode="HTML",
        reply_markup=step["keyboard"](data),
    )
    await callback.answer()


def clear_step_data(data: dict, target_step: str) -> None:
    if target_step == "main":
        data.clear()
        return

    for field in MENU_TREE[target_step]["clear_fields"]:
        data.pop(field, None)
