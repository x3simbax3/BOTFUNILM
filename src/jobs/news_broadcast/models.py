"""Shared models and limits for cinema news broadcasts."""

from __future__ import annotations

from dataclasses import dataclass


USER_BATCH_SIZE = 100
SEND_INTERVAL_SECONDS = 0.06
TELEGRAM_CAPTION_LIMIT = 1024


@dataclass(frozen=True)
class NewsFilter:
    name: str
    label: str
    search: str


@dataclass
class NewsBroadcastStats:
    selected: int = 0
    sent: int = 0
    failed: int = 0
    deactivated: int = 0
    article_uuid: str | None = None


NEWS_FILTERS = (
    NewsFilter(
        "trusted-cinema",
        "Проверенные новости кино",
        "единый запрос TheNewsAPI",
    ),
)


__all__ = (
    "NEWS_FILTERS",
    "SEND_INTERVAL_SECONDS",
    "TELEGRAM_CAPTION_LIMIT",
    "USER_BATCH_SIZE",
    "NewsBroadcastStats",
    "NewsFilter",
)
