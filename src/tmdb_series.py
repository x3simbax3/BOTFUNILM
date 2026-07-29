"""TMDB series details and released-episode availability."""

from datetime import date

import aiohttp

from config.config import TMDB_API, TMDB_LANG, TMDB_URL
from src.http_client import get_http_session
from src.lang import default_season_name
from src.models import is_active_series
from src.tmdb_client import fetch_json
from src.tmdb_models import (
    TmdbEpisodeAirInfo,
    TmdbError,
    TmdbNotConfiguredError,
    TmdbSeasonInfo,
    TmdbTvDetails,
)
from src.tmdb_parsing import _parse_episode_air_info, _parse_rating


async def fetch_tv_details(
    tv_id: int,
    *,
    include_episode_availability: bool = False,
) -> TmdbTvDetails:
    """Fetch regular seasons and episode counts for a TV series."""
    if not TMDB_API:
        raise TmdbNotConfiguredError

    url = f"{TMDB_URL.rstrip('/')}/tv/{tv_id}"
    session = await get_http_session()
    data = await fetch_json(session, url, {"language": TMDB_LANG}, TMDB_API)
    if not data:
        raise TmdbError("Не удалось получить информацию о сериале")

    raw_regular_seasons = [
        season
        for season in data.get("seasons") or []
        if season.get("season_number", 0) > 0
    ]
    next_episode = _parse_episode_air_info(data.get("next_episode_to_air"))
    last_episode = _parse_episode_air_info(data.get("last_episode_to_air"))
    raw_status = data.get("status")
    raw_in_production = data.get("in_production")
    status = raw_status if isinstance(raw_status, str) and raw_status else None
    in_production = raw_in_production if type(raw_in_production) is bool else None
    active = is_active_series(status, in_production)
    seasons = [
        TmdbSeasonInfo(
            season_number=raw_season["season_number"],
            name=raw_season.get(
                "name", default_season_name(raw_season["season_number"])
            ),
            episode_count=raw_season.get("episode_count", 0),
            available_episode_count=_infer_available_episode_count(
                raw_season["season_number"],
                raw_season.get("episode_count", 0),
                active=active,
                next_episode=next_episode,
                last_episode=last_episode,
            ),
        )
        for raw_season in raw_regular_seasons
    ]
    if include_episode_availability and active:
        seasons = await _refresh_active_season_availability(
            session,
            url,
            seasons,
            next_episode=next_episode,
            last_episode=last_episode,
        )

    return TmdbTvDetails(
        number_of_seasons=data.get("number_of_seasons", len(seasons)),
        number_of_episodes=data.get("number_of_episodes", 0),
        seasons=seasons,
        status=status,
        in_production=in_production,
        next_episode_to_air=next_episode,
        last_episode_to_air=last_episode,
        poster_path=(
            data.get("poster_path")
            if isinstance(data.get("poster_path"), str) and data.get("poster_path")
            else None
        ),
        rating=_parse_rating(data.get("vote_average")),
    )


def _infer_available_episode_count(
    season_number: int,
    episode_count: int,
    *,
    active: bool,
    next_episode: TmdbEpisodeAirInfo | None,
    last_episode: TmdbEpisodeAirInfo | None,
) -> int:
    if not active:
        return episode_count
    if next_episode is not None:
        if season_number < next_episode.season_number:
            return episode_count
        if season_number == next_episode.season_number:
            return min(episode_count, next_episode.episode_number - 1)
        return 0
    if last_episode is not None:
        if season_number < last_episode.season_number:
            return episode_count
        if season_number == last_episode.season_number:
            return min(episode_count, last_episode.episode_number)
        return 0
    return episode_count


async def _refresh_active_season_availability(
    session: aiohttp.ClientSession,
    series_url: str,
    seasons: list[TmdbSeasonInfo],
    *,
    next_episode: TmdbEpisodeAirInfo | None,
    last_episode: TmdbEpisodeAirInfo | None,
) -> list[TmdbSeasonInfo]:
    boundary_candidates = [
        episode.season_number
        for episode in (last_episode, next_episode)
        if episode is not None
    ]
    boundary = min(
        boundary_candidates,
        default=max((season.season_number for season in seasons), default=1),
    )
    refreshed = []
    today = date.today()
    for season in seasons:
        if season.season_number < boundary:
            refreshed.append(season)
            continue
        try:
            season_data = await fetch_json(
                session,
                f"{series_url}/season/{season.season_number}",
                {"language": TMDB_LANG},
                TMDB_API,
            )
        except TmdbError:
            refreshed.append(season)
            continue
        available = sum(
            1
            for episode in season_data.get("episodes") or []
            if _episode_has_aired(episode.get("air_date"), today)
        )
        refreshed.append(
            TmdbSeasonInfo(
                season_number=season.season_number,
                name=season.name,
                episode_count=season.episode_count,
                available_episode_count=min(season.episode_count, available),
            )
        )
    return refreshed


def _episode_has_aired(value: object, today: date) -> bool:
    if not isinstance(value, str) or not value:
        return False
    try:
        return date.fromisoformat(value) <= today
    except ValueError:
        return False


__all__ = ("fetch_tv_details",)
