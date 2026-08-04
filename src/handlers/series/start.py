"""Entry point for the series tracking workflow."""

import aiosqlite
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery

from src.fsm import MenuState
from src.handlers.navigation import reset_to_main, user_main_menu_keyboard
from src.lang import DETAILS_LOAD_FAILED, PROGRESS_LOAD_FAILED, SAVED_PROGRESS_INVALID
from src.services.series_metadata import (
    SeriesMetadataError,
    load_series_release_snapshot,
)
from src.services.series_tracking import SeriesProgressError, prepare_series_tracking
from src.tmdb_models import TmdbError

from .navigation import show_season_list


async def start_series_tracking(callback: CallbackQuery, state: FSMContext) -> None:
    data = await state.get_data()
    try:
        snapshot = await load_series_release_snapshot(data)
    except (aiosqlite.Error, TmdbError, SeriesMetadataError, TypeError, ValueError):
        await _leave_tracking(callback, state, DETAILS_LOAD_FAILED)
        return

    try:
        tracking = await prepare_series_tracking(
            data,
            callback.from_user.id,
            snapshot,
        )
    except aiosqlite.Error:
        await _leave_tracking(callback, state, PROGRESS_LOAD_FAILED)
        return
    except SeriesProgressError:
        await _leave_tracking(callback, state, SAVED_PROGRESS_INVALID)
        return

    tracking_data = tracking.to_fsm_dict()
    await state.update_data(**tracking_data)
    await show_season_list(
        callback.message,
        data | tracking_data,
        tracking.watched,
        edit=False,
    )
    await state.set_state(MenuState.tracking_series)


async def _leave_tracking(
    callback: CallbackQuery,
    state: FSMContext,
    text: str,
) -> None:
    await callback.message.answer(
        text,
        reply_markup=await user_main_menu_keyboard(callback.from_user.id),
    )
    await reset_to_main(state)


__all__ = ("start_series_tracking",)
