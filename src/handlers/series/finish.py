"""Persistence and final UI response for series tracking."""

from datetime import date

import aiosqlite
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery

from src.handlers.navigation import reset_to_main
from src.keyboards import main_menu_keyboard, post_add_tracking_keyboard
from src.lang import (
    DONE,
    INVALID_PROGRESS,
    NO_EPISODES_SELECTED,
    PROGRESS_SAVE_FAILED,
    tracking_complete_text,
)
from src.services.series_tracking import (
    EmptySeriesProgressError,
    SeriesProgressError,
    save_series_tracking_result,
)


async def finish_series_tracking(
    callback: CallbackQuery,
    state: FSMContext,
) -> None:
    if not callback.message:
        return

    data = await state.get_data()
    try:
        result = await save_series_tracking_result(data, callback.from_user.id)
    except EmptySeriesProgressError:
        await callback.answer(NO_EPISODES_SELECTED, show_alert=True)
        return
    except SeriesProgressError:
        await callback.answer(INVALID_PROGRESS, show_alert=True)
        return
    except (aiosqlite.Error, RuntimeError, ValueError):
        await callback.answer(PROGRESS_SAVE_FAILED, show_alert=True)
        return

    await state.update_data(watch_date=date.today().isoformat())
    is_new_item = not bool(data.get("library_progress_edit"))
    await callback.message.edit_text(
        tracking_complete_text(
            result.title,
            result.total_episodes,
            result.watched_total,
            result.average,
            is_ongoing=result.is_ongoing,
            announced_episodes=result.announced_episodes,
            tracking_enabled=False if is_new_item and result.is_ongoing else None,
        ),
        parse_mode="HTML",
        reply_markup=(
            post_add_tracking_keyboard(result.media_id, False)
            if is_new_item and result.is_ongoing
            else None
        ),
    )
    if not (is_new_item and result.is_ongoing):
        await callback.message.answer(DONE, reply_markup=main_menu_keyboard())
    await reset_to_main(state)
    await callback.answer()


__all__ = ("finish_series_tracking",)
