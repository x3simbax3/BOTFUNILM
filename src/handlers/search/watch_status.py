"""Planned/completed branches after confirming a title candidate."""

import aiosqlite
from aiogram import F
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery

from src.fsm import MenuState
from src.handlers.navigation import reset_to_main
from src.keyboards import (
    main_menu_keyboard,
    post_add_tracking_keyboard,
    rating_keyboard,
)
from src.lang import (
    INVALID_WATCH_STATUS,
    TITLE_SAVE_FAILED,
    planned_title_saved_text,
    rating_categories,
    rating_prompt_text,
)
from src.models import MediaWorkflowData
from src.services.planned_media import save_planned_media

from .router import router


@router.callback_query(
    MenuState.choosing_watch_status,
    F.data.startswith("watch_status:"),
)
async def choose_watch_status(callback: CallbackQuery, state: FSMContext) -> None:
    if not callback.data or not callback.message:
        return

    status = callback.data.removeprefix("watch_status:")
    if status not in {"completed", "planned"}:
        await callback.answer(INVALID_WATCH_STATUS, show_alert=True)
        return

    data = await state.get_data()
    workflow = MediaWorkflowData.from_fsm(data)
    if status == "planned":
        try:
            result = await save_planned_media(callback.from_user.id, workflow)
        except (aiosqlite.Error, RuntimeError, ValueError):
            await callback.answer(TITLE_SAVE_FAILED, show_alert=True)
            return

        is_ongoing = (
            result.series_snapshot is not None and result.series_snapshot.active
        )
        await callback.message.edit_text(
            planned_title_saved_text(
                workflow.tmdb_title,
                tracking_enabled=False if is_ongoing else None,
            ),
            parse_mode="HTML",
            reply_markup=(
                post_add_tracking_keyboard(result.media_id, False)
                if is_ongoing
                else None
            ),
        )
        if not is_ongoing:
            await callback.message.answer(
                "Готово — тайтл сохранён на потом.",
                reply_markup=main_menu_keyboard(),
            )
        await reset_to_main(state)
        await callback.answer()
        return

    await state.update_data(ratings={}, rating_index=0)
    categories = rating_categories(workflow.content_type)
    await callback.message.answer(
        rating_prompt_text(workflow.tmdb_title, categories[0][1], 1, len(categories)),
        parse_mode="HTML",
        reply_markup=rating_keyboard(),
    )
    await state.set_state(MenuState.rating_category)
    await callback.answer()


__all__ = ("choose_watch_status",)
