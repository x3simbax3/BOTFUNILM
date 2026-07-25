"""Backward-compatible imports for the former monolithic query module.

New code should import from the domain-specific database modules.
"""

from src.database.library import (
    get_user_library_filters,
    get_user_library_item,
    list_user_library,
    update_user_library_filter,
)
from src.database.media import (
    find_media_by_title,
    get_media_by_tmdb,
    update_media_poster,
    upsert_media,
)
from src.database.series import (
    get_user_season_progress,
    save_user_series_progress,
)
from src.database.user_media import get_user_media, save_user_media


__all__ = (
    "find_media_by_title",
    "get_media_by_tmdb",
    "get_user_library_filters",
    "get_user_library_item",
    "get_user_media",
    "get_user_season_progress",
    "list_user_library",
    "save_user_media",
    "save_user_series_progress",
    "update_media_poster",
    "update_user_library_filter",
    "upsert_media",
)
