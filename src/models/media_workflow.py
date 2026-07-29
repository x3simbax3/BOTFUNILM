"""Typed data passed between media handlers through FSM storage."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import asdict, dataclass
from typing import Any


@dataclass(frozen=True)
class MediaWorkflowData:
    media_id: int | None
    tmdb_id: int | None
    tmdb_title: str
    tmdb_description: str | None
    tmdb_poster_path: str | None
    tmdb_original_title: str | None
    tmdb_release_date: str | None
    tmdb_rating: float | None
    content_format: str
    content_type: str
    telegram_poster_file_id: str | None = None

    @classmethod
    def from_tmdb_candidate(
        cls,
        candidate: Mapping[str, Any],
        *,
        content_format: str | None = None,
        content_type: str | None = None,
    ) -> MediaWorkflowData:
        """Build workflow data from the serializable TMDB candidate payload."""
        tmdb_id = _get(candidate, "tmdb_id")
        return cls(
            media_id=current_media_id(candidate),
            tmdb_id=int(tmdb_id) if tmdb_id is not None else None,
            tmdb_title=str(_get(candidate, "title") or ""),
            tmdb_description=_get(candidate, "overview"),
            tmdb_poster_path=_get(candidate, "poster_path"),
            tmdb_original_title=_get(candidate, "original_title"),
            tmdb_release_date=_get(candidate, "release_date"),
            tmdb_rating=_get(candidate, "rating"),
            content_format=content_format
            or str(_get(candidate, "content_format") or ""),
            content_type=content_type
            or str(_get(candidate, "content_type") or "movie"),
            telegram_poster_file_id=_get(candidate, "telegram_poster_file_id"),
        )

    @classmethod
    def from_library_item(cls, item: Mapping[str, Any]) -> MediaWorkflowData:
        """Build workflow data from a library query row or plain mapping."""
        tmdb_id = _get(item, "tmdb_id")
        return cls(
            media_id=int(item["id"]),
            tmdb_id=int(tmdb_id) if tmdb_id is not None else None,
            tmdb_title=str(item["title"]),
            tmdb_description=_get(item, "description"),
            tmdb_poster_path=_get(item, "poster_path"),
            tmdb_original_title=_get(item, "original_title"),
            tmdb_release_date=_get(item, "release_date")
            or _get(item, "first_air_date"),
            tmdb_rating=_get(item, "rating"),
            content_format=str(item["content_format"]),
            content_type=str(item["content_type"]),
            telegram_poster_file_id=_get(item, "telegram_poster_file_id"),
        )

    @classmethod
    def from_fsm(cls, data: Mapping[str, Any]) -> MediaWorkflowData:
        """Restore workflow data from FSM storage."""
        tmdb_id = data.get("tmdb_id")
        return cls(
            media_id=current_media_id(data),
            tmdb_id=int(tmdb_id) if tmdb_id is not None else None,
            tmdb_title=str(data.get("tmdb_title") or ""),
            tmdb_description=data.get("tmdb_description"),
            tmdb_poster_path=data.get("tmdb_poster_path"),
            tmdb_original_title=data.get("tmdb_original_title"),
            tmdb_release_date=data.get("tmdb_release_date"),
            tmdb_rating=data.get("tmdb_rating"),
            content_format=str(data.get("content_format") or ""),
            content_type=str(data.get("content_type") or "movie"),
            telegram_poster_file_id=data.get("telegram_poster_file_id"),
        )

    def to_fsm_dict(self) -> dict[str, Any]:
        """Return a JSON-serializable mapping for ``FSMContext.update_data``."""
        return asdict(self)


def current_media_id(data: Mapping[str, Any]) -> int | None:
    """Return one validated media id from FSM-compatible data."""
    value = data.get("media_id")
    if type(value) is int:
        return value if value > 0 else None
    if isinstance(value, str) and value.isascii() and value.isdigit():
        parsed = int(value)
        return parsed if parsed > 0 and str(parsed) == value else None
    return None


def _get(source: Mapping[str, Any], key: str, default: Any = None) -> Any:
    """Read dicts and sqlite-style rows through the same interface."""
    try:
        return source[key]
    except (IndexError, KeyError):
        return default
