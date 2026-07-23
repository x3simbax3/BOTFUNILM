"""Small raw-SQL database API."""

from src.database.connection import connect_database, connection_scope
from src.database.queries import (
    get_media_by_tmdb,
    get_user_media,
    save_user_media,
    upsert_media,
)

__all__ = (
    "connect_database",
    "connection_scope",
    "get_media_by_tmdb",
    "get_user_media",
    "save_user_media",
    "upsert_media",
)
