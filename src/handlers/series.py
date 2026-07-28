"""Series season selection and progress persistence handlers."""

from collections.abc import Mapping
from datetime import date

import aiosqlite
from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery

from src.callback_data import (
    EpisodeCallback,
    EpisodePageCallback,
    parse_episode_callback,
    parse_season_callback,
)
from src.database.media import get_media_by_tmdb
from src.database.series import get_user_season_progress, save_user_series_progress
from src.fsm import MenuState
from src.keyboards import (
    EPISODES_PAGE_SIZE,
    episodes_keyboard,
    main_menu_keyboard,
    season_list_keyboard,
)
from src.lang import (
    DETAILS_LOAD_FAILED,
    DONE,
    INVALID_EPISODE,
    INVALID_PROGRESS,
    INVALID_PROGRESS_TRANSITION,
    INVALID_SEASON,
    NO_EPISODES_SELECTED,
    PROGRESS_LOAD_FAILED,
    PROGRESS_SAVE_FAILED,
    SAVED_PROGRESS_INVALID,
    SEASON_NOT_FOUND,
    episodes_prompt_text,
    series_tracking_text,
    tracking_complete_text,
)
from src.services import (
    SeriesProgressError,
    apply_episode_selection,
    ensure_media,
    season_episode_limits,
    validate_series_progress,
)
from src.tmdb import TmdbError, fetch_tv_details

router = Router(name="series")


async def start_series_tracking(callback: CallbackQuery, state: FSMContext) -> None:
    data = await state.get_data()
    tmdb_id = data.get("tmdb_id", 0)
    title = data.get("tmdb_title", "")

    try:
        details = await fetch_tv_details(tmdb_id)
    except TmdbError:
        await _leave_tracking(
            callback,
            state,
            DETAILS_LOAD_FAILED,
        )
        return

    seasons_data = [
        {
            "season_number": season.season_number,
            "name": season.name,
            "episode_count": season.episode_count,
        }
        for season in details.seasons
        if season.season_number > 0 and season.episode_count > 0
    ]

    try:
        media_id = await _existing_media_id(data, tmdb_id)
        progress_rows = (
            await get_user_season_progress(callback.from_user.id, media_id)
            if media_id is not None
            else []
        )
    except aiosqlite.Error:
        await _leave_tracking(
            callback,
            state,
            PROGRESS_LOAD_FAILED,
        )
        return

    try:
        watched = {
            int(row["season_number"]): int(row["episodes_watched"])
            for row in progress_rows
            # Season 0 used to be trackable. Ignore that legacy progress now
            # that specials are deliberately excluded from the series total.
            if int(row["season_number"]) != 0
        }
        total_episodes = sum(season_episode_limits(seasons_data).values())
        watched = validate_series_progress(watched, seasons_data, total_episodes)
    except SeriesProgressError:
        await _leave_tracking(
            callback,
            state,
            SAVED_PROGRESS_INVALID,
        )
        return

    await state.update_data(
        media_id=media_id,
        seasons_data=seasons_data,
        total_seasons=details.number_of_seasons,
        total_episodes=total_episodes,
        watched_by_season=watched,
        current_season=None,
        episodes_watched_total=sum(watched.values()),
    )
    await callback.message.answer(
        series_tracking_text(title, seasons_data),
        parse_mode="HTML",
        reply_markup=season_list_keyboard(seasons_data, watched),
    )
    await state.set_state(MenuState.tracking_series)


async def _existing_media_id(data: dict, tmdb_id: int) -> int | None:
    media_id = data.get("media_id")
    if media_id is not None:
        return int(media_id)

    existing = await get_media_by_tmdb(
        tmdb_id,
        "series",
        data.get("content_type", "movie"),
    )
    return int(existing["id"]) if existing is not None else None


async def _leave_tracking(
    callback: CallbackQuery,
    state: FSMContext,
    text: str,
) -> None:
    await callback.message.answer(text, reply_markup=main_menu_keyboard())
    await state.set_state(MenuState.choosing_action)


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
            watched = season_episode_limits(seasons_data)
            watched = validate_series_progress(
                watched,
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
        await callback.message.edit_text(
            series_tracking_text(data.get("tmdb_title", ""), seasons_data),
            parse_mode="HTML",
            reply_markup=season_list_keyboard(seasons_data, watched),
        )
        await callback.answer()
        return

    season_number = selection
    season_info = next(
        (
            season
            for season in data.get("seasons_data", [])
            if season["season_number"] == season_number
        ),
        None,
    )
    if not season_info:
        await callback.answer(SEASON_NOT_FOUND)
        return

    try:
        watched = _progress_from_state(data.get("watched_by_season", {}))
    except SeriesProgressError:
        await callback.answer(INVALID_PROGRESS_TRANSITION, show_alert=True)
        return
    await state.update_data(current_season=season_number)
    await callback.message.edit_text(
        episodes_prompt_text(
            data.get("tmdb_title", ""),
            season_info["name"],
            season_info["episode_count"],
            watched.get(season_number, 0),
        ),
        parse_mode="HTML",
        reply_markup=episodes_keyboard(season_info["episode_count"], season_number),
    )
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
        season_number = data.get("current_season")
        season_info = next(
            (
                season
                for season in data.get("seasons_data", [])
                if season["season_number"] == season_number
            ),
            None,
        )
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
            watched = _progress_from_state(data.get("watched_by_season", {}))
        except SeriesProgressError:
            await callback.answer(INVALID_PROGRESS_TRANSITION, show_alert=True)
            return
        await callback.message.edit_text(
            episodes_prompt_text(
                data.get("tmdb_title", ""),
                season_info["name"],
                season_info["episode_count"],
                watched.get(season_number, 0),
            ),
            parse_mode="HTML",
            reply_markup=episodes_keyboard(
                season_info["episode_count"],
                season_number,
                selection.page,
            ),
        )
        await callback.answer()
        return

    if selection == "noop":
        await callback.answer()
        return
    if selection == "back":
        try:
            watched = _progress_from_state(data.get("watched_by_season", {}))
        except SeriesProgressError:
            await callback.answer(INVALID_PROGRESS_TRANSITION, show_alert=True)
            return
        seasons_data = data.get("seasons_data", [])
        await state.update_data(current_season=None)
        await callback.message.edit_text(
            series_tracking_text(data.get("tmdb_title", ""), seasons_data),
            parse_mode="HTML",
            reply_markup=season_list_keyboard(seasons_data, watched),
        )
        await callback.answer()
        return
    if selection == "done":
        await finish_series_tracking(callback, state)
        return

    assert isinstance(selection, EpisodeCallback)
    season_number = selection.season_number
    try:
        watched = apply_episode_selection(
            _progress_from_state(data.get("watched_by_season", {})),
            data.get("seasons_data", []),
            data.get("total_episodes", 0),
            current_season=data.get("current_season"),
            season_number=season_number,
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
    seasons_data = data.get("seasons_data", [])
    await callback.message.edit_text(
        series_tracking_text(data.get("tmdb_title", ""), seasons_data),
        parse_mode="HTML",
        reply_markup=season_list_keyboard(seasons_data, watched),
    )
    await callback.answer()


async def finish_series_tracking(
    callback: CallbackQuery,
    state: FSMContext,
) -> None:
    if not callback.message:
        return

    data = await state.get_data()
    title = data.get("tmdb_title", "")
    total = data.get("total_episodes", 0)
    average = data.get("rating_average")
    try:
        watched = validate_series_progress(
            _progress_from_state(data.get("watched_by_season", {})),
            data.get("seasons_data", []),
            total,
        )
    except SeriesProgressError:
        await callback.answer(
            INVALID_PROGRESS,
            show_alert=True,
        )
        return

    watched_total = sum(watched.values())
    if watched_total == 0:
        await callback.answer(NO_EPISODES_SELECTED, show_alert=True)
        return
    try:
        media_id = await ensure_media(
            data,
            "series",
            number_of_seasons=data.get("total_seasons"),
            number_of_episodes=total,
        )
        await save_user_series_progress(
            user_id=callback.from_user.id,
            media_id=media_id,
            seasons=watched,
            total_episodes=total,
            user_rating=round(average) if average is not None else None,
        )
    except (aiosqlite.Error, RuntimeError, ValueError):
        await callback.answer(
            PROGRESS_SAVE_FAILED,
            show_alert=True,
        )
        return

    await state.update_data(watch_date=date.today().isoformat())
    await callback.message.edit_text(
        tracking_complete_text(title, total, watched_total, average),
        parse_mode="HTML",
    )
    await callback.message.answer(DONE, reply_markup=main_menu_keyboard())
    await state.set_state(MenuState.choosing_action)
    await callback.answer()


def _progress_from_state(value: object) -> dict[int, int]:
    """Restore integer season keys after Redis JSON serialization."""
    if not isinstance(value, Mapping):
        raise SeriesProgressError("Invalid progress state")

    progress: dict[int, int] = {}
    for raw_season, episodes_watched in value.items():
        if type(raw_season) is int:
            season_number = raw_season
        elif (
            isinstance(raw_season, str)
            and raw_season.isascii()
            and raw_season.isdigit()
            and str(int(raw_season)) == raw_season
        ):
            season_number = int(raw_season)
        else:
            raise SeriesProgressError("Invalid season key in progress state")
        if season_number in progress:
            raise SeriesProgressError("Duplicate season in progress state")
        progress[season_number] = episodes_watched
    return progress
