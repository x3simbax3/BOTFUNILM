"""Small raw-SQL database API."""

from src.database.connection import connect_database, connection_scope
from src.database.queries import (
    find_media_by_title,
    get_media_by_tmdb,
    get_user_library_filters,
    get_user_library_item,
    get_user_media,
    get_user_season_progress,
    list_user_library,
    save_user_series_progress,
    save_user_media,
    upsert_media,
    update_user_library_filter,
    update_media_poster,
)

__all__ = (
    "connect_database",
    "connection_scope",
    "find_media_by_title",
    "get_media_by_tmdb",
    "get_user_library_filters",
    "get_user_library_item",
    "get_user_media",
    "get_user_season_progress",
    "list_user_library",
    "save_user_series_progress",
    "save_user_media",
    "upsert_media",
    "update_user_library_filter",
    "update_media_poster",
)
