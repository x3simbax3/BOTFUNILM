"""Atomic persistence for completed movies."""

from collections.abc import Mapping
from typing import Any

from src.database.connection import connection_scope
from src.database.user_media import save_user_media
from src.services.media import ensure_media


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
    async with connection_scope(database_url) as connection:
        media_id = await ensure_media(
            workflow_data,
            "full_length",
            connection=connection,
        )
        await save_user_media(
            user_id=user_id,
            media_id=media_id,
            status="completed",
            user_rating=round(average),
            rating_details=workflow_data.get("ratings"),
            connection=connection,
        )
    return media_id


__all__ = ("UnreleasedMediaError", "save_completed_movie")
