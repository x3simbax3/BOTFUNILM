"""Domain models and errors shared by the TMDB integration."""

from dataclasses import dataclass

from src.models.series import SeriesEpisode, SeriesReleaseSnapshot, SeriesSeason


@dataclass(frozen=True)
class TmdbTitle:
    title: str
    overview: str | None
    poster_url: str | None
    original_query: str
    normalized_query: str
    tmdb_id: int = 0
    poster_path: str | None = None
    rating: float | None = None
    original_title: str | None = None
    release_date: str | None = None


TmdbEpisodeAirInfo = SeriesEpisode
TmdbSeasonInfo = SeriesSeason
TmdbTvDetails = SeriesReleaseSnapshot


class TmdbError(Exception):
    """Base error for failures reported by the TMDB integration."""


class TmdbNotConfiguredError(TmdbError):
    pass


class TmdbAuthenticationError(TmdbError):
    pass


class TmdbRateLimitError(TmdbError):
    pass


class TmdbUnavailableError(TmdbError):
    pass


class TmdbNotFoundError(TmdbError):
    def __init__(self, query: str = "") -> None:
        super().__init__()
        self.query = query


__all__ = (
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
)
