"""Business rules and persistence orchestration for series tracking."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from src.database.connection import connection_scope
from src.database.media import get_media_by_tmdb
from src.database.series import (
    get_media_seasons,
    get_user_season_progress,
    save_user_series_progress,
)
from src.database.series_release import update_media_series_release_info
from src.models import SeriesReleaseSnapshot, current_media_id
from src.services.media import ensure_media
from src.services.series_metadata import normalize_seasons


class SeriesProgressError(ValueError):
    """Raised when series progress violates the tracking workflow rules."""


class EmptySeriesProgressError(SeriesProgressError):
    """Raised when a completed tracking flow contains no watched episodes."""


@dataclass(frozen=True)
class SeriesTrackingStart:
    media_id: int | None
    seasons_data: list[dict[str, Any]]
    total_episodes: int
    release_data: dict[str, Any]
    watched: dict[int, int]

    def to_fsm_dict(self) -> dict[str, Any]:
        return {
            "media_id": self.media_id,
            "seasons_data": self.seasons_data,
            "total_episodes": self.total_episodes,
            **self.release_data,
            "watched_by_season": self.watched,
            "current_season": None,
            "episodes_watched_total": sum(self.watched.values()),
        }


@dataclass(frozen=True)
class SeriesTrackingResult:
    media_id: int
    title: str
    total_episodes: int
    announced_episodes: int
    watched_total: int
    average: float | None
    is_ongoing: bool


def season_episode_limits(seasons_data: Sequence[Mapping[str, Any]]) -> dict[int, int]:
    """Build validated per-season episode limits from release data."""
    limits: dict[int, int] = {}
    for season in seasons_data:
        season_number = season.get("season_number")
        episode_count = season.get("episode_count")
        if not _is_positive_int(season_number):
            raise SeriesProgressError("Invalid season number")
        if not _is_nonnegative_int(episode_count):
            raise SeriesProgressError("Invalid season episode count")
        if season_number in limits:
            raise SeriesProgressError("Duplicate season number")
        limits[season_number] = episode_count
    return limits


def validate_series_progress(
    seasons: Mapping[int, int],
    seasons_data: Sequence[Mapping[str, Any]],
    total_episodes: int,
) -> dict[int, int]:
    """Return a safe copy after validating all progress against season limits."""
    if not _is_nonnegative_int(total_episodes):
        raise SeriesProgressError("Invalid total episode count")

    limits = season_episode_limits(seasons_data)
    if sum(limits.values()) != total_episodes:
        raise SeriesProgressError("Season limits do not match the total episode count")

    validated: dict[int, int] = {}
    for season_number, episodes_watched in seasons.items():
        if not _is_positive_int(season_number):
            raise SeriesProgressError("Invalid season number")
        if not _is_nonnegative_int(episodes_watched):
            raise SeriesProgressError("Invalid watched episode count")
        episode_limit = limits.get(season_number)
        if episode_limit is None:
            raise SeriesProgressError("Unknown season")
        if episodes_watched > episode_limit:
            raise SeriesProgressError("Watched episode count exceeds the season limit")
        validated[season_number] = episodes_watched

    return validated


def apply_episode_selection(
    seasons: Mapping[int, int],
    seasons_data: Sequence[Mapping[str, Any]],
    total_episodes: int,
    *,
    current_season: int | None,
    season_number: int,
    episodes_watched: int,
) -> dict[int, int]:
    """Apply an episode choice only to the season currently open in the UI."""
    if current_season != season_number:
        raise SeriesProgressError("Episode selection belongs to a stale season")

    updated = dict(seasons)
    updated[season_number] = episodes_watched
    return validate_series_progress(updated, seasons_data, total_episodes)


def restore_progress_keys(value: object) -> dict[int, int]:
    """Restore integer season keys after Redis JSON serialization."""
    if not isinstance(value, Mapping):
        raise SeriesProgressError("Invalid progress state")

    progress: dict[int, int] = {}
    for raw_season, episodes_watched in value.items():
        if type(raw_season) is int:
            season_number = raw_season
        elif (
            isinstance(raw_season, str)
            and raw_season.isascii()
            and raw_season.isdigit()
            and str(int(raw_season)) == raw_season
        ):
            season_number = int(raw_season)
        else:
            raise SeriesProgressError("Invalid season key in progress state")
        if season_number in progress:
            raise SeriesProgressError("Duplicate season in progress state")
        progress[season_number] = episodes_watched
    return progress


def merge_tracking_season_limits(
    fresh_seasons: Sequence[Mapping[str, Any]],
    cached_seasons: Sequence[Mapping[str, Any]],
    progress: Mapping[int, int],
) -> list[dict[str, Any]]:
    """Build non-decreasing UI limits from TMDB, cache and user progress."""
    merged: dict[int, dict[str, Any]] = {}
    for season in cached_seasons:
        season_number = season.get("season_number")
        available = season.get("available_episode_count")
        announced = season.get("announced_episode_count")
        if not _is_positive_int(season_number) or not _is_nonnegative_int(available):
            raise SeriesProgressError("Invalid cached season limits")
        if not _is_nonnegative_int(announced):
            raise SeriesProgressError("Invalid cached announced episode count")
        merged[season_number] = {
            "season_number": season_number,
            "name": str(season.get("name") or f"Сезон {season_number}"),
            "episode_count": available,
            "announced_episode_count": max(announced, available),
        }

    for season in fresh_seasons:
        season_number = season.get("season_number")
        available = season.get("episode_count")
        announced = season.get("announced_episode_count", available)
        if not _is_positive_int(season_number) or not _is_nonnegative_int(available):
            raise SeriesProgressError("Invalid fresh season limits")
        if not _is_nonnegative_int(announced):
            raise SeriesProgressError("Invalid fresh announced episode count")
        current = merged.get(season_number)
        merged[season_number] = {
            "season_number": season_number,
            "name": str(season.get("name") or (current or {}).get("name") or ""),
            "episode_count": max(
                available,
                int((current or {}).get("episode_count", 0)),
            ),
            "announced_episode_count": max(
                announced,
                int((current or {}).get("announced_episode_count", 0)),
                available,
            ),
        }

    for season_number, episodes_watched in progress.items():
        if not _is_positive_int(season_number) or not _is_nonnegative_int(
            episodes_watched
        ):
            raise SeriesProgressError("Invalid saved progress")
        current = merged.get(season_number)
        if current is None:
            current = {
                "season_number": season_number,
                "name": f"Сезон {season_number}",
                "episode_count": 0,
                "announced_episode_count": 0,
            }
            merged[season_number] = current
        current["episode_count"] = max(current["episode_count"], episodes_watched)
        current["announced_episode_count"] = max(
            current["announced_episode_count"],
            current["episode_count"],
        )

    return [
        merged[number] for number in sorted(merged) if merged[number]["episode_count"]
    ]


async def load_saved_progress(
    user_id: int,
    media_id: int | None,
) -> dict[int, int]:
    if media_id is None:
        return {}
    rows = await get_user_season_progress(user_id, media_id)
    return {
        int(row["season_number"]): int(row["episodes_watched"])
        for row in rows
        if int(row["season_number"]) != 0
    }


async def prepare_series_tracking(
    fsm_data: Mapping[str, Any],
    user_id: int,
    snapshot: SeriesReleaseSnapshot,
) -> SeriesTrackingStart:
    seasons_data = normalize_seasons(snapshot)
    media_id = await _resolve_media_id(fsm_data)
    saved = await load_saved_progress(user_id, media_id)
    cached_seasons = await get_media_seasons(media_id) if media_id is not None else []
    seasons_data = merge_tracking_season_limits(
        seasons_data,
        cached_seasons,
        saved,
    )
    total_episodes = sum(int(season["episode_count"]) for season in seasons_data)
    watched = dict(saved)
    watched = validate_series_progress(watched, seasons_data, total_episodes)
    return SeriesTrackingStart(
        media_id=media_id,
        seasons_data=seasons_data,
        total_episodes=total_episodes,
        release_data=snapshot.to_fsm_dict(),
        watched=watched,
    )


async def save_series_tracking_result(
    fsm_data: Mapping[str, Any],
    user_id: int,
    *,
    database_url: str | None = None,
) -> SeriesTrackingResult:
    total = fsm_data.get("total_episodes", 0)
    announced_total = fsm_data.get("announced_total_episodes", total)
    watched = validate_series_progress(
        restore_progress_keys(fsm_data.get("watched_by_season", {})),
        fsm_data.get("seasons_data", []),
        total,
    )
    watched_total = sum(watched.values())
    if watched_total == 0:
        raise EmptySeriesProgressError("No watched episodes")

    average = fsm_data.get("rating_average")
    is_ongoing = bool(fsm_data.get("is_ongoing"))
    release_snapshot = SeriesReleaseSnapshot.from_fsm(fsm_data)
    async with connection_scope(database_url) as connection:
        media_id = await ensure_media(
            fsm_data,
            "series",
            number_of_seasons=fsm_data.get("total_seasons"),
            number_of_episodes=announced_total,
            available_episode_count=total,
            connection=connection,
        )
        await update_media_series_release_info(
            media_id,
            user_id=user_id,
            snapshot=release_snapshot,
            connection=connection,
        )
        await save_user_series_progress(
            user_id=user_id,
            media_id=media_id,
            seasons=watched,
            total_episodes=total,
            is_ongoing=is_ongoing,
            user_rating=round(average) if average is not None else None,
            rating_details=(
                None
                if fsm_data.get("library_progress_edit")
                else fsm_data.get("ratings")
            ),
            connection=connection,
        )
    return SeriesTrackingResult(
        media_id=media_id,
        title=str(fsm_data.get("tmdb_title") or ""),
        total_episodes=total,
        announced_episodes=announced_total,
        watched_total=watched_total,
        average=average,
        is_ongoing=is_ongoing,
    )


async def _resolve_media_id(fsm_data: Mapping[str, Any]) -> int | None:
    media_id = current_media_id(fsm_data)
    if media_id is not None:
        return media_id

    existing = await get_media_by_tmdb(
        int(fsm_data.get("tmdb_id") or 0),
        "series",
        str(fsm_data.get("content_type") or "movie"),
    )
    return int(existing["id"]) if existing is not None else None


def _is_nonnegative_int(value: object) -> bool:
    return type(value) is int and value >= 0


def _is_positive_int(value: object) -> bool:
    return type(value) is int and value > 0


__all__ = (
    "EmptySeriesProgressError",
    "SeriesProgressError",
    "SeriesTrackingResult",
    "SeriesTrackingStart",
    "apply_episode_selection",
    "load_saved_progress",
    "merge_tracking_season_limits",
    "prepare_series_tracking",
    "restore_progress_keys",
    "save_series_tracking_result",
    "season_episode_limits",
    "validate_series_progress",
)
