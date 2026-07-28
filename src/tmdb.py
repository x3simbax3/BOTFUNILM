"""Public facade and use cases for the TMDB integration.

Matching, transport, and domain types live in dedicated modules. This facade keeps
the established ``src.tmdb`` API stable for handlers and other callers.
"""

import logging
from datetime import date

import aiohttp

from config.config import TMDB_API, TMDB_LANG, TMDB_URL
from src.http_client import get_http_session
from src.lang import default_season_name
from src.tmdb_client import fetch_json as _client_fetch_json
from src.tmdb_matching import (
    ANIMATION_GENRE_ID,
    MIN_RELEVANCE,
    STOP_WORDS,
    filter_by_content_type,
    is_animation,
    is_anime,
    is_cartoon,
    make_queries,
    normalize_text,
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

logger = logging.getLogger(__name__)

TMDB_IMAGE_URL = "https://image.tmdb.org/t/p/original"
MAX_TITLE_CANDIDATES = 5

# Compatibility aliases for existing callers and tests. New code should import
# public matching functions from src.tmdb_matching directly when appropriate.
_normalize_text = normalize_text
_make_queries = make_queries
_relevance_score = title_relevance_score
_filter_by_content_type = filter_by_content_type
_is_animation = is_animation
_is_anime = is_anime
_is_cartoon = is_cartoon


async def find_title_guess(
    query: str,
    content_format: str,
    content_type: str,
) -> TmdbTitle:
    return (await find_title_candidates(query, content_format, content_type, limit=1))[
        0
    ]


async def find_title_candidates(
    query: str,
    content_format: str,
    content_type: str,
    *,
    limit: int = 5,
) -> list[TmdbTitle]:
    original_query = query.strip()
    if not original_query:
        raise ValueError("empty query")
    if limit <= 0:
        raise ValueError("invalid candidate limit")
    limit = min(limit, MAX_TITLE_CANDIDATES)

    if not TMDB_API:
        raise TmdbNotConfiguredError

    media_path = "tv" if content_format == "series" else "movie"
    search_url = f"{TMDB_URL.rstrip('/')}/search/{media_path}"
    queries = _make_queries(original_query)
    logger.info("Поиск '%s', варианты: %s", original_query, queries)

    session = await get_http_session()
    for query_variant in queries:
        data = await _fetch_json(
            session,
            search_url,
            {
                "query": query_variant,
                "language": TMDB_LANG,
                "include_adult": "false",
                "page": "1",
            },
        )
        results = _filter_by_content_type(
            _extract_results(data),
            content_type,
        )

        ranked = sorted(
            ((_relevance_score(result, original_query), result) for result in results),
            key=lambda item: item[0],
            reverse=True,
        )
        relevant = [result for score, result in ranked if score >= MIN_RELEVANCE]
        if relevant:
            candidates: list[TmdbTitle] = []
            seen_ids: set[int] = set()
            for result in relevant:
                candidate = _parse_title(result, original_query)
                if candidate.tmdb_id in seen_ids:
                    continue
                seen_ids.add(candidate.tmdb_id)
                candidates.append(candidate)
                if len(candidates) == limit:
                    break
            logger.info(
                "query='%s': найдено вариантов=%d, results=%d",
                query_variant,
                len(candidates),
                len(results),
            )
            return candidates

    raise TmdbNotFoundError(original_query)


async def fetch_tv_details(
    tv_id: int,
    *,
    include_episode_availability: bool = False,
) -> TmdbTvDetails:
    """Fetch regular season and episode counts for a TV series.

    TMDB stores specials and bonus material in season 0, but excludes them from
    ``number_of_seasons`` and ``number_of_episodes``.  Progress therefore uses
    only regular seasons (1 and above) so that all totals share one meaning.
    """
    if not TMDB_API:
        raise TmdbNotConfiguredError

    url = f"{TMDB_URL.rstrip('/')}/tv/{tv_id}"
    session = await get_http_session()
    data = await _fetch_json(session, url, {"language": TMDB_LANG})

    if not data:
        raise TmdbError("Не удалось получить информацию о сериале")

    raw_regular_seasons = []
    for raw_season in data.get("seasons") or []:
        season_number = raw_season.get("season_number", 0)
        if season_number <= 0:
            continue
        raw_regular_seasons.append(raw_season)

    next_episode = _parse_episode_air_info(data.get("next_episode_to_air"))
    last_episode = _parse_episode_air_info(data.get("last_episode_to_air"))

    raw_status = data.get("status")
    raw_in_production = data.get("in_production")
    status = raw_status if isinstance(raw_status, str) and raw_status else None
    in_production = raw_in_production if type(raw_in_production) is bool else None
    active = bool(in_production) or status in {
        "Returning Series",
        "Planned",
        "In Production",
    }
    seasons = [
        TmdbSeasonInfo(
            season_number=raw_season["season_number"],
            name=raw_season.get(
                "name",
                default_season_name(raw_season["season_number"]),
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


def _parse_episode_air_info(value: object) -> TmdbEpisodeAirInfo | None:
    if not isinstance(value, dict):
        return None
    season_number = value.get("season_number")
    episode_number = value.get("episode_number")
    if (
        type(season_number) is not int
        or season_number <= 0
        or type(episode_number) is not int
        or episode_number <= 0
    ):
        return None
    air_date = value.get("air_date")
    return TmdbEpisodeAirInfo(
        season_number=season_number,
        episode_number=episode_number,
        air_date=air_date if isinstance(air_date, str) and air_date else None,
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
            season_data = await _fetch_json(
                session,
                f"{series_url}/season/{season.season_number}",
                {"language": TMDB_LANG},
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


async def fetch_title_details(tmdb_id: int, content_format: str) -> TmdbTitle:
    """Fetch current title metadata for repairing catalogue entries."""
    if not TMDB_API:
        raise TmdbNotConfiguredError
    if tmdb_id <= 0 or content_format not in {"full_length", "series"}:
        raise ValueError("invalid title details request")

    media_path = "tv" if content_format == "series" else "movie"
    url = f"{TMDB_URL.rstrip('/')}/{media_path}/{tmdb_id}"
    session = await get_http_session()
    data = await _fetch_json(session, url, {"language": TMDB_LANG})
    if not data:
        raise TmdbError("Не удалось получить информацию о тайтле")
    return _parse_title(data)


async def _fetch_json(
    session: aiohttp.ClientSession,
    url: str,
    params: dict[str, str],
) -> dict:
    """Compatibility wrapper using the currently configured facade token."""
    return await _client_fetch_json(session, url, params, TMDB_API)


def _extract_results(data: dict) -> list[dict]:
    results = data.get("results")
    return results if isinstance(results, list) else []


def _parse_title(result: dict, original_query: str = "") -> TmdbTitle:
    title = (
        result.get("name")
        or result.get("title")
        or result.get("original_name")
        or result.get("original_title")
    )
    if not title:
        raise TmdbNotFoundError()
    poster_path = result.get("poster_path")
    poster_url = f"{TMDB_IMAGE_URL}{poster_path}" if poster_path else None
    return TmdbTitle(
        title=title,
        overview=result.get("overview"),
        poster_url=poster_url,
        original_query=original_query,
        normalized_query=original_query,
        tmdb_id=result.get("id", 0),
        poster_path=poster_path,
        rating=_parse_rating(result.get("vote_average")),
        original_title=result.get("original_name") or result.get("original_title"),
        release_date=result.get("first_air_date") or result.get("release_date"),
    )


def _parse_rating(value: object) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    rating = float(value)
    return rating if 0 <= rating <= 10 else None


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
    "fetch_tv_details",
    "fetch_title_details",
    "find_title_candidates",
    "find_title_guess",
    "title_relevance_score",
)
