"""Public search-handler facade and registration imports."""

from .candidates import (
    confirm_tmdb_guess,
    navigate_tmdb_guesses,
    reject_tmdb_guess,
    show_tmdb_guess_position,
)
from .router import router
from .title import search_title
from .watch_status import choose_watch_status

__all__ = (
    "choose_watch_status",
    "confirm_tmdb_guess",
    "navigate_tmdb_guesses",
    "reject_tmdb_guess",
    "router",
    "search_title",
    "show_tmdb_guess_position",
)
