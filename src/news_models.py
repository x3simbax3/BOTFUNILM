"""Provider-neutral models used by the cinema news pipeline."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class NewsArticle:
    uuid: str
    title: str
    description: str
    url: str
    image_url: str | None
    source: str
    published_at: str


@dataclass(frozen=True)
class NewsFetchResult:
    articles: tuple[NewsArticle, ...]
    api_limit: int | None
    api_remaining: int | None


@dataclass(frozen=True)
class NewsImage:
    data: bytes
    filename: str


__all__ = ("NewsArticle", "NewsFetchResult", "NewsImage")
