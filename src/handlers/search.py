"""Title search and TMDB result confirmation handlers."""

import aiosqlite
from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from src.database.media import (
    find_media_by_title,
    get_media_by_tmdb,
    update_media_poster,
)
from src.database.user_media import get_user_media, save_user_media
from src.fsm import MenuState
from src.handlers.common import (
    delete_message_safely,
    is_active_tmdb_guess,
    tmdb_guess_caption,
)
from src.keyboards import (
    main_menu_keyboard,
    rating_keyboard,
    tmdb_guess_keyboard,
    tmdb_retry_keyboard,
    watch_status_keyboard,
)
from src.lang import (
    ALREADY_IN_LIBRARY,
    FORMAT_MISSING,
    INVALID_WATCH_STATUS,
    LOCAL_SEARCH_FAILED,
    REJECTED_GUESS,
    STALE_GUESS,
    TITLE_AS_TEXT,
    TITLE_EMPTY,
    TITLE_SAVE_FAILED,
    TMDB_AUTH_FAILED,
    TMDB_FAILED,
    TMDB_NOT_CONFIGURED,
    TMDB_RATE_LIMITED,
    TMDB_SEARCHING,
    TMDB_SEARCHING_REMOTE,
    TMDB_TOO_LONG,
    TMDB_UNAVAILABLE,
    WATCH_STATUS_PROMPT,
    planned_title_saved_text,
    rating_categories,
    rating_prompt_text,
    tmdb_found_text,
    tmdb_not_found_text,
)
from src.posters import download_poster, poster_input
from src.services import ensure_media
from src.tmdb import (
    TMDB_IMAGE_URL,
    TmdbAuthenticationError,
    TmdbError,
    TmdbNotConfiguredError,
    TmdbNotFoundError,
    TmdbRateLimitError,
    TmdbTitle,
    TmdbUnavailableError,
    find_title_guess,
)

router = Router(name="search")


@router.message(MenuState.waiting_title)
async def search_title(message: Message, state: FSMContext) -> None:
    title_query = _valid_title_query(message.text)
    if title_query is None:
        await message.answer(TITLE_AS_TEXT if message.text is None else TITLE_EMPTY)
        return
    if len(title_query) > 342:
        await message.answer(TMDB_TOO_LONG)
        return

    data = await state.get_data()
    content_format = data.get("content_format")
    if not content_format:
        await message.answer(FORMAT_MISSING)
        return

    status_msg = await message.answer(TMDB_SEARCHING, parse_mode="HTML")
    content_type = data.get("content_type", "movie")
    local_media = None
    try:
        local_media = await find_media_by_title(
            title_query,
            content_format,
            content_type,
        )
        if local_media is None:
            await status_msg.edit_text(TMDB_SEARCHING_REMOTE)
            guess = await find_title_guess(title_query, content_format, content_type)
        else:
            guess = await _title_from_local_media(
                local_media,
                title_query,
                content_format,
            )
    except aiosqlite.Error:
        await status_msg.edit_text(LOCAL_SEARCH_FAILED)
        return
    except (ValueError, TmdbError) as exc:
        text, parse_mode = _search_error(exc, title_query)
        await status_msg.edit_text(text, parse_mode=parse_mode)
        return

    await status_msg.edit_text(tmdb_found_text(guess.title), parse_mode="HTML")
    await _show_guess(message, state, guess, content_format, local_media)


async def _title_from_local_media(
    local_media,
    title_query: str,
    content_format: str,
) -> TmdbTitle:
    poster_path = local_media["poster_path"]
    if poster_path and poster_path.startswith(("/", "http://", "https://")):
        poster_url = (
            poster_path
            if poster_path.startswith(("http://", "https://"))
            else f"{TMDB_IMAGE_URL}{poster_path}"
        )
        cached_path = await download_poster(
            poster_url,
            local_media["tmdb_id"] or 0,
            content_format,
        )
        if cached_path:
            poster_path = cached_path
            await update_media_poster(local_media["id"], cached_path)

    return TmdbTitle(
        title=local_media["title"],
        overview=local_media["description"],
        poster_url=None,
        original_query=title_query,
        normalized_query=title_query,
        tmdb_id=local_media["tmdb_id"] or 0,
        poster_path=poster_path,
        rating=local_media["rating"],
    )


async def _show_guess(
    message: Message,
    state: FSMContext,
    guess: TmdbTitle,
    content_format: str,
    local_media,
) -> None:
    text = tmdb_guess_caption(content_format, guess.title, guess.overview)
    photo = (
        poster_input(guess.poster_path) if local_media is not None else guess.poster_url
    )
    if photo:
        guess_message = await message.answer_photo(
            photo=photo,
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
        media_id=local_media["id"] if local_media is not None else None,
        tmdb_guess_message_id=guess_message.message_id,
        tmdb_title=guess.title,
        tmdb_id=guess.tmdb_id,
        tmdb_description=guess.overview,
        tmdb_poster_url=guess.poster_url,
        tmdb_poster_path=guess.poster_path,
        tmdb_rating=guess.rating,
    )
    await state.set_state(MenuState.confirming_tmdb_guess)


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

    await callback.answer()
    await state.update_data(tmdb_guess_message_id=None)
    await delete_message_safely(callback.message)
    await callback.message.answer(
        WATCH_STATUS_PROMPT,
        parse_mode="HTML",
        reply_markup=watch_status_keyboard(),
    )
    await state.set_state(MenuState.choosing_watch_status)


async def _already_in_library(data: dict, user_id: int) -> bool:
    media_id = data.get("media_id")
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
    return await get_user_media(user_id, int(media_id)) is not None


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

    if status == "planned":
        data = await state.get_data()
        try:
            media_id = await ensure_media(data, data.get("content_format", ""))
            await save_user_media(
                user_id=callback.from_user.id,
                media_id=media_id,
                status="planned",
            )
        except (aiosqlite.Error, RuntimeError, ValueError):
            await callback.answer(TITLE_SAVE_FAILED, show_alert=True)
            return

        await callback.message.edit_text(
            planned_title_saved_text(data.get("tmdb_title", "")),
            parse_mode="HTML",
        )
        await callback.message.answer(
            "Готово — тайтл сохранён на потом.",
            reply_markup=main_menu_keyboard(),
        )
        await state.set_state(MenuState.choosing_action)
        await callback.answer()
        return

    await state.update_data(ratings={}, rating_index=0)
    data = await state.get_data()
    categories = rating_categories(data.get("content_type", "movie"))
    await callback.message.answer(
        rating_prompt_text(
            data.get("tmdb_title", ""), categories[0][1], 1, len(categories)
        ),
        parse_mode="HTML",
        reply_markup=rating_keyboard(),
    )
    await state.set_state(MenuState.rating_category)
    await callback.answer()


@router.callback_query(MenuState.confirming_tmdb_guess, F.data == "tmdb_guess:no")
async def reject_tmdb_guess(callback: CallbackQuery, state: FSMContext) -> None:
    if not callback.message:
        return
    if not await is_active_tmdb_guess(callback, state):
        await callback.answer(STALE_GUESS)
        return

    await state.set_state(MenuState.choosing_tmdb_retry)
    await state.update_data(tmdb_guess_message_id=None)
    data = await state.get_data()
    await callback.message.answer(
        REJECTED_GUESS,
        reply_markup=tmdb_retry_keyboard(
            data.get("action"),
            data.get("content_format"),
        ),
    )
    await callback.answer()


def _valid_title_query(text: str | None) -> str | None:
    if text is None or not text.strip():
        return None
    return text


def _search_error(error: Exception, query: str) -> tuple[str, str | None]:
    if isinstance(error, ValueError):
        return TITLE_EMPTY, None
    if isinstance(error, TmdbNotConfiguredError):
        return TMDB_NOT_CONFIGURED, None
    if isinstance(error, TmdbAuthenticationError):
        return TMDB_AUTH_FAILED, None
    if isinstance(error, TmdbRateLimitError):
        return TMDB_RATE_LIMITED, None
    if isinstance(error, TmdbUnavailableError):
        return TMDB_UNAVAILABLE, None
    if isinstance(error, TmdbNotFoundError):
        return tmdb_not_found_text(query), "HTML"
    return TMDB_FAILED, None
