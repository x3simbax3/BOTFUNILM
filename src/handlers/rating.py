"""Rating workflow and movie persistence handlers."""

from datetime import date

import aiosqlite
from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery

from src.callback_data import parse_badge_callback, parse_rating_callback
from src.database.user_media import update_user_media_rating
from src.fsm import MenuState
from src.handlers.common import delete_message_safely
from src.handlers.navigation import reset_to_main, user_main_menu_keyboard
from src.handlers.series import start_series_tracking
from src.keyboards import badge_keyboard, rating_keyboard
from src.lang import (
    INVALID_BADGE,
    INVALID_RATING,
    MOVIE_SAVE_FAILED,
    RATING_ALREADY_SAVED,
    RATING_EDIT_CANCELLED,
    RATING_UPDATED,
    UNRELEASED_TITLE,
    badge_prompt_text,
    movie_watched_text,
    rating_categories,
    rating_prompt_text,
    rating_summary_text,
)
from src.models import current_media_id
from src.services import UnreleasedMediaError, save_completed_movie
from src.user_activity import track_user_event

router = Router(name="rating")


@router.callback_query(MenuState.rating_category, F.data == "rating:back")
async def back_from_rating(callback: CallbackQuery, state: FSMContext) -> None:
    if not callback.message:
        return

    data = await state.get_data()
    rating_index = data.get("rating_index", 0)
    categories = rating_categories(data.get("content_type", "movie"))
    if rating_index <= 0:
        await state.update_data(ratings={}, rating_index=0)
        if data.get("library_rating_edit"):
            await state.update_data(library_rating_edit=False)
            await reset_to_main(state)
            await callback.message.edit_text(
                RATING_EDIT_CANCELLED,
                reply_markup=await user_main_menu_keyboard(callback.from_user.id),
            )
            await callback.answer()
            return
        await state.set_state(MenuState.choosing_watch_status)
        await delete_message_safely(callback.message)
        await callback.answer()
        return

    previous_index = rating_index - 1
    ratings = dict(data.get("ratings", {}))
    ratings.pop(categories[previous_index][0], None)
    await state.update_data(ratings=ratings, rating_index=previous_index)
    await callback.message.edit_text(
        rating_prompt_text(
            data.get("tmdb_title", ""),
            categories[previous_index][1],
            previous_index + 1,
            len(categories),
        ),
        parse_mode="HTML",
        reply_markup=rating_keyboard(),
    )
    await callback.answer()


@router.callback_query(MenuState.rating_category, F.data.startswith("rate:"))
async def handle_rating(callback: CallbackQuery, state: FSMContext) -> None:
    if not callback.data or not callback.message:
        return

    score = parse_rating_callback(callback.data)
    if score is None:
        await callback.answer(INVALID_RATING, show_alert=True)
        return

    data = await state.get_data()
    ratings = data.get("ratings", {})
    rating_index = data.get("rating_index", 0)
    categories = rating_categories(data.get("content_type", "movie"))
    if not 0 <= rating_index < len(categories):
        await callback.answer(RATING_ALREADY_SAVED)
        return

    ratings[categories[rating_index][0]] = score
    rating_index += 1
    if rating_index < len(categories):
        await state.update_data(ratings=ratings, rating_index=rating_index)
        await callback.message.edit_text(
            rating_prompt_text(
                data.get("tmdb_title", ""),
                categories[rating_index][1],
                rating_index + 1,
                len(categories),
            ),
            parse_mode="HTML",
            reply_markup=rating_keyboard(),
        )
    else:
        average = sum(ratings.values()) / len(categories)
        await state.update_data(
            ratings=ratings,
            rating_average=average,
            rating_index=len(categories),
        )
        summary = rating_summary_text(
            data.get("tmdb_title", ""),
            ratings,
            average,
            categories,
        )
        await callback.message.edit_text(
            badge_prompt_text(data.get("tmdb_title", ""), summary),
            parse_mode="HTML",
            reply_markup=badge_keyboard("rating_badge"),
        )
        await state.set_state(MenuState.choosing_badge)

    await callback.answer()


@router.callback_query(
    MenuState.choosing_badge,
    F.data == "rating_badge:back",
)
async def back_from_badge(callback: CallbackQuery, state: FSMContext) -> None:
    if not callback.message:
        return
    data = await state.get_data()
    categories = rating_categories(data.get("content_type", "movie"))
    last_index = len(categories) - 1
    ratings = dict(data.get("ratings", {}))
    ratings.pop(categories[last_index][0], None)
    await state.update_data(ratings=ratings, rating_index=last_index)
    await state.set_state(MenuState.rating_category)
    await callback.message.edit_text(
        rating_prompt_text(
            data.get("tmdb_title", ""),
            categories[last_index][1],
            len(categories),
            len(categories),
        ),
        parse_mode="HTML",
        reply_markup=rating_keyboard(),
    )
    await callback.answer()


@router.callback_query(
    MenuState.choosing_badge,
    F.data.startswith("rating_badge:"),
)
async def choose_badge(callback: CallbackQuery, state: FSMContext) -> None:
    if not callback.data or not callback.message:
        return
    value = parse_badge_callback(callback.data)
    if value is None or value == "back":
        await callback.answer(INVALID_BADGE, show_alert=True)
        return

    badge = None if value == "none" else value
    await state.update_data(badge=badge)
    data = await state.get_data()
    average = data.get("rating_average")
    if type(average) not in {int, float}:
        await callback.answer(RATING_ALREADY_SAVED, show_alert=True)
        return

    if data.get("library_rating_edit"):
        await finish_library_rating_edit(callback, state, float(average))
    elif data.get("content_format") == "series":
        await start_series_tracking(callback, state)
    else:
        await finish_movie(callback, state, float(average))
    await callback.answer()


async def finish_library_rating_edit(
    callback: CallbackQuery,
    state: FSMContext,
    average: float,
) -> None:
    data = await state.get_data()
    media_id = current_media_id(data)
    if media_id is None:
        await callback.answer(MOVIE_SAVE_FAILED, show_alert=True)
        return
    try:
        updated = await update_user_media_rating(
            callback.from_user.id,
            media_id,
            round(average),
            badge=data.get("badge"),
            rating_details=data.get("ratings"),
        )
        if not updated:
            raise RuntimeError("Library item disappeared")
    except (aiosqlite.Error, RuntimeError, ValueError):
        await callback.answer(MOVIE_SAVE_FAILED, show_alert=True)
        return

    await track_user_event(callback.from_user.id, "rating_set")

    await state.update_data(library_rating_edit=False)
    await callback.message.answer(
        RATING_UPDATED,
        reply_markup=await user_main_menu_keyboard(callback.from_user.id),
    )
    await reset_to_main(state)


async def finish_movie(
    callback: CallbackQuery,
    state: FSMContext,
    average: float,
) -> None:
    data = await state.get_data()
    try:
        await save_completed_movie(
            callback.from_user.id,
            dict(data),
            average,
        )
    except UnreleasedMediaError:
        await callback.answer(UNRELEASED_TITLE, show_alert=True)
        await reset_to_main(state)
        return
    except (aiosqlite.Error, RuntimeError):
        await callback.answer(
            MOVIE_SAVE_FAILED,
            show_alert=True,
        )
        return

    await track_user_event(callback.from_user.id, "media_added")
    await track_user_event(callback.from_user.id, "rating_set")

    await state.update_data(watch_date=date.today().isoformat())
    await callback.message.answer(
        movie_watched_text(data.get("tmdb_title", ""), average),
        parse_mode="HTML",
        reply_markup=await user_main_menu_keyboard(callback.from_user.id),
    )
    await reset_to_main(state)
