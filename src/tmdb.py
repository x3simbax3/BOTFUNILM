import asyncio
import logging
import re
import unicodedata
from dataclasses import dataclass
from difflib import SequenceMatcher

import aiohttp
from config.config import TMDB_API, TMDB_LANG, TMDB_URL


logger = logging.getLogger(__name__)

TMDB_IMAGE_URL = "https://image.tmdb.org/t/p/original"

ANIMATION_GENRE_ID = 16

STOP_WORDS = {
    "в", "во", "и", "а", "о", "об", "от", "до", "на", "не", "ни", "но", "ну", "по", "со", "то", "у", "же", "бы", "ли", "за", "из",
    "the", "a", "an", "of", "to", "in", "on", "at", "and", "or", "is", "are", "was", "were", "be", "been", "being",
    "have", "has", "had", "do", "does", "did", "will", "would", "could", "should", "may", "might", "must", "can",
}

MIN_RELEVANCE = 300


@dataclass(frozen=True)
class TmdbTitle:
    title: str
    overview: str | None
    poster_url: str | None
    original_query: str
    normalized_query: str
    tmdb_id: int = 0
    poster_path: str | None = None


@dataclass(frozen=True)
class TmdbSeasonInfo:
    season_number: int
    name: str
    episode_count: int


@dataclass(frozen=True)
class TmdbTvDetails:
    number_of_seasons: int
    number_of_episodes: int
    seasons: list[TmdbSeasonInfo]


class TmdbError(Exception):
    pass


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


def _normalize_text(text: str) -> str:
    normalized = unicodedata.normalize("NFKC", text).casefold().replace("ё", "е")
    return re.sub(r"[_\W]+", " ", normalized).strip()


def _make_queries(original: str) -> list[str]:
    """Генерирует варианты запроса для лучшего fuzzy matching."""
    queries: list[str] = []
    words = original.split()
    meaningful = [w for w in words if _normalize_text(w) not in STOP_WORDS]

    queries.append(original)

    if meaningful and meaningful != words:
        queries.append(" ".join(meaningful))

    long_words = [w for w in meaningful if len(w) > 3]
    if long_words and long_words != meaningful:
        queries.append(" ".join(long_words))

    if len(meaningful) > 1:
        queries.append(" ".join(meaningful[:-1]))

    if len(meaningful) > 1:
        queries.append(" ".join(meaningful[1:]))

    if len(meaningful) > 2:
        top2 = sorted(meaningful, key=len, reverse=True)[:2]
        queries.append(" ".join(top2))

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
    search_url = f"{TMDB_URL.rstrip('/')}/search/{media_path}"

    queries = _make_queries(original_query)
    logger.info("Поиск '%s', варианты: %s", original_query, queries)

    async with aiohttp.ClientSession() as session:
        for q in queries:
            data = await _fetch_json(
                session,
                search_url,
                {
                    "query": q,
                    "language": TMDB_LANG,
                    "include_adult": "false",
                    "page": "1",
                },
            )
            results = _extract_results(data)
            results = _filter_by_content_type(results, content_type)

            if results:
                best_result = max(
                    results,
                    key=lambda result: _relevance_score(result, original_query),
                )
                best_score = _relevance_score(best_result, original_query)
                best = _parse_title(best_result, original_query)
                logger.info(
                    "query='%s': лучший='%s', score=%.0f, results=%d",
                    q, best.title, best_score, len(results),
                )
                if best_score >= MIN_RELEVANCE:
                    return best

        raise TmdbNotFoundError(original_query)


async def fetch_tv_details(tv_id: int) -> TmdbTvDetails:
    """Получает информацию о сезонах и сериях сериала из TMDB."""
    if not TMDB_API:
        raise TmdbNotConfiguredError

    url = f"{TMDB_URL.rstrip('/')}/tv/{tv_id}"
    params = {"language": TMDB_LANG}

    async with aiohttp.ClientSession() as session:
        data = await _fetch_json(session, url, params)

    if not data:
        raise TmdbError("Не удалось получить информацию о сериале")

    raw_seasons = data.get("seasons") or []
    seasons = []
    for s in raw_seasons:
        season_num = s.get("season_number", 0)
        if season_num < 0:
            continue
        seasons.append(TmdbSeasonInfo(
            season_number=season_num,
            name=s.get("name", f"Сезон {season_num}"),
            episode_count=s.get("episode_count", 0),
        ))

    return TmdbTvDetails(
        number_of_seasons=data.get("number_of_seasons", len(seasons)),
        number_of_episodes=data.get("number_of_episodes", 0),
        seasons=seasons,
    )


def _extract_results(data: dict) -> list[dict]:
    results = data.get("results")
    return results if isinstance(results, list) else []


def title_relevance_score(result: dict, query: str) -> float:
    query_normalized = _normalize_text(query)
    if not query_normalized:
        return 0.0
    query_words = [w for w in query_normalized.split() if w and w not in STOP_WORDS]
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
        title_words = [w for w in title.split() if w and w not in STOP_WORDS]
        word_count_diff = abs(len(query_words) - len(title_words))
        if title == query_normalized:
            bonus = 1200 if title == _normalize_text(result.get("original_title") or result.get("original_name") or "") else 1000
            best_title_score = max(best_title_score, bonus)
        elif title.startswith(query_normalized):
            best_title_score = max(best_title_score, 800)
        elif query_normalized in title:
            best_title_score = max(best_title_score, 600 - word_count_diff * 80)
        elif title in query_normalized:
            score = 700 - max(0, len(query_words) - len(title_words)) * 180
            best_title_score = max(best_title_score, score)
        else:
            query_word_set = set(query_words)
            title_word_set = set(title_words)
            overlap = len(query_word_set & title_word_set)
            if overlap > 0:
                query_coverage = overlap / max(len(query_word_set), 1)
                title_coverage = overlap / max(len(title_word_set), 1)
                overlap_score = (
                    overlap * 120
                    + query_coverage * 180
                    + title_coverage * 80
                    - word_count_diff * 30
                )
                best_title_score = max(best_title_score, overlap_score)

            similarity = SequenceMatcher(None, query_normalized, title).ratio()
            if similarity >= 0.6:
                best_title_score = max(best_title_score, similarity * 500)

    popularity = result.get("popularity") or 0
    return best_title_score + min(popularity / 20, 30)


# Оставлено для совместимости с существующими тестами и внутренними вызовами.
_relevance_score = title_relevance_score


async def _fetch_json(
    session: aiohttp.ClientSession,
    url: str,
    params: dict[str, str],
) -> dict:
    headers = {"Authorization": f"Bearer {TMDB_API}"}
    try:
        async with session.get(
            url,
            params=params,
            headers=headers,
            timeout=aiohttp.ClientTimeout(total=15),
        ) as resp:
            if resp.status in (401, 403):
                raise TmdbAuthenticationError
            if resp.status == 429:
                raise TmdbRateLimitError
            if resp.status >= 500:
                raise TmdbUnavailableError
            if resp.status != 200:
                raise TmdbError(f"TMDB вернул HTTP {resp.status}")

            try:
                return await resp.json(content_type=None)
            except (aiohttp.ContentTypeError, ValueError) as exc:
                raise TmdbError("TMDB вернул некорректный ответ") from exc
    except TmdbError as exc:
        logger.warning("TMDB %s вернул ошибку: %s", url, type(exc).__name__)
        raise
    except asyncio.TimeoutError:
        logger.warning("TMDB %s: таймаут", url)
        raise TmdbUnavailableError from None
    except aiohttp.ClientError as exc:
        logger.warning("TMDB %s: сетевая ошибка: %s", url, exc)
        raise TmdbUnavailableError from exc


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
    tmdb_id = result.get("id", 0)
    return TmdbTitle(
        title=title,
        overview=result.get("overview"),
        poster_url=poster_url,
        original_query=original_query,
        normalized_query=original_query,
        tmdb_id=tmdb_id,
        poster_path=poster_path,
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
    "TmdbAuthenticationError",
    "TmdbNotConfiguredError",
    "TmdbNotFoundError",
    "TmdbRateLimitError",
    "TmdbUnavailableError",
    "TmdbTitle",
    "TmdbSeasonInfo",
    "TmdbTvDetails",
    "fetch_tv_details",
    "find_title_guess",
    "title_relevance_score",
)
