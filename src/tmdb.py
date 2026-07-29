"""Backward-compatible public facade for the TMDB integration."""

from src.tmdb_matching import (
    ANIMATION_GENRE_ID,
    MIN_RELEVANCE,
    STOP_WORDS,
    title_relevance_score,
)
from src.tmdb_models import (
    TmdbAuthenticationError,
    TmdbEpisodeAirInfo,
    TmdbError,
    TmdbNotConfiguredError,
    TmdbNotFoundError,
    TmdbRateLimitError,
    TmdbSeasonInfo,
    TmdbTitle,
    TmdbTvDetails,
    TmdbUnavailableError,
)
from src.tmdb_parsing import TMDB_IMAGE_URL
from src.tmdb_search import (
    MAX_TITLE_CANDIDATES,
    fetch_title_details,
    find_title_candidates,
    find_title_guess,
)
from src.tmdb_series import fetch_tv_details

__all__ = (
    "ANIMATION_GENRE_ID",
    "MIN_RELEVANCE",
    "MAX_TITLE_CANDIDATES",
    "STOP_WORDS",
    "TMDB_IMAGE_URL",
    "TmdbAuthenticationError",
    "TmdbEpisodeAirInfo",
    "TmdbError",
    "TmdbNotConfiguredError",
    "TmdbNotFoundError",
    "TmdbRateLimitError",
    "TmdbSeasonInfo",
    "TmdbTitle",
    "TmdbTvDetails",
    "TmdbUnavailableError",
    "fetch_title_details",
    "fetch_tv_details",
    "find_title_candidates",
    "find_title_guess",
    "title_relevance_score",
)
