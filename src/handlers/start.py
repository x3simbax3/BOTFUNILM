"""Compatibility facade for the handlers split into domain modules.

New code should import from the specific handler module. The re-exports keep the
previous public surface available for integrations while the aggregate router
preserves the original registration entry point.
"""

from aiogram import Router

from src.handlers.common import (
    CAPTION_ELLIPSIS,
    PHOTO_CAPTION_LIMIT,
    edit_message as _edit_message,
    is_active_tmdb_guess as _is_active_tmdb_guess,
    limit_caption_description as _limit_caption_description,
    replace_message as _replace_message,
    tmdb_guess_caption as _tmdb_guess_caption,
)
from src.handlers.library import (
    LIBRARY_PAGE_SIZE,
    back_to_library,
    change_library_filter,
    change_library_page,
    library_item_caption as _library_item_caption,
    media_id_from_start as _media_id_from_start,
    open_library,
    open_library_page as _open_library_page,
    router as library_router,
    show_library_item as _show_library_item,
)
from src.handlers.menu import (
    MENU_TREE,
    choose_action,
    choose_content_type,
    choose_format,
    clear_step_data as _clear_step_data,
    go_back,
    retry_title,
    router as menu_router,
    start,
)
from src.handlers.rating import (
    finish_movie as _finish_movie,
    handle_rating,
    router as rating_router,
)
from src.handlers.search import (
    confirm_tmdb_guess,
    reject_tmdb_guess,
    router as search_router,
    search_title,
)
from src.handlers.series import (
    finish_series_tracking as _finish_series_tracking,
    handle_episode_selection,
    handle_season_selection,
    router as series_router,
    start_series_tracking as _start_series_tracking,
)
from src.tmdb import TMDB_IMAGE_URL


router = Router(name="start")
router.include_routers(
    menu_router,
    library_router,
    search_router,
    rating_router,
    series_router,
)


__all__ = (
    "CAPTION_ELLIPSIS",
    "LIBRARY_PAGE_SIZE",
    "MENU_TREE",
    "PHOTO_CAPTION_LIMIT",
    "TMDB_IMAGE_URL",
    "back_to_library",
    "change_library_filter",
    "change_library_page",
    "choose_action",
    "choose_content_type",
    "choose_format",
    "confirm_tmdb_guess",
    "go_back",
    "handle_episode_selection",
    "handle_rating",
    "handle_season_selection",
    "open_library",
    "reject_tmdb_guess",
    "retry_title",
    "router",
    "search_title",
    "start",
)
