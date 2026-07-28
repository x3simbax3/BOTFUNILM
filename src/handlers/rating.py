"""Rating workflow and movie persistence handlers."""

from datetime import date

import aiosqlite
from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery

from src.callback_data import parse_rating_callback
from src.database.user_media import save_user_media, update_user_media_rating
from src.fsm import MenuState
from src.handlers.common import delete_message_safely
from src.handlers.series import start_series_tracking
from src.keyboards import main_menu_keyboard, rating_keyboard
from src.lang import (
    INVALID_RATING,
    MOVIE_SAVE_FAILED,
    RATING_ALREADY_SAVED,
    RATING_EDIT_CANCELLED,
    RATING_UPDATED,
    movie_watched_text,
    rating_categories,
    rating_prompt_text,
    rating_summary_text,
)
from src.services import ensure_media

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
            await state.set_state(MenuState.choosing_action)
            await callback.message.edit_text(
                RATING_EDIT_CANCELLED,
                reply_markup=main_menu_keyboard(),
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
        await state.update_data(ratings=ratings, rating_average=average)
        await callback.message.edit_text(
            rating_summary_text(
                data.get("tmdb_title", ""),
                ratings,
                average,
                categories,
            ),
            parse_mode="HTML",
        )
        if data.get("library_rating_edit"):
            await finish_library_rating_edit(callback, state, average)
        elif data.get("content_format") == "series":
            await start_series_tracking(callback, state)
        else:
            await finish_movie(callback, state, average)

    await callback.answer()


async def finish_library_rating_edit(
    callback: CallbackQuery,
    state: FSMContext,
    average: float,
) -> None:
    data = await state.get_data()
    media_id = data.get("media_id")
    if type(media_id) is not int or media_id <= 0:
        await callback.answer(MOVIE_SAVE_FAILED, show_alert=True)
        return
    try:
        updated = await update_user_media_rating(
            callback.from_user.id,
            media_id,
            round(average),
            rating_details=data.get("ratings"),
        )
        if not updated:
            raise RuntimeError("Library item disappeared")
    except (aiosqlite.Error, RuntimeError, ValueError):
        await callback.answer(MOVIE_SAVE_FAILED, show_alert=True)
        return

    await state.update_data(library_rating_edit=False)
    await callback.message.answer(
        RATING_UPDATED,
        reply_markup=main_menu_keyboard(),
    )
    await state.set_state(MenuState.choosing_action)


async def finish_movie(
    callback: CallbackQuery,
    state: FSMContext,
    average: float,
) -> None:
    data = await state.get_data()
    try:
        media_id = await ensure_media(data, "full_length")
        await save_user_media(
            user_id=callback.from_user.id,
            media_id=media_id,
            status="completed",
            user_rating=round(average),
            rating_details=data.get("ratings"),
        )
    except (aiosqlite.Error, RuntimeError):
        await callback.answer(
            MOVIE_SAVE_FAILED,
            show_alert=True,
        )
        return

    await state.update_data(watch_date=date.today().isoformat())
    await callback.message.answer(
        movie_watched_text(data.get("tmdb_title", ""), average),
        parse_mode="HTML",
        reply_markup=main_menu_keyboard(),
    )
    await state.set_state(MenuState.choosing_action)
