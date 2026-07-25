"""Business rules for changing and saving series progress."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any


class SeriesProgressError(ValueError):
    """Raised when series progress violates the tracking workflow rules."""


def season_episode_limits(seasons_data: Sequence[Mapping[str, Any]]) -> dict[int, int]:
    """Build validated per-season episode limits from TMDB season data."""
    limits: dict[int, int] = {}
    for season in seasons_data:
        season_number = season.get("season_number")
        episode_count = season.get("episode_count")
        if not _is_nonnegative_int(season_number):
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
        if not _is_nonnegative_int(season_number):
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


def _is_nonnegative_int(value: object) -> bool:
    return type(value) is int and value >= 0


__all__ = (
    "SeriesProgressError",
    "apply_episode_selection",
    "season_episode_limits",
    "validate_series_progress",
)
