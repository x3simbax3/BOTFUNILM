"""Atomic persistence for completed movies."""

from collections.abc import Mapping
from typing import Any

from src.database.connection import connection_scope
from src.database.user_media import save_user_media
from src.release_availability import release_date_has_passed
from src.services.media import ensure_media
from src.tmdb_movie import fetch_movie_details


class UnreleasedMediaError(ValueError):
    pass


async def save_completed_movie(
    user_id: int,
    workflow_data: Mapping[str, Any],
    average: float,
    *,
    database_url: str | None = None,
) -> int:
    """Upsert catalogue metadata and completed user entry in one transaction."""
    if not bool(workflow_data.get("is_released", True)):
        raise UnreleasedMediaError("Media has not been released yet")
    fresh_workflow = dict(workflow_data)
    tmdb_id = workflow_data.get("tmdb_id")
    if type(tmdb_id) is int and tmdb_id > 0:
        details = await fetch_movie_details(tmdb_id)
        is_released = (
            release_date_has_passed(details.release_date)
            if details.release_date
            else details.status == "Released"
        )
        if not is_released:
            raise UnreleasedMediaError("Media has not been released yet")
        fresh_workflow["tmdb_release_date"] = details.release_date
        fresh_workflow["is_released"] = True
    async with connection_scope(database_url) as connection:
        media_id = await ensure_media(
            fresh_workflow,
            "full_length",
            connection=connection,
        )
        await save_user_media(
            user_id=user_id,
            media_id=media_id,
            status="completed",
            user_rating=round(average),
            rating_details=fresh_workflow.get("ratings"),
            connection=connection,
        )
    return media_id


__all__ = ("UnreleasedMediaError", "save_completed_movie")
