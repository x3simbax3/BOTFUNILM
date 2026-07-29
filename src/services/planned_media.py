"""Saving media to a user's planned list."""

from __future__ import annotations

from dataclasses import dataclass

from src.database.series_release import update_media_series_release_info
from src.database.user_media import save_user_media
from src.models import MediaWorkflowData, SeriesReleaseSnapshot
from src.services.media import ensure_media
from src.tmdb_models import TmdbError
from src.tmdb_series import fetch_tv_details


@dataclass(frozen=True)
class PlannedMediaResult:
    media_id: int
    series_snapshot: SeriesReleaseSnapshot | None = None


async def save_planned_media(
    user_id: int,
    workflow: MediaWorkflowData,
) -> PlannedMediaResult:
    """Upsert catalogue metadata and attach it to the user's planned list."""
    snapshot = await _series_snapshot(workflow)
    media_id = await ensure_media(
        workflow.to_fsm_dict(),
        workflow.content_format,
        number_of_seasons=(snapshot.number_of_seasons if snapshot else None),
        number_of_episodes=(snapshot.number_of_episodes if snapshot else None),
        available_episode_count=(
            snapshot.available_episode_count if snapshot else None
        ),
    )
    if snapshot is not None:
        await update_media_series_release_info(
            media_id,
            user_id=user_id,
            snapshot=snapshot,
        )
    await save_user_media(user_id=user_id, media_id=media_id, status="planned")
    return PlannedMediaResult(media_id=media_id, series_snapshot=snapshot)


async def _series_snapshot(
    workflow: MediaWorkflowData,
) -> SeriesReleaseSnapshot | None:
    if workflow.content_format != "series":
        return None
    try:
        return await fetch_tv_details(
            workflow.tmdb_id or 0,
            include_episode_availability=True,
        )
    except TmdbError:
        return None


__all__ = ("PlannedMediaResult", "save_planned_media")
