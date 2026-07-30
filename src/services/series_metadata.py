"""Loading and normalization of series release metadata."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from src.database.media import get_media_by_id
from src.database.series import get_media_seasons
from src.models import (
    SeriesReleaseSnapshot,
    SeriesSeason,
    current_media_id,
    is_active_series,
)
from src.tmdb_series import fetch_tv_details


class SeriesMetadataError(RuntimeError):
    """Raised when release metadata cannot be prepared for tracking."""


def snapshot_from_cached_rows(
    fsm_data: Mapping[str, Any],
    rows: Sequence[Mapping[str, Any]],
) -> SeriesReleaseSnapshot:
    """Combine cached season rows with release fields already stored in FSM."""
    return SeriesReleaseSnapshot.from_fsm(
        fsm_data,
        seasons=tuple(SeriesSeason.from_mapping(row) for row in rows),
    )


async def load_series_release_snapshot(
    fsm_data: Mapping[str, Any],
    *,
    database_url: str | None = None,
) -> SeriesReleaseSnapshot:
    """Use catalogue metadata when present; fetch TMDB only for a new title."""
    media_id = current_media_id(fsm_data)
    if media_id is not None:
        return await load_cached_series_release_snapshot(
            media_id,
            database_url=database_url,
        )
    if fsm_data.get("library_progress_edit"):
        raise SeriesMetadataError("Library media id is missing")

    return await fetch_tv_details(
        int(fsm_data.get("tmdb_id") or 0),
        include_episode_availability=True,
    )


async def load_cached_series_release_snapshot(
    media_id: int,
    *,
    database_url: str | None = None,
) -> SeriesReleaseSnapshot:
    media = await get_media_by_id(media_id, database_url=database_url)
    if media is None:
        raise SeriesMetadataError("Catalogue series is missing")
    rows = await get_media_seasons(media_id, database_url=database_url)
    if not rows:
        raise SeriesMetadataError("Cached seasons are missing")
    seasons = tuple(SeriesSeason.from_mapping(row) for row in rows)
    return SeriesReleaseSnapshot.from_library_item(media, seasons=seasons)


def normalize_seasons(snapshot: SeriesReleaseSnapshot) -> list[dict[str, Any]]:
    """Return regular, non-empty seasons in the FSM-compatible shape."""
    return snapshot.season_dicts(include_empty=False)


def count_available_episodes(snapshot: SeriesReleaseSnapshot) -> int:
    return sum(season["episode_count"] for season in normalize_seasons(snapshot))


__all__ = (
    "SeriesMetadataError",
    "count_available_episodes",
    "is_active_series",
    "load_cached_series_release_snapshot",
    "load_series_release_snapshot",
    "normalize_seasons",
    "snapshot_from_cached_rows",
)
