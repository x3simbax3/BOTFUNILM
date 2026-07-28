"""Media catalogue operations shared by movie and series flows."""

from collections.abc import Mapping
from typing import Any

from src.database.media import upsert_media
from src.posters import download_poster


async def ensure_media(
    data: Mapping[str, Any],
    content_format: str,
    *,
    number_of_seasons: int | None = None,
    number_of_episodes: int | None = None,
    available_episode_count: int | None = None,
) -> int:
    """Return an existing media id or create/update its catalogue record."""
    media_id = data.get("media_id")
    if media_id is not None:
        return int(media_id)

    poster_path = await download_poster(
        data.get("tmdb_poster_url"),
        data.get("tmdb_id", 0),
        content_format,
    )
    media_details = {
        "tmdb_id": data.get("tmdb_id"),
        "content_format": content_format,
        "content_type": data.get("content_type", "movie"),
        "title": data.get("tmdb_title", ""),
        "original_title": data.get("tmdb_original_title"),
        "description": data.get("tmdb_description"),
        "poster_path": poster_path or data.get("tmdb_poster_path"),
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

    return await upsert_media(
        **media_details,
    )
