"""Rating workflow and movie persistence handlers."""

from datetime import date

import aiosqlite
from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery

from src.callback_data import parse_rating_callback
from src.database.user_media import save_user_media
from src.fsm import MenuState
from src.handlers.series import start_series_tracking
from src.keyboards import main_menu_keyboard, rating_keyboard
from src.services import ensure_media
from src.lang import (
    INVALID_RATING,
    MOVIE_SAVE_FAILED,
    RATING_ALREADY_SAVED,
    movie_watched_text,
    rating_categories,
    rating_prompt_text,
    rating_summary_text,
)


router = Router(name="rating")


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
        if data.get("content_format") == "series":
            await start_series_tracking(callback, state)
        else:
            await finish_movie(callback, state, average)

    await callback.answer()


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
