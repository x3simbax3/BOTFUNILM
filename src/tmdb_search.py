"""TMDB title search and title-detail use cases."""

import logging
from dataclasses import replace

from config.config import TMDB_API, TMDB_LANG, TMDB_REGION, TMDB_URL
from src.http_client import get_http_session
from src.tmdb_client import fetch_json
from src.tmdb_matching import (
    MIN_RELEVANCE,
    filter_by_content_type,
    make_queries,
    title_relevance_score,
)
from src.tmdb_models import (
    TmdbError,
    TmdbNotConfiguredError,
    TmdbNotFoundError,
    TmdbTitle,
)
from src.tmdb_parsing import (
    _extract_results,
    _parse_title,
    regional_movie_release_date,
)

logger = logging.getLogger(__name__)
MAX_TITLE_CANDIDATES = 5


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
    queries = make_queries(original_query)
    logger.info(
        "TMDB search started format=%s type=%s variants=%d",
        content_format,
        content_type,
        len(queries),
    )

    session = await get_http_session()
    for attempt, query_variant in enumerate(queries, start=1):
        parameters = {
            "query": query_variant,
            "language": TMDB_LANG,
            "include_adult": "false",
            "page": "1",
        }
        if media_path == "movie":
            parameters["region"] = TMDB_REGION
        data = await fetch_json(
            session,
            search_url,
            parameters,
            TMDB_API,
        )
        results = filter_by_content_type(_extract_results(data), content_type)
        ranked = sorted(
            (
                (title_relevance_score(result, original_query), result)
                for result in results
            ),
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
                "TMDB search matched format=%s type=%s attempt=%d "
                "candidates=%d results=%d",
                content_format,
                content_type,
                attempt,
                len(candidates),
                len(results),
            )
            return candidates

    logger.info(
        "TMDB search completed without match format=%s type=%s attempts=%d",
        content_format,
        content_type,
        len(queries),
    )
    raise TmdbNotFoundError(original_query)


async def fetch_title_details(tmdb_id: int, content_format: str) -> TmdbTitle:
    """Fetch current title metadata for repairing catalogue entries."""
    if not TMDB_API:
        raise TmdbNotConfiguredError
    if tmdb_id <= 0 or content_format not in {"full_length", "series"}:
        raise ValueError("invalid title details request")

    media_path = "tv" if content_format == "series" else "movie"
    url = f"{TMDB_URL.rstrip('/')}/{media_path}/{tmdb_id}"
    session = await get_http_session()
    parameters = {"language": TMDB_LANG}
    if media_path == "movie":
        parameters["append_to_response"] = "release_dates"
    data = await fetch_json(session, url, parameters, TMDB_API)
    if not data:
        raise TmdbError("Не удалось получить информацию о тайтле")
    title = _parse_title(data)
    regional_date = regional_movie_release_date(data, TMDB_REGION)
    if media_path != "movie" or regional_date is None:
        return title
    return replace(title, release_date=regional_date)


__all__ = (
    "MAX_TITLE_CANDIDATES",
    "fetch_title_details",
    "find_title_candidates",
    "find_title_guess",
)
