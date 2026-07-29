"""Media catalogue operations shared by movie and series flows."""

from collections.abc import Mapping
from typing import Any

import aiosqlite

from src.database.media import upsert_media
from src.models import current_media_id


async def ensure_media(
    data: Mapping[str, Any],
    content_format: str,
    *,
    number_of_seasons: int | None = None,
    number_of_episodes: int | None = None,
    available_episode_count: int | None = None,
    connection: aiosqlite.Connection | None = None,
) -> int:
    """Return an existing media id or create/update its catalogue record."""
    media_id = current_media_id(data)
    if media_id is not None:
        return media_id

    media_details = {
        "tmdb_id": data.get("tmdb_id"),
        "content_format": content_format,
        "content_type": data.get("content_type", "movie"),
        "title": data.get("tmdb_title", ""),
        "original_title": data.get("tmdb_original_title"),
        "description": data.get("tmdb_description"),
        "poster_path": data.get("tmdb_poster_path"),
        "telegram_poster_file_id": data.get("telegram_poster_file_id"),
    }
    if content_format == "series":
        media_details["first_air_date"] = data.get("tmdb_release_date")
    else:
        media_details["release_date"] = data.get("tmdb_release_date")
    if number_of_seasons is not None:
        media_details["number_of_seasons"] = number_of_seasons
    if number_of_episodes is not None:
        media_details["number_of_episodes"] = number_of_episodes
    if content_format == "series" and available_episode_count is not None:
        media_details["available_episode_count"] = available_episode_count
    if data.get("tmdb_rating") is not None:
        media_details["rating"] = data["tmdb_rating"]

    if connection is None:
        return await upsert_media(**media_details)
    return await upsert_media(**media_details, connection=connection)
