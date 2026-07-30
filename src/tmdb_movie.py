"""TMDB movie details used by scheduled release tracking."""

from config.config import TMDB_API, TMDB_LANG, TMDB_URL
from src.http_client import get_http_session
from src.tmdb_client import fetch_json
from src.tmdb_models import TmdbError, TmdbMovieDetails, TmdbNotConfiguredError
from src.tmdb_parsing import _parse_rating


async def fetch_movie_details(movie_id: int) -> TmdbMovieDetails:
    if not TMDB_API:
        raise TmdbNotConfiguredError
    if movie_id <= 0:
        raise ValueError("invalid movie id")

    session = await get_http_session()
    data = await fetch_json(
        session,
        f"{TMDB_URL.rstrip('/')}/movie/{movie_id}",
        {"language": TMDB_LANG},
        TMDB_API,
    )
    title = _optional_text(data.get("title"))
    if not title:
        raise TmdbError("Не удалось получить информацию о фильме")
    return TmdbMovieDetails(
        title=title,
        original_title=_optional_text(data.get("original_title")),
        description=_optional_text(data.get("overview")),
        poster_path=_optional_text(data.get("poster_path")),
        rating=_parse_rating(data.get("vote_average")),
        release_date=_optional_text(data.get("release_date")),
        status=_optional_text(data.get("status")),
    )


def _optional_text(value: object) -> str | None:
    return value if isinstance(value, str) and value else None


__all__ = ("fetch_movie_details",)
