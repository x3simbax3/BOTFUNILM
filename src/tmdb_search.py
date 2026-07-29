"""TMDB title search and title-detail use cases."""

import logging

from config.config import TMDB_API, TMDB_LANG, TMDB_URL
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
from src.tmdb_parsing import _extract_results, _parse_title

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
    logger.info("Поиск '%s', варианты: %s", original_query, queries)

    session = await get_http_session()
    for query_variant in queries:
        data = await fetch_json(
            session,
            search_url,
            {
                "query": query_variant,
                "language": TMDB_LANG,
                "include_adult": "false",
                "page": "1",
            },
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
                "query='%s': найдено вариантов=%d, results=%d",
                query_variant,
                len(candidates),
                len(results),
            )
            return candidates

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
    data = await fetch_json(session, url, {"language": TMDB_LANG}, TMDB_API)
    if not data:
        raise TmdbError("Не удалось получить информацию о тайтле")
    return _parse_title(data)


__all__ = (
    "MAX_TITLE_CANDIDATES",
    "fetch_title_details",
    "find_title_candidates",
    "find_title_guess",
)
