"""Local-first title search with typed candidate results."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import asdict, dataclass
from typing import Any

from src.database.media_search import find_media_by_title
from src.tmdb_models import TmdbTitle
from src.tmdb_search import MAX_TITLE_CANDIDATES, find_title_candidates


@dataclass(frozen=True)
class TitleSearchCandidate:
    media_id: int | None
    title: str
    overview: str | None
    poster_url: str | None
    tmdb_id: int
    poster_path: str | None
    rating: float | None
    original_title: str | None
    release_date: str | None
    telegram_poster_file_id: str | None = None

    @classmethod
    def from_tmdb(
        cls,
        title: TmdbTitle,
        *,
        media_id: int | None = None,
        telegram_poster_file_id: str | None = None,
    ) -> TitleSearchCandidate:
        return cls(
            media_id=media_id,
            title=title.title,
            overview=title.overview,
            poster_url=title.poster_url,
            tmdb_id=title.tmdb_id,
            poster_path=title.poster_path,
            rating=title.rating,
            original_title=title.original_title,
            release_date=title.release_date,
            telegram_poster_file_id=telegram_poster_file_id,
        )

    def to_fsm_dict(self) -> dict[str, Any]:
        return asdict(self)


async def search_title_candidates(
    query: str,
    content_format: str,
    content_type: str,
    *,
    remote_search_started: Callable[[], Awaitable[None]] | None = None,
) -> list[TitleSearchCandidate]:
    """Return a local candidate when possible, otherwise query TMDB."""
    local_media = await find_media_by_title(query, content_format, content_type)
    if local_media is not None:
        local_title = _title_from_local_media(
            local_media,
            query,
        )
        return [
            TitleSearchCandidate.from_tmdb(
                local_title,
                media_id=int(local_media["id"]),
                telegram_poster_file_id=dict(local_media).get(
                    "telegram_poster_file_id"
                ),
            )
        ]

    if remote_search_started is not None:
        await remote_search_started()
    titles = await find_title_candidates(
        query,
        content_format,
        content_type,
        limit=MAX_TITLE_CANDIDATES,
    )
    return [TitleSearchCandidate.from_tmdb(title) for title in titles]


def _title_from_local_media(
    local_media,
    query: str,
) -> TmdbTitle:
    poster_path = local_media["poster_path"]
    return TmdbTitle(
        title=local_media["title"],
        overview=local_media["description"],
        poster_url=None,
        original_query=query,
        normalized_query=query,
        tmdb_id=local_media["tmdb_id"] or 0,
        poster_path=poster_path,
        rating=local_media["rating"],
        original_title=local_media["original_title"],
        release_date=local_media["first_air_date"] or local_media["release_date"],
    )


__all__ = ("TitleSearchCandidate", "search_title_candidates")
