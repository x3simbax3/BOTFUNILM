from aiogram import F, Router
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from src.fsm import MenuState
from src.keyboards import (
    content_type_keyboard,
    format_keyboard,
    main_menu_keyboard,
    selected_type_keyboard,
    tmdb_guess_keyboard,
    tmdb_retry_keyboard,
)
from src.texts import (
    START_TEXT,
    TMDB_SEARCHING,
    TMDB_TOO_LONG,
    action_text,
    content_type_text,
    selected_type_text,
    tmdb_found_text,
    tmdb_guess_text,
    tmdb_not_found_text,
)
from src.tmdb import (
    TmdbError,
    TmdbNotConfiguredError,
    TmdbNotFoundError,
    find_title_guess,
)

router = Router(name="start")


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

PHOTO_CAPTION_LIMIT = 1024
CAPTION_ELLIPSIS = "…"


@router.message(CommandStart())
async def start(message: Message, state: FSMContext) -> None:
    await state.clear()
    await state.set_state(MenuState.choosing_action)
    await message.answer(
        START_TEXT,
        parse_mode="HTML",
        reply_markup=main_menu_keyboard(),
    )


@router.callback_query(F.data.in_({"menu:library", "menu:add"}))
async def choose_action(callback: CallbackQuery, state: FSMContext) -> None:
    if not callback.data or not callback.message:
        return

    action = callback.data.split(":")[1]
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

    _, action, content_format = callback.data.split(":")
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

    _, action, content_format, content_type = callback.data.split(":")
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
    await callback.answer("Выбор сохранен")


@router.message(MenuState.waiting_title)
async def search_title(message: Message, state: FSMContext) -> None:
    if not message.text:
        await message.answer("Введи название текстом.")
        return

    data = await state.get_data()
    content_format = data.get("content_format")
    if not content_format:
        await message.answer("Не найден выбранный формат. Начни заново через /start.")
        return

    title_query = message.text
    if not title_query.strip():
        await message.answer("Название не может быть пустым. Введи название ещё раз.")
        return

    if len(title_query) > 342:
        await message.answer(TMDB_TOO_LONG)
        return

    status_msg = await message.answer(TMDB_SEARCHING, parse_mode="HTML")

    try:
        content_type = data.get("content_type", "movie")
        guess = await find_title_guess(title_query, content_format, content_type)
    except ValueError:
        await status_msg.edit_text("Название не может быть пустым. Введи название ещё раз.")
        return
    except TmdbNotConfiguredError:
        await status_msg.edit_text("TMDB_API не настроен. Добавь ключ в config/.env.")
        return
    except TmdbNotFoundError:
        await status_msg.edit_text(
            tmdb_not_found_text(title_query),
            parse_mode="HTML",
        )
        return
    except TmdbError:
        await status_msg.edit_text("Не удалось получить ответ от TMDB. Попробуй позже.")
        return

    await status_msg.edit_text(
        tmdb_found_text(guess.title),
        parse_mode="HTML"
    )

    text = _tmdb_guess_caption(content_format, guess.title, guess.overview)

    if guess.poster_url:
        guess_message = await message.answer_photo(
            photo=guess.poster_url,
            caption=text,
            parse_mode="HTML",
            reply_markup=tmdb_guess_keyboard(),
        )
        await state.update_data(tmdb_guess_message_id=guess_message.message_id)
        await state.set_state(MenuState.confirming_tmdb_guess)
        return

    guess_message = await message.answer(
        text,
        parse_mode="HTML",
        reply_markup=tmdb_guess_keyboard(),
    )
    await state.update_data(tmdb_guess_message_id=guess_message.message_id)
    await state.set_state(MenuState.confirming_tmdb_guess)


@router.callback_query(MenuState.confirming_tmdb_guess, F.data == "tmdb_guess:yes")
async def confirm_tmdb_guess(callback: CallbackQuery, state: FSMContext) -> None:
    if not await _is_active_tmdb_guess(callback, state):
        await callback.answer("Это старый вариант.")
        return

    await callback.answer()


@router.callback_query(MenuState.confirming_tmdb_guess, F.data == "tmdb_guess:no")
async def reject_tmdb_guess(callback: CallbackQuery, state: FSMContext) -> None:
    if not callback.message:
        return

    if not await _is_active_tmdb_guess(callback, state):
        await callback.answer("Это старый вариант.")
        return

    await state.set_state(MenuState.choosing_tmdb_retry)
    await state.update_data(tmdb_guess_message_id=None)
    data = await state.get_data()
    await callback.message.answer(
        "Ок, не оно. Что сделать?",
        reply_markup=tmdb_retry_keyboard(
            data.get("action"),
            data.get("content_format"),
        ),
    )
    await callback.answer()


@router.callback_query(MenuState.choosing_tmdb_retry, F.data == "title:retry")
async def retry_title(callback: CallbackQuery, state: FSMContext) -> None:
    if not callback.message:
        return

    await state.set_state(MenuState.waiting_title)
    await _replace_message(callback.message, "Введи название ещё раз.")
    await callback.answer()


@router.callback_query(F.data.startswith("back:"))
async def go_back(callback: CallbackQuery, state: FSMContext) -> None:
    if not callback.data or not callback.message:
        return

    _, target_step, *params = callback.data.split(":")
    step = MENU_TREE.get(target_step)
    if not step:
        await callback.answer("Неизвестный шаг", show_alert=True)
        return

    data = await state.get_data()
    data.update(zip(step["param_fields"], params))

    _clear_step_data(data, target_step)

    if any(not data.get(field) for field in step["required_fields"]):
        await callback.answer("Не удалось вернуться назад", show_alert=True)
        return

    await state.set_data(data)
    await state.set_state(step["state"])

    await _replace_message(
        callback.message,
        step["text"](data),
        parse_mode="HTML",
        reply_markup=step["keyboard"](data),
    )
    await callback.answer()


def _clear_step_data(data: dict, target_step: str) -> None:
    for field in MENU_TREE[target_step]["clear_fields"]:
        data.pop(field, None)


async def _edit_message(
    message: Message,
    text: str,
    parse_mode: str | None = None,
    reply_markup=None,
) -> None:
    if message.photo:
        await message.edit_caption(
            caption=text,
            parse_mode=parse_mode,
            reply_markup=reply_markup,
        )
        return

    await message.edit_text(
        text,
        parse_mode=parse_mode,
        reply_markup=reply_markup,
    )


async def _is_active_tmdb_guess(callback: CallbackQuery, state: FSMContext) -> bool:
    if not callback.message:
        return False

    data = await state.get_data()
    return callback.message.message_id == data.get("tmdb_guess_message_id")


async def _replace_message(
    message: Message,
    text: str,
    parse_mode: str | None = None,
    reply_markup=None,
) -> None:
    if message.photo:
        await message.delete()
        await message.answer(
            text,
            parse_mode=parse_mode,
            reply_markup=reply_markup,
        )
        return

    await _edit_message(
        message,
        text,
        parse_mode=parse_mode,
        reply_markup=reply_markup,
    )


def _tmdb_guess_caption(
    content_format: str,
    title: str,
    overview: str | None,
) -> str:
    description = overview or "Описание не найдено."
    caption_without_description = tmdb_guess_text(content_format, title, "")
    description_limit = PHOTO_CAPTION_LIMIT - len(caption_without_description)

    return tmdb_guess_text(
        content_format,
        title,
        _limit_caption_description(description, description_limit),
    )


def _limit_caption_description(description: str, limit: int) -> str:
    if limit <= len(CAPTION_ELLIPSIS):
        return ""

    if len(description) <= limit:
        return description

    return f"{description[: limit - len(CAPTION_ELLIPSIS)].rstrip()}{CAPTION_ELLIPSIS}"
