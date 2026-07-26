"""Public facade and use cases for the TMDB integration.

Matching, transport, and domain types live in dedicated modules. This facade keeps
the established ``src.tmdb`` API stable for handlers and other callers.
"""

import logging

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
    original_query = query.strip()
    if not original_query:
        raise ValueError("empty query")

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

        if results:
            best_result = max(
                results,
                key=lambda result: _relevance_score(result, original_query),
            )
            best_score = _relevance_score(best_result, original_query)
            best = _parse_title(best_result, original_query)
            logger.info(
                "query='%s': лучший='%s', score=%.0f, results=%d",
                query_variant,
                best.title,
                best_score,
                len(results),
            )
            if best_score >= MIN_RELEVANCE:
                return best

    raise TmdbNotFoundError(original_query)


async def fetch_tv_details(tv_id: int) -> TmdbTvDetails:
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

    seasons = []
    for raw_season in data.get("seasons") or []:
        season_number = raw_season.get("season_number", 0)
        if season_number <= 0:
            continue
        seasons.append(
            TmdbSeasonInfo(
                season_number=season_number,
                name=raw_season.get("name", default_season_name(season_number)),
                episode_count=raw_season.get("episode_count", 0),
            )
        )

    return TmdbTvDetails(
        number_of_seasons=data.get("number_of_seasons", len(seasons)),
        number_of_episodes=data.get("number_of_episodes", 0),
        seasons=seasons,
    )


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
    )


__all__ = (
    "ANIMATION_GENRE_ID",
    "MIN_RELEVANCE",
    "STOP_WORDS",
    "TMDB_IMAGE_URL",
    "TmdbAuthenticationError",
    "TmdbError",
    "TmdbNotConfiguredError",
    "TmdbNotFoundError",
    "TmdbRateLimitError",
    "TmdbSeasonInfo",
    "TmdbTitle",
    "TmdbTvDetails",
    "TmdbUnavailableError",
    "fetch_tv_details",
    "find_title_guess",
    "title_relevance_score",
)
