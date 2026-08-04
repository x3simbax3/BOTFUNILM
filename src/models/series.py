"""Shared models for series release metadata."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

ACTIVE_SERIES_STATUSES = frozenset({"Returning Series", "Planned", "In Production"})


def is_active_series(status: str | None, in_production: bool | None) -> bool:
    return bool(in_production) or status in ACTIVE_SERIES_STATUSES


@dataclass(frozen=True)
class SeriesSeason:
    season_number: int
    name: str
    episode_count: int
    available_episode_count: int | None = None

    @classmethod
    def from_mapping(cls, season: Mapping[str, Any]) -> SeriesSeason:
        announced = _get(
            season,
            "announced_episode_count",
            _get(season, "episode_count", 0),
        )
        available = _get(
            season,
            "available_episode_count",
            _get(season, "episode_count"),
        )
        return cls(
            season_number=int(season["season_number"]),
            name=str(season["name"]),
            episode_count=int(announced),
            available_episode_count=(int(available) if available is not None else None),
        )

    @property
    def announced_episode_count(self) -> int:
        return self.episode_count

    @property
    def aired_episode_count(self) -> int:
        if self.available_episode_count is None:
            return self.episode_count
        return self.available_episode_count

    def to_fsm_dict(self) -> dict[str, Any]:
        return {
            "season_number": self.season_number,
            "name": self.name,
            "episode_count": self.aired_episode_count,
            "announced_episode_count": self.episode_count,
        }


@dataclass(frozen=True)
class SeriesEpisode:
    season_number: int
    episode_number: int
    air_date: str | None


@dataclass(frozen=True)
class SeriesReleaseSnapshot:
    number_of_seasons: int
    number_of_episodes: int
    seasons: tuple[SeriesSeason, ...]
    status: str | None = None
    in_production: bool | None = None
    next_episode_to_air: SeriesEpisode | None = None
    last_episode_to_air: SeriesEpisode | None = None
    poster_path: str | None = None
    rating: float | None = None
    title: str | None = None
    original_title: str | None = None
    description: str | None = None
    first_air_date: str | None = None

    def __post_init__(self) -> None:
        """Freeze season collections even when callers provide a list."""
        object.__setattr__(self, "seasons", tuple(self.seasons))

    @classmethod
    def from_library_item(
        cls,
        item: Mapping[str, Any],
        *,
        seasons: Sequence[SeriesSeason] = (),
    ) -> SeriesReleaseSnapshot:
        return cls(
            number_of_seasons=int(_get(item, "number_of_seasons") or len(seasons)),
            number_of_episodes=int(_get(item, "number_of_episodes") or 0),
            seasons=seasons,
            status=_get(item, "tmdb_status"),
            in_production=_optional_bool(_get(item, "tmdb_in_production")),
            next_episode_to_air=_episode_from_values(
                _get(item, "next_episode_season_number"),
                _get(item, "next_episode_number"),
                _get(item, "next_episode_air_date"),
            ),
            poster_path=_get(item, "poster_path"),
            rating=_get(item, "rating"),
        )

    @classmethod
    def from_fsm(
        cls,
        data: Mapping[str, Any],
        *,
        seasons: Sequence[SeriesSeason] | None = None,
    ) -> SeriesReleaseSnapshot:
        resolved_seasons = (
            list(seasons)
            if seasons is not None
            else [
                SeriesSeason.from_mapping(season)
                for season in data.get("seasons_data", [])
            ]
        )
        return cls(
            number_of_seasons=int(data.get("total_seasons") or len(resolved_seasons)),
            number_of_episodes=int(
                data.get("announced_total_episodes")
                or sum(season.episode_count for season in resolved_seasons)
            ),
            seasons=resolved_seasons,
            status=data.get("tmdb_series_status"),
            in_production=_optional_bool(data.get("tmdb_series_in_production")),
            next_episode_to_air=_episode_from_values(
                data.get("tmdb_next_episode_season_number"),
                data.get("tmdb_next_episode_number"),
                data.get("tmdb_next_episode_air_date"),
            ),
            poster_path=data.get("tmdb_poster_path"),
            rating=data.get("tmdb_rating"),
        )

    @property
    def announced_episode_count(self) -> int:
        return self.number_of_episodes

    @property
    def available_episode_count(self) -> int:
        return sum(season.aired_episode_count for season in self.regular_seasons)

    @property
    def next_episode(self) -> SeriesEpisode | None:
        return self.next_episode_to_air

    @property
    def active(self) -> bool:
        return is_active_series(self.status, self.in_production)

    @property
    def regular_seasons(self) -> list[SeriesSeason]:
        return [season for season in self.seasons if season.season_number > 0]

    def season_dicts(self, *, include_empty: bool = True) -> list[dict[str, Any]]:
        return [
            season.to_fsm_dict()
            for season in self.regular_seasons
            if include_empty or season.episode_count > 0
        ]

    def to_fsm_dict(self) -> dict[str, Any]:
        next_episode = self.next_episode_to_air
        return {
            "total_seasons": self.number_of_seasons,
            "announced_total_episodes": self.number_of_episodes,
            "is_ongoing": self.active,
            "is_airing": self.next_episode is not None,
            "tmdb_series_status": self.status,
            "tmdb_series_in_production": self.in_production,
            "tmdb_next_episode_air_date": (
                next_episode.air_date if next_episode is not None else None
            ),
            "tmdb_next_episode_season_number": (
                next_episode.season_number if next_episode is not None else None
            ),
            "tmdb_next_episode_number": (
                next_episode.episode_number if next_episode is not None else None
            ),
        }


def _episode_from_values(
    season_number: object,
    episode_number: object,
    air_date: object,
) -> SeriesEpisode | None:
    if type(season_number) is not int or type(episode_number) is not int:
        return None
    return SeriesEpisode(
        season_number=season_number,
        episode_number=episode_number,
        air_date=air_date if isinstance(air_date, str) else None,
    )


def _optional_bool(value: object) -> bool | None:
    if value is None:
        return None
    return bool(value)


def _get(source: Mapping[str, Any], key: str, default: Any = None) -> Any:
    try:
        return source[key]
    except (IndexError, KeyError):
        return default
