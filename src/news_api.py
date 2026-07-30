"""Small asynchronous client for TheNewsAPI."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from urllib.parse import unquote, urlsplit

import aiohttp

from config.config import THENEWSAPI_KEY
from src.http_client import get_http_session

NEWS_API_URL = "https://api.thenewsapi.com/v1/news/all"
MAX_RESPONSE_BYTES = 1024 * 1024


class NewsApiError(RuntimeError):
    pass


class NewsApiAuthenticationError(NewsApiError):
    pass


class NewsApiRateLimitError(NewsApiError):
    pass


class NewsApiUnavailableError(NewsApiError):
    pass


@dataclass(frozen=True)
class NewsArticle:
    uuid: str
    title: str
    description: str
    url: str
    image_url: str | None
    source: str
    published_at: str


async def fetch_news(
    search: str,
    *,
    published_after: datetime,
) -> list[NewsArticle]:
    if not THENEWSAPI_KEY:
        raise NewsApiAuthenticationError("THENEWSAPI_KEY is not configured")

    session = await get_http_session()
    params = {
        "api_token": THENEWSAPI_KEY,
        "search": search,
        "search_fields": "title,description",
        "categories": "entertainment",
        "language": "ru",
        "published_after": published_after.strftime("%Y-%m-%dT%H:%M:%S"),
        "sort": "published_at",
        "limit": "3",
    }
    try:
        async with session.get(
            NEWS_API_URL,
            params=params,
            timeout=aiohttp.ClientTimeout(total=20),
        ) as response:
            status = response.status
            payload = await _read_response(response)
    except TimeoutError as exc:
        raise NewsApiUnavailableError("TheNewsAPI request timed out") from exc
    except aiohttp.ClientError as exc:
        raise NewsApiUnavailableError("TheNewsAPI request failed") from exc

    if status in {401, 403}:
        raise NewsApiAuthenticationError(_error_message(payload))
    if status == 429:
        raise NewsApiRateLimitError(_error_message(payload))
    if status >= 500:
        raise NewsApiUnavailableError(_error_message(payload))
    if status >= 400:
        raise NewsApiError(_error_message(payload))

    data = payload.get("data")
    if not isinstance(data, list):
        raise NewsApiError("TheNewsAPI response has no data list")
    return [article for item in data if (article := _parse_article(item))]


async def _read_response(response: aiohttp.ClientResponse) -> dict:
    if response.content_length and response.content_length > MAX_RESPONSE_BYTES:
        raise NewsApiError("TheNewsAPI response is too large")
    body = bytearray()
    async for chunk in response.content.iter_chunked(64 * 1024):
        body.extend(chunk)
        if len(body) > MAX_RESPONSE_BYTES:
            raise NewsApiError("TheNewsAPI response is too large")
    try:
        payload = json.loads(body)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise NewsApiError("TheNewsAPI returned invalid JSON") from exc
    if not isinstance(payload, dict):
        raise NewsApiError("TheNewsAPI returned an invalid response object")
    return payload


def _parse_article(value: object) -> NewsArticle | None:
    if not isinstance(value, dict):
        return None
    uuid = _text(value.get("uuid"))
    title = _text(value.get("title"))
    url = _safe_http_url(value.get("url"))
    if not uuid or not title or not url:
        return None
    return NewsArticle(
        uuid=uuid,
        title=title,
        description=_text(value.get("description")) or _text(value.get("snippet")),
        url=url,
        image_url=_safe_http_url(value.get("image_url")),
        source=unquote(_text(value.get("source"))).strip(),
        published_at=_text(value.get("published_at")),
    )


def _safe_http_url(value: object) -> str | None:
    url = _text(value)
    if not url:
        return None
    try:
        parsed = urlsplit(url)
        _ = parsed.port
    except ValueError:
        return None
    if parsed.scheme.lower() not in {"http", "https"} or not parsed.hostname:
        return None
    if parsed.username is not None or parsed.password is not None:
        return None
    return url


def _text(value: object) -> str:
    return value.strip() if isinstance(value, str) else ""


def _error_message(payload: dict) -> str:
    error = payload.get("error")
    if isinstance(error, dict) and isinstance(error.get("message"), str):
        return error["message"]
    return "TheNewsAPI request failed"


__all__ = (
    "NewsApiAuthenticationError",
    "NewsApiError",
    "NewsApiRateLimitError",
    "NewsApiUnavailableError",
    "NewsArticle",
    "fetch_news",
)
