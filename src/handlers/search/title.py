"""Title input validation and search orchestration."""

import aiosqlite
from aiogram.fsm.context import FSMContext
from aiogram.types import Message

from src.fsm import MenuState
from src.lang import (
    FORMAT_MISSING,
    LOCAL_SEARCH_FAILED,
    TITLE_AS_TEXT,
    TITLE_EMPTY,
    TMDB_AUTH_FAILED,
    TMDB_FAILED,
    TMDB_NOT_CONFIGURED,
    TMDB_RATE_LIMITED,
    TMDB_SEARCHING,
    TMDB_SEARCHING_REMOTE,
    TMDB_TOO_LONG,
    TMDB_UNAVAILABLE,
    tmdb_found_text,
    tmdb_not_found_text,
)
from src.services.title_search import search_title_candidates
from src.tmdb_models import (
    TmdbAuthenticationError,
    TmdbError,
    TmdbNotConfiguredError,
    TmdbNotFoundError,
    TmdbRateLimitError,
    TmdbUnavailableError,
)

from .candidates import show_candidates
from .router import router


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

    status_message = await message.answer(TMDB_SEARCHING, parse_mode="HTML")
    content_type = data.get("content_type", "movie")

    async def show_remote_search_status() -> None:
        await status_message.edit_text(TMDB_SEARCHING_REMOTE)

    try:
        candidates = await search_title_candidates(
            title_query,
            content_format,
            content_type,
            remote_search_started=show_remote_search_status,
        )
    except aiosqlite.Error:
        await status_message.edit_text(LOCAL_SEARCH_FAILED)
        return
    except (ValueError, TmdbError) as exc:
        text, parse_mode = _search_error(exc, title_query)
        await status_message.edit_text(text, parse_mode=parse_mode)
        return

    await status_message.edit_text(
        tmdb_found_text(candidates[0].title),
        parse_mode="HTML",
    )
    await show_candidates(
        message,
        state,
        candidates,
        content_format,
        content_type,
    )


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


__all__ = ("search_title",)
