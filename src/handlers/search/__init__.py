"""Search handlers facade and registration imports."""

from src.database.media import update_media_poster
from src.database.media_search import find_media_by_title
from src.database.series_release import update_media_series_release_info
from src.database.user_media import save_user_media
from src.handlers.common import delete_message_safely
from src.posters import download_poster
from src.tmdb import fetch_tv_details, find_title_candidates

from .candidates import (
    _already_in_library as _candidate_already_in_library,
)
from .candidates import (
    confirm_tmdb_guess as _confirm_tmdb_guess,
)
from .candidates import (
    navigate_tmdb_guesses,
    reject_tmdb_guess,
    show_tmdb_guess_position,
)
from .router import router
from .title import search_title as _search_title
from .watch_status import choose_watch_status as _choose_watch_status

_already_in_library = _candidate_already_in_library


async def search_title(message, state) -> None:
    """Compatibility wrapper preserving the former module's patch seams."""
    from src.services import title_search

    title_search.find_media_by_title = find_media_by_title
    title_search.find_title_candidates = find_title_candidates
    title_search.download_poster = download_poster
    title_search.update_media_poster = update_media_poster
    await _search_title(message, state)


async def confirm_tmdb_guess(callback, state) -> None:
    from . import candidates

    candidates.delete_message_safely = delete_message_safely
    candidates._already_in_library = _already_in_library
    await _confirm_tmdb_guess(callback, state)


async def choose_watch_status(callback, state) -> None:
    from src.services import planned_media

    planned_media.fetch_tv_details = fetch_tv_details
    planned_media.save_user_media = save_user_media
    planned_media.update_media_series_release_info = update_media_series_release_info
    await _choose_watch_status(callback, state)


__all__ = (
    "choose_watch_status",
    "confirm_tmdb_guess",
    "navigate_tmdb_guesses",
    "reject_tmdb_guess",
    "router",
    "search_title",
    "show_tmdb_guess_position",
)
