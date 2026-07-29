"""Compatibility facade for the series tracking service."""

from src.services.series_tracking import (
    SeriesProgressError,
    apply_episode_selection,
    season_episode_limits,
    validate_series_progress,
)

__all__ = (
    "SeriesProgressError",
    "apply_episode_selection",
    "season_episode_limits",
    "validate_series_progress",
)
