"""Strict parsing for callback data received from Telegram clients."""

import re
from dataclasses import dataclass

Action = str
ContentFormat = str
ContentType = str

VALID_ACTIONS = frozenset({"add"})
VALID_CONTENT_FORMATS = frozenset({"full_length", "series"})
VALID_CONTENT_TYPES = frozenset({"movie", "anime", "cartoon"})
VALID_LIBRARY_FILTERS = frozenset(
    {
        "all",
        "series",
        "full_length",
        "anime",
        "movie",
        "cartoon",
        "completed",
        "planned",
        "unfinished",
        "ongoing",
        "rated",
        "unrated",
        "format_all",
        "category_all",
        "status_all",
        "rating_all",
    }
)
VALID_LIBRARY_SORTS = frozenset({"recent", "rating", "tmdb_rating", "title"})
VALID_LIBRARY_FILTER_GROUPS = frozenset(
    {"format", "category", "status", "rating", "sort", "back"}
)

MAX_LIBRARY_PAGE = 100_000
MAX_SEASON_NUMBER = 10_000
MAX_EPISODE_COUNT = 100_000

_FORMAT_RE = re.compile(r"format:([^:]+):([^:]+)\Z", re.ASCII)
_TYPE_RE = re.compile(r"type:([^:]+):([^:]+):([^:]+)\Z", re.ASCII)
_BACK_RE = re.compile(r"back:([^:]+)(?::([^:]+))?(?::([^:]+))?\Z", re.ASCII)
_LIBRARY_FILTER_RE = re.compile(r"library:filter:([^:]+)\Z", re.ASCII)
_LIBRARY_FILTER_GROUP_RE = re.compile(r"library:filters:([^:]+)\Z", re.ASCII)
_LIBRARY_SORT_RE = re.compile(
    r"library:sort:(recent|rating|tmdb_rating|title)\Z", re.ASCII
)
_LIBRARY_PAGE_RE = re.compile(r"library:page:(0|[1-9][0-9]{0,5})\Z", re.ASCII)
_RATING_RE = re.compile(r"rate:(10|[1-9])\Z", re.ASCII)
_SEASON_RE = re.compile(r"season:(done|all|[1-9][0-9]{0,4})\Z", re.ASCII)
_EPISODE_RE = re.compile(
    r"ep:(?:done|back|noop|([1-9][0-9]{0,4}):([1-9][0-9]{0,5}))\Z",
    re.ASCII,
)
_EPISODE_PAGE_RE = re.compile(r"ep:page:(0|[1-9][0-9]{0,3})\Z", re.ASCII)


@dataclass(frozen=True)
class FormatCallback:
    action: Action
    content_format: ContentFormat


@dataclass(frozen=True)
class TypeCallback:
    action: Action
    content_format: ContentFormat
    content_type: ContentType


@dataclass(frozen=True)
class BackCallback:
    target_step: str
    params: tuple[str, ...]


@dataclass(frozen=True)
class EpisodeCallback:
    season_number: int
    episodes_watched: int


@dataclass(frozen=True)
class EpisodePageCallback:
    page: int


def parse_format_callback(data: str) -> FormatCallback | None:
    match = _FORMAT_RE.fullmatch(data)
    if not match:
        return None
    action, content_format = match.groups()
    if action not in VALID_ACTIONS or content_format not in VALID_CONTENT_FORMATS:
        return None
    return FormatCallback(action, content_format)


def parse_type_callback(data: str) -> TypeCallback | None:
    match = _TYPE_RE.fullmatch(data)
    if not match:
        return None
    action, content_format, content_type = match.groups()
    if (
        action not in VALID_ACTIONS
        or content_format not in VALID_CONTENT_FORMATS
        or content_type not in VALID_CONTENT_TYPES
    ):
        return None
    return TypeCallback(action, content_format, content_type)


def parse_back_callback(data: str) -> BackCallback | None:
    match = _BACK_RE.fullmatch(data)
    if not match:
        return None
    target_step, first, second = match.groups()
    params = tuple(value for value in (first, second) if value is not None)
    valid_params = {
        "main": {()},
        "format": {(action,) for action in VALID_ACTIONS},
        "content_type": {()}
        | {
            (action, content_format)
            for action in VALID_ACTIONS
            for content_format in VALID_CONTENT_FORMATS
        },
    }
    if params not in valid_params.get(target_step, set()):
        return None
    return BackCallback(target_step, params)


def parse_library_filter_callback(data: str) -> str | None:
    match = _LIBRARY_FILTER_RE.fullmatch(data)
    if not match or match.group(1) not in VALID_LIBRARY_FILTERS:
        return None
    return match.group(1)


def parse_library_sort_callback(data: str) -> str | None:
    match = _LIBRARY_SORT_RE.fullmatch(data)
    if not match or match.group(1) not in VALID_LIBRARY_SORTS:
        return None
    return match.group(1)


def parse_library_filter_group_callback(data: str) -> str | None:
    match = _LIBRARY_FILTER_GROUP_RE.fullmatch(data)
    if not match or match.group(1) not in VALID_LIBRARY_FILTER_GROUPS:
        return None
    return match.group(1)


def parse_library_page_callback(data: str) -> int | None:
    match = _LIBRARY_PAGE_RE.fullmatch(data)
    if not match:
        return None
    page = int(match.group(1))
    return page if page <= MAX_LIBRARY_PAGE else None


def parse_rating_callback(data: str) -> int | None:
    match = _RATING_RE.fullmatch(data)
    return int(match.group(1)) if match else None


def parse_season_callback(data: str) -> int | str | None:
    match = _SEASON_RE.fullmatch(data)
    if not match:
        return None
    value = match.group(1)
    if value in {"done", "all"}:
        return value
    season_number = int(value)
    return season_number if season_number <= MAX_SEASON_NUMBER else None


def parse_episode_callback(
    data: str,
) -> EpisodeCallback | EpisodePageCallback | str | None:
    page_match = _EPISODE_PAGE_RE.fullmatch(data)
    if page_match:
        return EpisodePageCallback(int(page_match.group(1)))
    match = _EPISODE_RE.fullmatch(data)
    if not match:
        return None
    if data in {"ep:done", "ep:back", "ep:noop"}:
        return data.removeprefix("ep:")
    season_number, episodes_watched = (int(value) for value in match.groups())
    if season_number > MAX_SEASON_NUMBER or episodes_watched > MAX_EPISODE_COUNT:
        return None
    return EpisodeCallback(season_number, episodes_watched)
