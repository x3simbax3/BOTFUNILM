"""Series handlers facade and registration imports."""

from src.database.series import (
    get_media_seasons,
    get_user_season_progress,
    save_user_series_progress,
)
from src.database.series_release import update_media_series_release_info
from src.tmdb import fetch_tv_details

from .finish import finish_series_tracking as _finish_series_tracking
from .navigation import handle_episode_selection, handle_season_selection
from .router import router
from .start import start_series_tracking as _start_series_tracking


async def start_series_tracking(callback, state) -> None:
    """Compatibility wrapper preserving established test and import seams."""
    from src.services import series_metadata, series_tracking

    series_metadata.fetch_tv_details = fetch_tv_details
    series_metadata.get_media_seasons = get_media_seasons
    series_tracking.get_user_season_progress = get_user_season_progress
    await _start_series_tracking(callback, state)


async def finish_series_tracking(callback, state) -> None:
    """Compatibility wrapper for the former monolithic handler module."""
    from src.services import series_tracking

    series_tracking.save_user_series_progress = save_user_series_progress
    series_tracking.update_media_series_release_info = update_media_series_release_info
    await _finish_series_tracking(callback, state)


__all__ = (
    "finish_series_tracking",
    "handle_episode_selection",
    "handle_season_selection",
    "router",
    "start_series_tracking",
)
