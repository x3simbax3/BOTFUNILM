"""Pure parsing helpers for TMDB responses."""

from src.tmdb_models import TmdbEpisodeAirInfo, TmdbNotFoundError, TmdbTitle

TMDB_IMAGE_URL = "https://image.tmdb.org/t/p/original"


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


__all__ = ("TMDB_IMAGE_URL",)
