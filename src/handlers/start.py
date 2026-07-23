from datetime import date

from aiogram import F, Router
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from src.fsm import MenuState
from src.keyboards import (
    content_type_keyboard,
    episodes_keyboard,
    format_keyboard,
    main_menu_keyboard,
    rating_keyboard,
    season_list_keyboard,
    selected_type_keyboard,
    tmdb_guess_keyboard,
    tmdb_retry_keyboard,
)
from src.texts import (
    RATING_CATEGORIES,
    START_TEXT,
    TMDB_SEARCHING,
    TMDB_TOO_LONG,
    action_text,
    content_type_text,
    episodes_prompt_text,
    movie_watched_text,
    rating_prompt_text,
    rating_summary_text,
    selected_type_text,
    series_tracking_text,
    tmdb_found_text,
    tmdb_guess_text,
    tmdb_not_found_text,
    tracking_complete_text,
)
from src.tmdb import (
    TmdbError,
    TmdbNotConfiguredError,
    TmdbNotFoundError,
    fetch_tv_details,
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
CAPTION_ELLIPSIS = "..."


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
    else:
        guess_message = await message.answer(
            text,
            parse_mode="HTML",
            reply_markup=tmdb_guess_keyboard(),
        )

    await state.update_data(
        tmdb_guess_message_id=guess_message.message_id,
        tmdb_title=guess.title,
        tmdb_id=guess.tmdb_id,
    )
    await state.set_state(MenuState.confirming_tmdb_guess)


# --- TMDB подтверждение ---

@router.callback_query(MenuState.confirming_tmdb_guess, F.data == "tmdb_guess:yes")
async def confirm_tmdb_guess(callback: CallbackQuery, state: FSMContext) -> None:
    if not await _is_active_tmdb_guess(callback, state):
        await callback.answer("Это старый вариант.")
        return

    await callback.answer()
    await state.update_data(tmdb_guess_message_id=None, ratings={}, rating_index=0)

    data = await state.get_data()
    title = data.get("tmdb_title", "")
    category_key, category_name = RATING_CATEGORIES[0]
    await callback.message.answer(
        rating_prompt_text(title, category_name, 1, len(RATING_CATEGORIES)),
        parse_mode="HTML",
        reply_markup=rating_keyboard(),
    )
    await state.set_state(MenuState.rating_category)


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


# --- Оценка ---

@router.callback_query(MenuState.rating_category, F.data.startswith("rate:"))
async def handle_rating(callback: CallbackQuery, state: FSMContext) -> None:
    if not callback.data or not callback.message:
        return

    score = int(callback.data.split(":")[1])
    data = await state.get_data()
    ratings = data.get("ratings", {})
    rating_index = data.get("rating_index", 0)
    title = data.get("tmdb_title", "")

    category_key, category_name = RATING_CATEGORIES[rating_index]
    ratings[category_key] = score
    rating_index += 1

    if rating_index < len(RATING_CATEGORIES):
        await state.update_data(ratings=ratings, rating_index=rating_index)
        next_key, next_name = RATING_CATEGORIES[rating_index]
        await callback.message.edit_text(
            rating_prompt_text(title, next_name, rating_index + 1, len(RATING_CATEGORIES)),
            parse_mode="HTML",
            reply_markup=rating_keyboard(),
        )
    else:
        average = sum(ratings.values()) / len(RATING_CATEGORIES)
        await state.update_data(ratings=ratings, rating_average=average)
        await callback.message.edit_text(
            rating_summary_text(title, ratings, average),
            parse_mode="HTML",
        )

        content_format = data.get("content_format", "")
        if content_format == "series":
            await _start_series_tracking(callback, state)
        else:
            await _finish_movie(callback, state, average)

    await callback.answer()


async def _finish_movie(callback: CallbackQuery, state: FSMContext, average: float) -> None:
    data = await state.get_data()
    title = data.get("tmdb_title", "")
    await state.update_data(watch_date=date.today().isoformat())
    await callback.message.answer(
        movie_watched_text(title, average),
        parse_mode="HTML",
        reply_markup=main_menu_keyboard(),
    )
    await state.set_state(MenuState.choosing_action)


# --- Трекинг сериала ---

async def _start_series_tracking(callback: CallbackQuery, state: FSMContext) -> None:
    data = await state.get_data()
    tmdb_id = data.get("tmdb_id", 0)
    title = data.get("tmdb_title", "")

    try:
        details = await fetch_tv_details(tmdb_id)
    except TmdbError:
        await callback.message.answer(
            "Не удалось получить информацию о сериале. Попробуй позже.",
            reply_markup=main_menu_keyboard(),
        )
        await state.set_state(MenuState.choosing_action)
        return

    seasons_data = [
        {
            "season_number": s.season_number,
            "name": s.name,
            "episode_count": s.episode_count,
        }
        for s in details.seasons
        if s.episode_count > 0
    ]

    await state.update_data(
        tv_details=details,
        seasons_data=seasons_data,
        total_episodes=details.number_of_episodes,
        watched_by_season={},
        current_season=None,
        episodes_watched_total=0,
    )

    await callback.message.answer(
        series_tracking_text(title, seasons_data),
        parse_mode="HTML",
        reply_markup=season_list_keyboard(seasons_data, {}),
    )
    await state.set_state(MenuState.tracking_series)


@router.callback_query(MenuState.tracking_series, F.data.startswith("season:"))
async def handle_season_selection(callback: CallbackQuery, state: FSMContext) -> None:
    if not callback.data:
        return

    value = callback.data.split(":")[1]
    data = await state.get_data()
    title = data.get("tmdb_title", "")
    seasons_data = data.get("seasons_data", [])
    watched = data.get("watched_by_season", {})

    if value == "done":
        average = data.get("rating_average", 0)
        total = data.get("total_episodes", 0)
        watched_total = data.get("episodes_watched_total", 0)
        await state.update_data(watch_date=date.today().isoformat())
        await callback.message.edit_text(
            tracking_complete_text(title, total, watched_total, average),
            parse_mode="HTML",
        )
        await callback.message.answer(
            "Готово!",
            reply_markup=main_menu_keyboard(),
        )
        await state.set_state(MenuState.choosing_action)
        await callback.answer()
        return

    season_number = int(value)
    season_info = next(
        (s for s in seasons_data if s["season_number"] == season_number),
        None,
    )
    if not season_info:
        await callback.answer("Сезон не найден")
        return

    already_watched = watched.get(season_number, 0)
    await state.update_data(current_season=season_number)
    await callback.message.edit_text(
        episodes_prompt_text(
            title,
            season_info["name"],
            season_info["episode_count"],
            already_watched,
        ),
        parse_mode="HTML",
        reply_markup=episodes_keyboard(
            season_info["episode_count"],
            season_number,
        ),
    )
    await callback.answer()


@router.callback_query(MenuState.tracking_series, F.data.startswith("ep:"))
async def handle_episode_selection(callback: CallbackQuery, state: FSMContext) -> None:
    if not callback.data:
        return

    parts = callback.data.split(":")
    data = await state.get_data()
    if parts[1] == "done":
        average = data.get("rating_average", 0)
        total = data.get("total_episodes", 0)
        watched_total = data.get("episodes_watched_total", 0)
        title = data.get("tmdb_title", "")
        await state.update_data(watch_date=date.today().isoformat())
        await callback.message.edit_text(
            tracking_complete_text(title, total, watched_total, average),
            parse_mode="HTML",
        )
        await callback.message.answer(
            "Готово!",
            reply_markup=main_menu_keyboard(),
        )
        await state.set_state(MenuState.choosing_action)
        await callback.answer()
        return

    season_number = int(parts[1])
    episodes_watched = int(parts[2])

    title = data.get("tmdb_title", "")
    seasons_data = data.get("seasons_data", [])
    watched = data.get("watched_by_season", {})

    watched[season_number] = episodes_watched
    watched_total = sum(watched.values())
    await state.update_data(
        watched_by_season=watched,
        episodes_watched_total=watched_total,
    )

    await callback.message.edit_text(
        series_tracking_text(title, seasons_data),
        parse_mode="HTML",
        reply_markup=season_list_keyboard(seasons_data, watched),
    )
    await callback.answer()


# --- Навигация ---

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

    clipped = description[: max(0, limit - len(CAPTION_ELLIPSIS))].rstrip()
    return f"{clipped}{CAPTION_ELLIPSIS}"
