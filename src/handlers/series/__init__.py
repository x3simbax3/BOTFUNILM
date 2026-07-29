"""Public series-handler facade and registration imports."""

from .finish import finish_series_tracking
from .navigation import handle_episode_selection, handle_season_selection
from .router import router
from .start import start_series_tracking

__all__ = (
    "finish_series_tracking",
    "handle_episode_selection",
    "handle_season_selection",
    "router",
    "start_series_tracking",
)
