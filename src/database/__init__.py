"""Small raw-SQL database API."""

from src.database.connection import connect_database, connection_scope
from src.database.queries import (
    find_media_by_title,
    get_media_by_tmdb,
    get_user_media,
    get_user_season_progress,
    save_user_series_progress,
    save_user_media,
    upsert_media,
)

__all__ = (
    "connect_database",
    "connection_scope",
    "find_media_by_title",
    "get_media_by_tmdb",
    "get_user_media",
    "get_user_season_progress",
    "save_user_series_progress",
    "save_user_media",
    "upsert_media",
)
