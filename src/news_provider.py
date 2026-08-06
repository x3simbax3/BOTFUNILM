"""Interface implemented by interchangeable cinema news providers."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from datetime import datetime
from typing import Protocol

from src.news_models import NewsFetchResult, NewsImage

BeforeNewsRequest = Callable[[], Awaitable[None]]


class NewsProvider(Protocol):
    async def fetch_news(
        self,
        *,
        published_after: datetime,
        page: int = 1,
        before_request: BeforeNewsRequest | None = None,
    ) -> NewsFetchResult: ...

    async def fetch_image(self, url: str) -> NewsImage | None: ...

    async def fetch_description(self, url: str) -> str | None: ...


__all__ = ("BeforeNewsRequest", "NewsProvider")
