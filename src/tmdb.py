import asyncio
from difflib import SequenceMatcher
import json
from dataclasses import dataclass
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from config.config import TMDB_API, TMDB_LANG, TMDB_URL


TMDB_IMAGE_URL = "https://image.tmdb.org/t/p/w500"
TITLE_QUOTES = "\"'`«»„“”"


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

    data = _request_json(url, normalized_query)
    results = data.get("results") or []
    if results:
        return _parse_title(_select_best_result(results, normalized_query))

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


def _select_best_result(results: list[dict], query: str) -> dict:
    normalized_query = _normalize_for_match(query)
    return max(
        results,
        key=lambda result: _result_score(result, normalized_query),
    )


def _result_score(result: dict, normalized_query: str) -> float:
    names = [
        result.get("name"),
        result.get("title"),
        result.get("original_name"),
        result.get("original_title"),
    ]

    scores = [
        _match_score(normalized_query, name)
        for name in names
        if isinstance(name, str) and name.strip()
    ]
    return max(scores, default=0.0)


def _match_score(normalized_query: str, title: str) -> float:
    normalized_title = _normalize_for_match(title)
    if normalized_title == normalized_query:
        return 2.0

    return SequenceMatcher(None, normalized_query, normalized_title).ratio()


def _normalize_for_match(value: str) -> str:
    return _normalize_query(value).casefold().replace("ё", "е")


def _request_json(url: str, query: str) -> dict:
    if not TMDB_API:
        raise TmdbNotConfiguredError

    params = {
        "query": query,
        "language": TMDB_LANG,
        "include_adult": "false",
        "page": "1",
    }

    headers = {"Authorization": f"Bearer {TMDB_API}"}

    request = Request(f"{url}?{urlencode(params)}", headers=headers)

    try:
        with urlopen(request, timeout=10) as response:
            return json.loads(response.read().decode("utf-8"))
    except (HTTPError, URLError, TimeoutError, json.JSONDecodeError) as error:
        raise TmdbError from error


__all__ = (
    "TmdbError",
    "TmdbNotConfiguredError",
    "TmdbNotFoundError",
    "TmdbTitle",
    "find_title_guess",
)
