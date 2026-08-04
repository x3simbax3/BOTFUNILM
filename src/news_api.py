"""Small asynchronous client for TheNewsAPI."""

from __future__ import annotations

import asyncio
import codecs
import ipaddress
import json
import socket
from dataclasses import dataclass
from datetime import datetime
from html.parser import HTMLParser
from urllib.parse import unquote, urljoin, urlsplit

import aiohttp

from config.config import THENEWSAPI_KEY
from src.http_client import get_http_session

NEWS_API_URL = "https://api.thenewsapi.com/v1/news/top"
MAX_RESPONSE_BYTES = 1024 * 1024
MAX_ARTICLE_RESPONSE_BYTES = 2 * 1024 * 1024
ARTICLE_TEXT_TARGET = 1400


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


@dataclass(frozen=True)
class NewsFetchResult:
    articles: tuple[NewsArticle, ...]
    api_limit: int | None
    api_remaining: int | None


async def fetch_news(
    search: str,
    *,
    published_after: datetime,
) -> NewsFetchResult:
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
        "limit": "3",
    }
    try:
        async with session.get(
            NEWS_API_URL,
            params=params,
            timeout=aiohttp.ClientTimeout(total=20),
        ) as response:
            status = response.status
            headers = getattr(response, "headers", {})
            api_limit = _header_int(
                headers,
                "X-UsageLimit-Limit",
                "X-Usage-Limit",
            )
            api_remaining = _header_int(
                headers,
                "X-UsageLimit-Remaining",
                "X-Usage-Remaining",
            )
            payload = await _read_response(response)
    except TimeoutError as exc:
        raise NewsApiUnavailableError("TheNewsAPI request timed out") from exc
    except aiohttp.ClientError as exc:
        raise NewsApiUnavailableError("TheNewsAPI request failed") from exc

    if status in {401, 403}:
        raise NewsApiAuthenticationError(_error_message(payload))
    if status in {402, 429}:
        raise NewsApiRateLimitError(_error_message(payload))
    if status >= 500:
        raise NewsApiUnavailableError(_error_message(payload))
    if status >= 400:
        raise NewsApiError(_error_message(payload))

    data = payload.get("data")
    if not isinstance(data, list):
        raise NewsApiError("TheNewsAPI response has no data list")
    return NewsFetchResult(
        articles=tuple(article for item in data if (article := _parse_article(item))),
        api_limit=api_limit,
        api_remaining=api_remaining,
    )


async def fetch_article_text(url: str) -> str | None:
    """Extract article body from a public source page when the API truncates it."""
    session = await get_http_session()
    current_url = url
    for _ in range(3):
        await _validate_public_url(current_url)
        try:
            async with session.get(
                current_url,
                timeout=aiohttp.ClientTimeout(total=15),
                allow_redirects=False,
                headers={"User-Agent": "BotFunilm/1.0"},
            ) as response:
                if response.status in {301, 302, 303, 307, 308}:
                    location = response.headers.get("Location")
                    if not location:
                        return None
                    current_url = urljoin(current_url, location)
                    continue
                if response.status != 200:
                    return None
                content_type = response.headers.get("Content-Type", "")
                if "text/html" not in content_type.lower():
                    return None
                return await _extract_article_body(response)
        except (TimeoutError, aiohttp.ClientError, ValueError):
            return None
    return None


async def _validate_public_url(url: str) -> None:
    parsed = urlsplit(url)
    if (
        parsed.scheme.lower() not in {"http", "https"}
        or not parsed.hostname
        or parsed.username is not None
        or parsed.password is not None
    ):
        raise ValueError("invalid article URL")
    port = parsed.port or (443 if parsed.scheme.lower() == "https" else 80)
    addresses = await asyncio.get_running_loop().getaddrinfo(
        parsed.hostname,
        port,
        type=socket.SOCK_STREAM,
    )
    if not addresses or any(
        not ipaddress.ip_address(address[4][0]).is_global for address in addresses
    ):
        raise ValueError("article URL resolves to a non-public address")


async def _extract_article_body(response: aiohttp.ClientResponse) -> str | None:
    parser = _ArticleBodyParser()
    decoder = codecs.getincrementaldecoder(response.charset or "utf-8")(errors="ignore")
    size = 0
    async for chunk in response.content.iter_chunked(64 * 1024):
        size += len(chunk)
        if size > MAX_ARTICLE_RESPONSE_BYTES:
            return None
        parser.feed(decoder.decode(chunk))
        if parser.text_length >= ARTICLE_TEXT_TARGET:
            break
    parser.feed(decoder.decode(b"", final=True))
    text = parser.text
    return text or None


class _ArticleBodyParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self._body_depth = 0
        self._ignored_depth = 0
        self._parts: list[str] = []

    @property
    def text(self) -> str:
        return " ".join("".join(self._parts).split())

    @property
    def text_length(self) -> int:
        return sum(len(part) for part in self._parts)

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attributes = dict(attrs)
        if self._body_depth:
            self._body_depth += 1
        elif (attributes.get("itemprop") or "").lower() == "articlebody":
            self._body_depth = 1
        if self._body_depth and tag in {"script", "style", "noscript"}:
            self._ignored_depth += 1
        if self._body_depth and not self._ignored_depth and tag == "br":
            self._parts.append("\n")

    def handle_endtag(self, tag: str) -> None:
        if not self._body_depth:
            return
        if self._ignored_depth and tag in {"script", "style", "noscript"}:
            self._ignored_depth -= 1
        if not self._ignored_depth and tag in {"p", "li"}:
            self._parts.append("\n")
        self._body_depth -= 1

    def handle_data(self, data: str) -> None:
        if self._body_depth and not self._ignored_depth:
            self._parts.append(data)


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


def _header_int(headers, *names: str) -> int | None:
    for name in names:
        value = headers.get(name)
        if value is not None and value.isascii() and value.isdigit():
            return int(value)
    return None


__all__ = (
    "NewsApiAuthenticationError",
    "NewsApiError",
    "NewsApiRateLimitError",
    "NewsApiUnavailableError",
    "NewsArticle",
    "NewsFetchResult",
    "fetch_article_text",
    "fetch_news",
)
