import asyncio
import json
from dataclasses import dataclass
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from config.config import TMDB_API, TMDB_LANG, TMDB_URL


TMDB_IMAGE_URL = "https://image.tmdb.org/t/p/w500"
TITLE_QUOTES = "\"'`«»„“”"
MAX_QUERY_CANDIDATES = 16


@dataclass(frozen=True)
class TmdbTitle:
    title: str
    overview: str | None
    poster_url: str | None


class TmdbError(Exception):
    pass


class TmdbNotConfiguredError(TmdbError):
    pass


class TmdbNotFoundError(TmdbError):
    pass


async def find_title_guess(query: str, content_format: str) -> TmdbTitle:
    return await asyncio.to_thread(_find_title_guess, query, content_format)


def _find_title_guess(query: str, content_format: str) -> TmdbTitle:
    normalized_query = _normalize_query(query)
    media_path = "tv" if content_format == "series" else "movie"
    url = f"{TMDB_URL.rstrip('/')}/search/{media_path}"

    for query_candidate in _query_candidates(normalized_query):
        data = _request_json(url, query_candidate)
        results = data.get("results") or []
        if results:
            return _parse_title(results[0])

    raise TmdbNotFoundError


def _parse_title(result: dict) -> TmdbTitle:
    title = (
        result.get("name")
        or result.get("title")
        or result.get("original_name")
        or result.get("original_title")
    )
    if not title:
        raise TmdbNotFoundError

    poster_path = result.get("poster_path")
    poster_url = f"{TMDB_IMAGE_URL}{poster_path}" if poster_path else None

    return TmdbTitle(
        title=title,
        overview=result.get("overview"),
        poster_url=poster_url,
    )


def _normalize_query(query: str) -> str:
    normalized = " ".join(query.strip().strip(TITLE_QUOTES).split())
    if not normalized:
        raise ValueError("empty query")
    return normalized


def _query_candidates(query: str) -> list[str]:
    candidates = [query]
    if "е" not in query and "Е" not in query:
        return candidates

    positions = [
        index for index, char in enumerate(query)
        if char in {"е", "Е"}
    ]

    for mask in range(1, 2 ** len(positions)):
        chars = list(query)
        for bit_index, char_index in enumerate(positions):
            if not mask & (1 << bit_index):
                continue

            chars[char_index] = "Ё" if chars[char_index] == "Е" else "ё"

        candidate = "".join(chars)
        if candidate not in candidates:
            candidates.append(candidate)

        if len(candidates) >= MAX_QUERY_CANDIDATES:
            break

    return candidates


def _request_json(url: str, query: str) -> dict:
    if not TMDB_API:
        raise TmdbNotConfiguredError

    params = {
        "query": query,
        "language": TMDB_LANG,
        "include_adult": "false",
        "page": "1",
    }

    headers = {}
    if _is_bearer_token(TMDB_API):
        headers["Authorization"] = f"Bearer {TMDB_API}"
    else:
        params["api_key"] = TMDB_API

    request = Request(f"{url}?{urlencode(params)}", headers=headers)

    try:
        with urlopen(request, timeout=10) as response:
            return json.loads(response.read().decode("utf-8"))
    except (HTTPError, URLError, TimeoutError, json.JSONDecodeError) as error:
        raise TmdbError from error


def _is_bearer_token(api_key: str) -> bool:
    return "." in api_key or api_key.startswith("eyJ")


__all__ = (
    "TmdbError",
    "TmdbNotConfiguredError",
    "TmdbNotFoundError",
    "TmdbTitle",
    "find_title_guess",
)
