"""Telegram message rendering for cinema news."""

from __future__ import annotations

import html
from urllib.parse import urlsplit

from aiogram.types import Message

from src.jobs.news_broadcast.models import TELEGRAM_CAPTION_LIMIT
from src.news_models import NewsArticle


def _article_text(article: NewsArticle) -> str:
    source_text = urlsplit(article.url).hostname or article.source or "Источник"
    source_text = _truncate_caption_part(source_text, TELEGRAM_CAPTION_LIMIT - 4)
    title_limit = TELEGRAM_CAPTION_LIMIT - len(source_text) - 4
    title_text = _truncate_caption_part(article.title, title_limit)
    description_limit = TELEGRAM_CAPTION_LIMIT - len(title_text) - len(source_text) - 4
    description_text = _truncate_caption_part(
        article.description,
        description_limit,
    )
    title = html.escape(title_text)
    description = html.escape(description_text)
    source = html.escape(source_text)
    return "\n\n".join((f"<b>{title}</b>", description, source))


def _truncate_caption_part(value: str, limit: int) -> str:
    if len(value) <= limit:
        return value
    if limit <= 0:
        return ""
    if limit == 1:
        return "…"
    return f"{value[: limit - 1].rstrip()}…"


def _telegram_photo_id(message: Message) -> str | None:
    if not message.photo:
        return None
    return message.photo[-1].file_id


__all__ = ("_article_text", "_telegram_photo_id")
