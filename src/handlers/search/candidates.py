"""TMDB candidate presentation, carousel, confirmation and rejection."""

from collections.abc import Mapping, MutableMapping, Sequence
from typing import Any

import aiosqlite
from aiogram import F
from aiogram.exceptions import TelegramBadRequest
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from src.database.media import (
    clear_media_telegram_poster_file_id,
    get_media_by_tmdb,
    update_media_telegram_poster_file_id,
)
from src.database.user_media import get_user_media
from src.fsm import MenuState
from src.handlers.common import (
    delete_message_safely,
    is_active_tmdb_guess,
    tmdb_guess_caption,
)
from src.keyboards import (
    tmdb_guess_keyboard,
    tmdb_retry_keyboard,
    watch_status_keyboard,
)
from src.lang import (
    ALREADY_IN_LIBRARY,
    LOCAL_SEARCH_FAILED,
    REJECTED_GUESS,
    STALE_GUESS,
    TMDB_FAILED,
    WATCH_STATUS_PROMPT,
)
from src.models import MediaWorkflowData, current_media_id
from src.posters import poster_input, sent_photo_file_id
from src.release_availability import release_date_has_passed
from src.services.title_search import TitleSearchCandidate
from src.tmdb_models import TmdbError
from src.tmdb_movie import fetch_movie_details
from src.tmdb_search import MAX_TITLE_CANDIDATES

from .router import router


async def show_candidates(
    message: Message,
    state: FSMContext,
    candidates: Sequence[TitleSearchCandidate],
    content_format: str,
    content_type: str,
) -> None:
    payloads = [candidate.to_fsm_dict() for candidate in candidates]
    guess_message = await _send_candidate(
        message,
        payloads[0],
        content_format,
        0,
        len(payloads),
    )
    telegram_poster_file_id = sent_photo_file_id(guess_message) or payloads[0].get(
        "telegram_poster_file_id"
    )
    if telegram_poster_file_id and payloads[0].get("media_id"):
        try:
            await update_media_telegram_poster_file_id(
                int(payloads[0]["media_id"]),
                telegram_poster_file_id,
            )
        except aiosqlite.Error:
            pass
    workflow_data = MediaWorkflowData.from_tmdb_candidate(
        payloads[0],
        content_format=content_format,
        content_type=content_type,
    ).to_fsm_dict()
    workflow_data["telegram_poster_file_id"] = telegram_poster_file_id
    await state.update_data(
        tmdb_candidates=payloads,
        tmdb_candidate_index=0,
        tmdb_guess_message_id=guess_message.message_id,
        **workflow_data,
    )
    await state.set_state(MenuState.confirming_tmdb_guess)


async def _send_candidate(
    message: Message,
    candidate: Mapping[str, Any],
    content_format: str,
    position: int,
    total: int,
):
    release_date = candidate.get("release_date") or ""
    year = release_date[:4] if release_date[:4].isdigit() else ""
    display_title = candidate["title"]
    if year:
        display_title = f"{display_title} ({year})"
    original_title = candidate.get("original_title")
    if original_title and original_title != candidate["title"]:
        display_title = f"{display_title} · {original_title}"
    text = tmdb_guess_caption(
        content_format,
        display_title,
        candidate.get("overview"),
    )
    fallback_photo = poster_input(candidate.get("poster_path")) or poster_input(
        candidate.get("poster_url")
    )
    cached_file_id = candidate.get("telegram_poster_file_id")
    photo = cached_file_id or fallback_photo
    keyboard = tmdb_guess_keyboard(position, total)
    if photo:
        try:
            return await message.answer_photo(
                photo=photo,
                caption=text,
                parse_mode="HTML",
                reply_markup=keyboard,
            )
        except TelegramBadRequest:
            if cached_file_id:
                if isinstance(candidate, MutableMapping):
                    candidate["telegram_poster_file_id"] = None
                media_id = candidate.get("media_id")
                if media_id:
                    try:
                        await clear_media_telegram_poster_file_id(int(media_id))
                    except (aiosqlite.Error, TypeError, ValueError):
                        pass
            if cached_file_id and fallback_photo:
                try:
                    return await message.answer_photo(
                        photo=fallback_photo,
                        caption=text,
                        parse_mode="HTML",
                        reply_markup=keyboard,
                    )
                except TelegramBadRequest:
                    pass
            return await message.answer(
                text,
                parse_mode="HTML",
                reply_markup=keyboard,
            )
    return await message.answer(text, parse_mode="HTML", reply_markup=keyboard)


@router.callback_query(
    MenuState.confirming_tmdb_guess,
    F.data.in_({"tmdb_guess:previous", "tmdb_guess:next"}),
)
async def navigate_tmdb_guesses(callback: CallbackQuery, state: FSMContext) -> None:
    if not callback.data or not callback.message:
        return
    if not await is_active_tmdb_guess(callback, state):
        await callback.answer(STALE_GUESS)
        return

    data = await state.get_data()
    candidates = data.get("tmdb_candidates", [])
    if (
        not isinstance(candidates, list)
        or not 1 < len(candidates) <= MAX_TITLE_CANDIDATES
    ):
        await callback.answer(STALE_GUESS)
        return

    current = int(data.get("tmdb_candidate_index", 0))
    step = -1 if callback.data == "tmdb_guess:previous" else 1
    position = (current + step) % len(candidates)
    candidate = candidates[position]
    if not isinstance(candidate, dict):
        await callback.answer(STALE_GUESS)
        return

    if not await delete_message_safely(callback.message):
        await callback.answer(TMDB_FAILED, show_alert=True)
        return
    await callback.answer()
    guess_message = await _send_candidate(
        callback.message,
        candidate,
        data.get("content_format", ""),
        position,
        len(candidates),
    )
    telegram_poster_file_id = sent_photo_file_id(guess_message) or candidate.get(
        "telegram_poster_file_id"
    )
    if telegram_poster_file_id and candidate.get("media_id"):
        try:
            await update_media_telegram_poster_file_id(
                int(candidate["media_id"]),
                telegram_poster_file_id,
            )
        except aiosqlite.Error:
            pass
    workflow_data = MediaWorkflowData.from_tmdb_candidate(
        candidate,
        content_format=data.get("content_format", ""),
        content_type=data.get("content_type", "movie"),
    ).to_fsm_dict()
    workflow_data["telegram_poster_file_id"] = telegram_poster_file_id
    await state.update_data(
        tmdb_candidate_index=position,
        tmdb_guess_message_id=guess_message.message_id,
        **workflow_data,
    )


@router.callback_query(
    MenuState.confirming_tmdb_guess,
    F.data == "tmdb_guess:position",
)
async def show_tmdb_guess_position(
    callback: CallbackQuery,
    state: FSMContext,
) -> None:
    if not await is_active_tmdb_guess(callback, state):
        await callback.answer(STALE_GUESS)
        return
    data = await state.get_data()
    candidates = data.get("tmdb_candidates", [])
    position = int(data.get("tmdb_candidate_index", 0))
    await callback.answer(f"Вариант {position + 1} из {len(candidates)}")


@router.callback_query(MenuState.confirming_tmdb_guess, F.data == "tmdb_guess:yes")
async def confirm_tmdb_guess(callback: CallbackQuery, state: FSMContext) -> None:
    if not await is_active_tmdb_guess(callback, state):
        await callback.answer(STALE_GUESS)
        return

    data = await state.get_data()
    try:
        if await _already_in_library(data, callback.from_user.id):
            await callback.answer(ALREADY_IN_LIBRARY, show_alert=True)
            return
    except aiosqlite.Error:
        await callback.answer(LOCAL_SEARCH_FAILED, show_alert=True)
        return

    is_released = bool(data.get("is_released", True))
    release_date = data.get("tmdb_release_date")
    if data.get("content_format") == "full_length":
        tmdb_id = data.get("tmdb_id")
        if type(tmdb_id) is int and tmdb_id > 0:
            try:
                details = await fetch_movie_details(tmdb_id)
            except (TmdbError, ValueError):
                is_released = False
            else:
                release_date = details.release_date
                is_released = (
                    release_date_has_passed(release_date)
                    if release_date
                    else details.status == "Released"
                )

    await callback.answer()
    await state.update_data(
        tmdb_candidates=[],
        tmdb_candidate_index=0,
        tmdb_guess_message_id=None,
        tmdb_release_date=release_date,
        is_released=is_released,
    )
    await delete_message_safely(callback.message)
    await callback.message.answer(
        WATCH_STATUS_PROMPT,
        parse_mode="HTML",
        reply_markup=watch_status_keyboard(allow_completed=is_released),
    )
    await state.set_state(MenuState.choosing_watch_status)


async def _already_in_library(data: dict, user_id: int) -> bool:
    media_id = current_media_id(data)
    if media_id is None:
        tmdb_id = data.get("tmdb_id")
        content_format = data.get("content_format")
        if not tmdb_id or not content_format:
            return False
        media = await get_media_by_tmdb(
            tmdb_id,
            content_format,
            data.get("content_type", "movie"),
        )
        if media is None:
            return False
        media_id = media["id"]
    return await get_user_media(user_id, media_id) is not None


@router.callback_query(MenuState.confirming_tmdb_guess, F.data == "tmdb_guess:no")
async def reject_tmdb_guess(callback: CallbackQuery, state: FSMContext) -> None:
    if not callback.message:
        return
    if not await is_active_tmdb_guess(callback, state):
        await callback.answer(STALE_GUESS)
        return

    await state.set_state(MenuState.choosing_tmdb_retry)
    await state.update_data(
        tmdb_candidates=[],
        tmdb_candidate_index=0,
        tmdb_guess_message_id=None,
    )
    data = await state.get_data()
    await callback.message.answer(
        REJECTED_GUESS,
        reply_markup=tmdb_retry_keyboard(
            data.get("action"),
            data.get("content_format"),
        ),
    )
    await callback.answer()


__all__ = (
    "confirm_tmdb_guess",
    "navigate_tmdb_guesses",
    "reject_tmdb_guess",
    "show_candidates",
    "show_tmdb_guess_position",
)
