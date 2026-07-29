"""Season and episode navigation handlers."""

from typing import Any

from aiogram import F
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from src.callback_data import (
    EpisodeCallback,
    EpisodePageCallback,
    parse_episode_callback,
    parse_season_callback,
)
from src.fsm import MenuState
from src.keyboards import EPISODES_PAGE_SIZE, episodes_keyboard, season_list_keyboard
from src.lang import (
    INVALID_EPISODE,
    INVALID_PROGRESS_TRANSITION,
    INVALID_SEASON,
    SEASON_NOT_AVAILABLE,
    SEASON_NOT_FOUND,
    episodes_prompt_text,
    series_tracking_text,
)
from src.services.series_tracking import (
    SeriesProgressError,
    apply_episode_selection,
    restore_progress_keys,
    season_episode_limits,
    validate_series_progress,
)

from .finish import finish_series_tracking
from .router import router


async def show_season_list(
    message: Message,
    data: dict[str, Any],
    watched: dict[int, int],
    *,
    edit: bool = True,
) -> None:
    seasons_data = data.get("seasons_data", [])
    send = message.edit_text if edit else message.answer
    await send(
        series_tracking_text(
            data.get("tmdb_title", ""),
            seasons_data,
            is_ongoing=bool(data.get("is_ongoing")),
        ),
        parse_mode="HTML",
        reply_markup=season_list_keyboard(seasons_data, watched),
    )


async def show_episode_list(
    message: Message,
    data: dict[str, Any],
    season_info: dict[str, Any],
    watched: dict[int, int],
    *,
    page: int = 0,
) -> None:
    season_number = season_info["season_number"]
    episode_count = season_info["episode_count"]
    await message.edit_text(
        episodes_prompt_text(
            data.get("tmdb_title", ""),
            season_info["name"],
            episode_count,
            watched.get(season_number, 0),
        ),
        parse_mode="HTML",
        reply_markup=episodes_keyboard(episode_count, season_number, page),
    )


@router.callback_query(MenuState.tracking_series, F.data.startswith("season:"))
async def handle_season_selection(callback: CallbackQuery, state: FSMContext) -> None:
    if not callback.data or not callback.message:
        return

    selection = parse_season_callback(callback.data)
    if selection is None:
        await callback.answer(INVALID_SEASON, show_alert=True)
        return
    if selection == "done":
        await finish_series_tracking(callback, state)
        return

    data = await state.get_data()
    if selection == "all":
        seasons_data = data.get("seasons_data", [])
        try:
            watched = validate_series_progress(
                season_episode_limits(seasons_data),
                seasons_data,
                data.get("total_episodes", 0),
            )
        except SeriesProgressError:
            await callback.answer(INVALID_PROGRESS_TRANSITION, show_alert=True)
            return
        await state.update_data(
            watched_by_season=watched,
            episodes_watched_total=sum(watched.values()),
            current_season=None,
        )
        await show_season_list(callback.message, data, watched)
        await callback.answer()
        return

    season_info = _find_season(data, selection)
    if not season_info:
        await callback.answer(SEASON_NOT_FOUND)
        return
    if season_info["episode_count"] == 0:
        await callback.answer(SEASON_NOT_AVAILABLE, show_alert=True)
        return

    try:
        watched = restore_progress_keys(data.get("watched_by_season", {}))
    except SeriesProgressError:
        await callback.answer(INVALID_PROGRESS_TRANSITION, show_alert=True)
        return
    await state.update_data(current_season=selection)
    await show_episode_list(callback.message, data, season_info, watched)
    await callback.answer()


@router.callback_query(MenuState.tracking_series, F.data.startswith("ep:"))
async def handle_episode_selection(callback: CallbackQuery, state: FSMContext) -> None:
    if not callback.data or not callback.message:
        return

    selection = parse_episode_callback(callback.data)
    if selection is None:
        await callback.answer(INVALID_EPISODE, show_alert=True)
        return

    data = await state.get_data()
    if isinstance(selection, EpisodePageCallback):
        season_info = _find_season(data, data.get("current_season"))
        if not season_info:
            await callback.answer(INVALID_PROGRESS_TRANSITION, show_alert=True)
            return
        total_pages = max(
            1,
            (season_info["episode_count"] + EPISODES_PAGE_SIZE - 1)
            // EPISODES_PAGE_SIZE,
        )
        if selection.page >= total_pages:
            await callback.answer(INVALID_EPISODE, show_alert=True)
            return
        try:
            watched = restore_progress_keys(data.get("watched_by_season", {}))
        except SeriesProgressError:
            await callback.answer(INVALID_PROGRESS_TRANSITION, show_alert=True)
            return
        await show_episode_list(
            callback.message,
            data,
            season_info,
            watched,
            page=selection.page,
        )
        await callback.answer()
        return

    if selection == "noop":
        await callback.answer()
        return
    if selection == "back":
        try:
            watched = restore_progress_keys(data.get("watched_by_season", {}))
        except SeriesProgressError:
            await callback.answer(INVALID_PROGRESS_TRANSITION, show_alert=True)
            return
        await state.update_data(current_season=None)
        await show_season_list(callback.message, data, watched)
        await callback.answer()
        return
    if selection == "done":
        await finish_series_tracking(callback, state)
        return

    if not isinstance(selection, EpisodeCallback):
        await callback.answer(INVALID_EPISODE, show_alert=True)
        return
    try:
        watched = apply_episode_selection(
            restore_progress_keys(data.get("watched_by_season", {})),
            data.get("seasons_data", []),
            data.get("total_episodes", 0),
            current_season=data.get("current_season"),
            season_number=selection.season_number,
            episodes_watched=selection.episodes_watched,
        )
    except SeriesProgressError:
        await callback.answer(INVALID_PROGRESS_TRANSITION, show_alert=True)
        return
    await state.update_data(
        watched_by_season=watched,
        episodes_watched_total=sum(watched.values()),
        current_season=None,
    )
    await show_season_list(callback.message, data, watched)
    await callback.answer()


def _find_season(data: dict[str, Any], season_number: object) -> dict | None:
    return next(
        (
            season
            for season in data.get("seasons_data", [])
            if season["season_number"] == season_number
        ),
        None,
    )


__all__ = (
    "handle_episode_selection",
    "handle_season_selection",
    "show_episode_list",
    "show_season_list",
)
