"""Application services shared by handlers."""

from src.services.completed_movie import save_completed_movie
from src.services.media import ensure_media
from src.services.series_tracking import (
    SeriesProgressError,
    apply_episode_selection,
    season_episode_limits,
    validate_series_progress,
)

__all__ = (
    "SeriesProgressError",
    "apply_episode_selection",
    "ensure_media",
    "save_completed_movie",
    "season_episode_limits",
    "validate_series_progress",
)
