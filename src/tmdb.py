import asyncio
import logging
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlencode

import aiohttp
from config.config import TMDB_API, TMDB_LANG, TMDB_URL


logger = logging.getLogger(__name__)

TMDB_IMAGE_URL = "https://image.tmdb.org/t/p/w500"

ANIMATION_GENRE_ID = 16

STOP_WORDS = {
    "в", "во", "и", "а", "о", "об", "от", "до", "на", "не", "ни", "но", "ну", "по", "со", "то", "у", "же", "бы", "ли", "за", "из",
    "the", "a", "an", "of", "to", "in", "on", "at", "and", "or", "is", "are", "was", "were", "be", "been", "being",
    "have", "has", "had", "do", "does", "did", "will", "would", "could", "should", "may", "might", "must", "can",
}

MIN_RELEVANCE = 150


@dataclass(frozen=True)
class TmdbTitle:
    title: str
    overview: str | None
    poster_url: str | None
    original_query: str
    normalized_query: str


class TmdbError(Exception):
    pass


class TmdbNotConfiguredError(TmdbError):
    pass


class TmdbNotFoundError(TmdbError):
    def __init__(self, query: str = "") -> None:
        super().__init__()
        self.query = query


def _normalize_text(text: str) -> str:
    return text.lower().replace("ё", "е")


def _make_queries(original: str) -> list[str]:
    """Генерирует варианты запроса для лучшего fuzzy matching."""
    queries: list[str] = []
    words = original.split()
    meaningful = [w for w in words if w not in STOP_WORDS]

    # 1. Оригинал
    queries.append(original)

    # 2. Без стоп-слов
    if meaningful and meaningful != words:
        queries.append(" ".join(meaningful))

    # 3. Только слова длиннее 3 символов
    long_words = [w for w in meaningful if len(w) > 3]
    if long_words and long_words != meaningful:
        queries.append(" ".join(long_words))

    # 4. Без последнего слова (часто там опечатка)
    if len(meaningful) > 1:
        queries.append(" ".join(meaningful[:-1]))

    # 5. Без первого слова
    if len(meaningful) > 1:
        queries.append(" ".join(meaningful[1:]))

    # 6. Только 2 самых длинных слова
    if len(meaningful) > 2:
        top2 = sorted(meaningful, key=len, reverse=True)[:2]
        queries.append(" ".join(top2))

    # Дедупликация
    seen: set[str] = set()
    unique: list[str] = []
    for q in queries:
        key = _normalize_text(q)
        if key not in seen:
            seen.add(key)
            unique.append(q)
    return unique


async def find_title_guess(query: str, content_format: str, content_type: str) -> TmdbTitle:
    original_query = query.strip()
    if not original_query:
        raise ValueError("empty query")

    if not TMDB_API:
        raise TmdbNotConfiguredError

    media_path = "tv" if content_format == "series" else "movie"
    search_url = f"{TMDB_URL.rstrip('/')}/search"
    multi_url = f"{search_url}/multi"
    specific_url = f"{search_url}/{media_path}"

    queries = _make_queries(original_query)
    logger.info("Поиск '%s', варианты: %s", original_query, queries)

    async with aiohttp.ClientSession() as session:
        for q in queries:
            multi_task = _fetch_json(
                session, multi_url,
                {"query": q, "language": TMDB_LANG, "include_adult": "false", "page": "1"},
            )
            specific_task = _fetch_json(
                session, specific_url,
                {"query": q, "language": TMDB_LANG, "include_adult": "false", "page": "1"},
            )

            multi_data, specific_data = await asyncio.gather(
                multi_task, specific_task, return_exceptions=True
            )

            results = _merge_search_results(multi_data, specific_data, media_path)
            results = _filter_by_content_type(results, content_type)

            if results:
                best = _pick_best(results, original_query)
                best_score = _relevance_score(
                    {"title": best.title, "original_title": best.title}, original_query
                )
                logger.info(
                    "query='%s': лучший='%s', score=%.0f, results=%d",
                    q, best.title, best_score, len(results),
                )
                if best_score >= MIN_RELEVANCE:
                    return best

        raise TmdbNotFoundError(original_query)


def _merge_search_results(
    multi_data: Any,
    specific_data: Any,
    media_path: str,
) -> list[dict]:
    seen_ids: set[int] = set()
    merged: list[dict] = []

    for data in (specific_data, multi_data):
        if isinstance(data, BaseException):
            continue
        for item in _extract_results(data):
            item_id = item.get("id")
            if item_id in seen_ids:
                continue
            media_type = item.get("media_type", media_path)
            if media_path == "movie" and media_type not in ("movie",):
                continue
            if media_path == "tv" and media_type not in ("tv",):
                continue
            seen_ids.add(item_id)
            merged.append(item)

    return merged


def _extract_results(data: Any) -> list[dict]:
    if isinstance(data, BaseException):
        return []
    if isinstance(data, dict):
        return data.get("results") or []
    return []


def _relevance_score(result: dict, query: str) -> float:
    query_normalized = _normalize_text(query)
    titles = [
        result.get("title") or "",
        result.get("name") or "",
        result.get("original_title") or "",
        result.get("original_name") or "",
    ]
    titles = [_normalize_text(t) for t in titles if t]

    if not titles:
        return 0.0

    best_title_score = 0.0
    for title in titles:
        if title == query_normalized:
            best_title_score = max(best_title_score, 1000)
        elif title.startswith(query_normalized):
            best_title_score = max(best_title_score, 800)
        elif query_normalized in title:
            best_title_score = max(best_title_score, 600)
        elif title in query_normalized:
            best_title_score = max(best_title_score, 700)
        else:
            query_words = set(query_normalized.split()) - STOP_WORDS
            title_words = set(title.split()) - STOP_WORDS
            overlap = len(query_words & title_words)
            if overlap > 0:
                best_title_score = max(best_title_score, 200 + overlap * 100)

    popularity = result.get("popularity") or 0
    return best_title_score + min(popularity / 10, 100)


def _pick_best(results: list[dict], original_query: str) -> TmdbTitle:
    results.sort(key=lambda r: _relevance_score(r, original_query), reverse=True)
    return _parse_title(results[0], original_query)


def _discover_genre_filter(content_type: str) -> dict[str, str]:
    if content_type == "anime":
        return {"with_genres": str(ANIMATION_GENRE_ID), "with_original_language": "ja"}
    if content_type == "cartoon":
        return {"with_genres": str(ANIMATION_GENRE_ID), "with_original_language.not": "ja"}
    return {"without_genres": str(ANIMATION_GENRE_ID)}


async def _fetch_json(
    session: aiohttp.ClientSession,
    url: str,
    params: dict[str, str],
) -> dict:
    headers = {"Authorization": f"Bearer {TMDB_API}"}
    try:
        async with session.get(
            f"{url}?{urlencode(params)}", headers=headers,
            timeout=aiohttp.ClientTimeout(total=15),
        ) as resp:
            if resp.status != 200:
                logger.warning("TMDB %s вернул %d", url.split("?")[0], resp.status)
                return {}
            return await resp.json(content_type=None)
    except asyncio.TimeoutError:
        logger.warning("TMDB %s таймаут", url.split("?")[0])
        return {}
    except Exception as exc:
        logger.warning("TMDB %s ошибка: %s", url.split("?")[0], exc)
        return {}


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
    )


def _filter_by_content_type(results: list[dict], content_type: str) -> list[dict]:
    if content_type == "anime":
        return [r for r in results if _is_anime(r)]
    elif content_type == "cartoon":
        return [r for r in results if _is_cartoon(r)]
    elif content_type == "movie":
        return [r for r in results if not _is_animation(r)]
    return results


def _is_animation(result: dict) -> bool:
    genre_ids = result.get("genre_ids") or []
    return ANIMATION_GENRE_ID in genre_ids


def _is_anime(result: dict) -> bool:
    genre_ids = result.get("genre_ids") or []
    if not genre_ids:
        return result.get("original_language") == "ja"
    return ANIMATION_GENRE_ID in genre_ids and result.get("original_language") == "ja"


def _is_cartoon(result: dict) -> bool:
    genre_ids = result.get("genre_ids") or []
    if not genre_ids:
        return False
    return ANIMATION_GENRE_ID in genre_ids and result.get("original_language") != "ja"


__all__ = (
    "TmdbError",
    "TmdbNotConfiguredError",
    "TmdbNotFoundError",
    "TmdbTitle",
    "find_title_guess",
)
