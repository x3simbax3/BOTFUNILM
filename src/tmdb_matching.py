"""Query generation, title scoring, and content classification for TMDB."""

import re
import unicodedata
from difflib import SequenceMatcher

ANIMATION_GENRE_ID = 16
MIN_RELEVANCE = 300

STOP_WORDS = {
    "в",
    "во",
    "и",
    "а",
    "о",
    "об",
    "от",
    "до",
    "на",
    "не",
    "ни",
    "но",
    "ну",
    "по",
    "со",
    "то",
    "у",
    "же",
    "бы",
    "ли",
    "за",
    "из",
    "the",
    "a",
    "an",
    "of",
    "to",
    "in",
    "on",
    "at",
    "and",
    "or",
    "is",
    "are",
    "was",
    "were",
    "be",
    "been",
    "being",
    "have",
    "has",
    "had",
    "do",
    "does",
    "did",
    "will",
    "would",
    "could",
    "should",
    "may",
    "might",
    "must",
    "can",
}


def normalize_text(text: str) -> str:
    normalized = unicodedata.normalize("NFKC", text).casefold().replace("ё", "е")
    return re.sub(r"[_\W]+", " ", normalized).strip()


def make_queries(original: str) -> list[str]:
    """Generate query variants used for fuzzy matching."""
    queries: list[str] = []
    words = original.split()
    meaningful = [word for word in words if normalize_text(word) not in STOP_WORDS]

    queries.append(original)

    if meaningful and meaningful != words:
        queries.append(" ".join(meaningful))

    long_words = [word for word in meaningful if len(word) > 3]
    if long_words and long_words != meaningful:
        queries.append(" ".join(long_words))

    if len(meaningful) > 1:
        queries.append(" ".join(meaningful[:-1]))
        queries.append(" ".join(meaningful[1:]))

    if len(meaningful) > 2:
        top_two = sorted(meaningful, key=len, reverse=True)[:2]
        queries.append(" ".join(top_two))

    seen: set[str] = set()
    unique: list[str] = []
    for query in queries:
        key = normalize_text(query)
        if key not in seen:
            seen.add(key)
            unique.append(query)
    return unique


def title_relevance_score(result: dict, query: str) -> float:
    query_normalized = normalize_text(query)
    if not query_normalized:
        return 0.0
    query_words = [
        word for word in query_normalized.split() if word and word not in STOP_WORDS
    ]
    titles = [
        result.get("title") or "",
        result.get("name") or "",
        result.get("original_title") or "",
        result.get("original_name") or "",
    ]
    titles = [normalize_text(title) for title in titles if title]

    if not titles:
        return 0.0

    best_title_score = 0.0
    for title in titles:
        title_words = [
            word for word in title.split() if word and word not in STOP_WORDS
        ]
        word_count_diff = abs(len(query_words) - len(title_words))
        original_title = (
            result.get("original_title") or result.get("original_name") or ""
        )
        if title == query_normalized:
            bonus = 1200 if title == normalize_text(original_title) else 1000
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


def filter_by_content_type(results: list[dict], content_type: str) -> list[dict]:
    if content_type == "anime":
        return [result for result in results if is_anime(result)]
    if content_type == "cartoon":
        return [result for result in results if is_cartoon(result)]
    if content_type == "movie":
        return [result for result in results if not is_animation(result)]
    return results


def is_animation(result: dict) -> bool:
    genre_ids = result.get("genre_ids") or []
    return ANIMATION_GENRE_ID in genre_ids


def is_anime(result: dict) -> bool:
    genre_ids = result.get("genre_ids") or []
    if not genre_ids:
        return result.get("original_language") == "ja"
    return ANIMATION_GENRE_ID in genre_ids and result.get("original_language") == "ja"


def is_cartoon(result: dict) -> bool:
    genre_ids = result.get("genre_ids") or []
    if not genre_ids:
        return False
    return ANIMATION_GENRE_ID in genre_ids and result.get("original_language") != "ja"


__all__ = (
    "ANIMATION_GENRE_ID",
    "MIN_RELEVANCE",
    "STOP_WORDS",
    "filter_by_content_type",
    "is_animation",
    "is_anime",
    "is_cartoon",
    "make_queries",
    "normalize_text",
    "title_relevance_score",
)
