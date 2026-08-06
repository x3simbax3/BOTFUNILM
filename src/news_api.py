"""Asynchronous client for fresh, trusted TheNewsAPI articles."""

from __future__ import annotations

import asyncio
import ipaddress
import json
import socket
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import datetime
from html.parser import HTMLParser
from urllib.parse import unquote, urljoin, urlsplit

import aiohttp

from config.config import NEWS_ALLOWED_DOMAINS, NEWS_API_RETRIES, THENEWSAPI_KEY
from src.http_client import get_http_session
from src.news_models import NewsArticle, NewsFetchResult, NewsImage
from src.observability import record_api_error
from src.news_provider import BeforeNewsRequest

NEWS_API_URL = "https://api.thenewsapi.com/v1/news/all"
MAX_RESPONSE_BYTES = 1024 * 1024
MAX_ARTICLE_METADATA_BYTES = 512 * 1024
MAX_IMAGE_RESPONSE_BYTES = 8 * 1024 * 1024
NEWS_SEARCH = (
    "(фильм* | кино | сериал* | сезон* | мультфильм* | мультсериал* | "
    "аниме | трейлер* | экранизац* | кинопреми*)"
)


class NewsApiError(RuntimeError):
    pass


class NewsApiAuthenticationError(NewsApiError):
    pass


class NewsApiRateLimitError(NewsApiError):
    def __init__(self, message: str, *, retry_after: float | None = None) -> None:
        super().__init__(message)
        self.retry_after = retry_after


class NewsApiUnavailableError(NewsApiError):
    pass


async def fetch_news(
    *,
    published_after: datetime,
    before_request: BeforeNewsRequest | None = None,
) -> NewsFetchResult:
    if not THENEWSAPI_KEY:
        raise NewsApiAuthenticationError("THENEWSAPI_KEY is not configured")

    session = await get_http_session()
    params = {
        "api_token": THENEWSAPI_KEY,
        "search": NEWS_SEARCH,
        "search_fields": "title",
        "categories": "entertainment",
        "domains": ",".join(sorted(NEWS_ALLOWED_DOMAINS)),
        "language": "ru",
        "published_after": published_after.strftime("%Y-%m-%dT%H:%M:%S"),
        "sort": "published_at",
        "limit": "3",
    }
    for attempt in range(NEWS_API_RETRIES):
        if before_request is not None:
            await before_request()
        try:
            async with session.get(
                NEWS_API_URL,
                params=params,
                timeout=aiohttp.ClientTimeout(total=20),
            ) as response:
                return await _parse_news_response(response)
        except NewsApiRateLimitError as exc:
            record_api_error("thenewsapi", exc)
            if exc.retry_after is None or attempt + 1 == NEWS_API_RETRIES:
                raise
            await asyncio.sleep(min(exc.retry_after, 30))
        except NewsApiUnavailableError as exc:
            record_api_error("thenewsapi", exc)
            if attempt + 1 == NEWS_API_RETRIES:
                raise
            await asyncio.sleep(2**attempt)
        except (asyncio.TimeoutError, TimeoutError, aiohttp.ClientError) as exc:
            if attempt + 1 == NEWS_API_RETRIES:
                error = NewsApiUnavailableError("TheNewsAPI request failed")
                record_api_error("thenewsapi", error)
                raise error from exc
            await asyncio.sleep(2**attempt)
    raise AssertionError("unreachable")


async def _parse_news_response(response: aiohttp.ClientResponse) -> NewsFetchResult:
    status = response.status
    headers = getattr(response, "headers", {})
    api_limit = _header_int(headers, "X-UsageLimit-Limit", "X-Usage-Limit")
    api_remaining = _header_int(
        headers,
        "X-UsageLimit-Remaining",
        "X-Usage-Remaining",
    )
    if status >= 400:
        payload = await _read_error_response(response)
    else:
        payload = await _read_response(response)
    if status in {401, 403}:
        raise NewsApiAuthenticationError(_error_message(payload))
    if status == 402:
        raise NewsApiRateLimitError(_error_message(payload))
    if status == 429:
        raise NewsApiRateLimitError(
            _error_message(payload),
            retry_after=_retry_after_seconds(headers) or 1.0,
        )
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


class TheNewsApiProvider:
    """NewsProvider adapter for TheNewsAPI and source-hosted media."""

    async def fetch_news(
        self,
        *,
        published_after: datetime,
        before_request: BeforeNewsRequest | None = None,
    ) -> NewsFetchResult:
        return await fetch_news(
            published_after=published_after,
            before_request=before_request,
        )

    async def fetch_image(self, url: str) -> NewsImage | None:
        return await fetch_news_image(url)

    async def fetch_description(self, url: str) -> str | None:
        return await fetch_article_description(url)


async def fetch_news_image(url: str) -> NewsImage | None:
    """Download and validate an article image before broadcasting it."""
    current_url = url
    async with _public_http_session() as session:
        for _ in range(3):
            try:
                _validate_public_url(current_url)
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
                    return await _read_image_response(response)
            except (asyncio.TimeoutError, TimeoutError, aiohttp.ClientError, ValueError):
                return None
    return None


async def fetch_article_description(url: str) -> str | None:
    """Read a source page's complete meta description without scraping its body."""
    current_url = url
    async with _public_http_session() as session:
        for _ in range(3):
            try:
                _validate_public_url(current_url)
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
                    content_type = response.headers.get("Content-Type", "").lower()
                    if "text/html" not in content_type:
                        return None
                    return await _read_meta_description(response)
            except (asyncio.TimeoutError, TimeoutError, aiohttp.ClientError, ValueError):
                return None
    return None


def _validate_public_url(url: str) -> None:
    """Validate URL syntax; destination addresses are checked by _PublicResolver."""
    parsed = urlsplit(url)
    if (
        parsed.scheme.lower() not in {"http", "https"}
        or not parsed.hostname
        or parsed.username is not None
        or parsed.password is not None
    ):
        raise ValueError("invalid article URL")
    _ = parsed.port


class _PublicResolver(aiohttp.abc.AbstractResolver):
    """Resolve article hosts once and allow only globally routable addresses."""

    async def resolve(
        self,
        host: str,
        port: int = 0,
        family: socket.AddressFamily = socket.AF_UNSPEC,
    ) -> list[aiohttp.abc.ResolveResult]:
        addresses = await asyncio.get_running_loop().getaddrinfo(
            host,
            port,
            family=family,
            type=socket.SOCK_STREAM,
        )
        if not addresses or any(
            not ipaddress.ip_address(address[4][0]).is_global for address in addresses
        ):
            raise ValueError("article URL resolves to a non-public address")
        return [
            {
                "hostname": host,
                "host": address[4][0],
                "port": port,
                "family": address[0],
                "proto": address[2],
                "flags": address[3],
            }
            for address in addresses
        ]

    async def close(self) -> None:
        pass


@asynccontextmanager
async def _public_http_session() -> AsyncIterator[aiohttp.ClientSession]:
    connector = aiohttp.TCPConnector(
        resolver=_PublicResolver(),
        use_dns_cache=False,
    )
    async with aiohttp.ClientSession(connector=connector) as session:
        yield session


async def _read_image_response(response: aiohttp.ClientResponse) -> NewsImage | None:
    content_type = response.headers.get("Content-Type", "").split(";", 1)[0].lower()
    extensions = {
        "image/jpeg": "jpg",
        "image/png": "png",
        "image/webp": "webp",
    }
    extension = extensions.get(content_type)
    if extension is None:
        return None
    if response.content_length and response.content_length > MAX_IMAGE_RESPONSE_BYTES:
        return None
    body = bytearray()
    async for chunk in response.content.iter_chunked(64 * 1024):
        body.extend(chunk)
        if len(body) > MAX_IMAGE_RESPONSE_BYTES:
            return None
    data = bytes(body)
    if not _matches_image_signature(data, extension):
        return None
    return NewsImage(data=data, filename=f"news.{extension}")


async def _read_meta_description(response: aiohttp.ClientResponse) -> str | None:
    body = bytearray()
    async for chunk in response.content.iter_chunked(32 * 1024):
        body.extend(chunk)
        if len(body) > MAX_ARTICLE_METADATA_BYTES:
            return None
        if b"</head" in body.lower():
            break
    parser = _MetaDescriptionParser()
    parser.feed(body.decode(response.charset or "utf-8", errors="ignore"))
    return _text(parser.description) or None


class _MetaDescriptionParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.description = ""

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.lower() != "meta":
            return
        attributes = {key.lower(): value or "" for key, value in attrs}
        kind = (attributes.get("property") or attributes.get("name", "")).lower()
        if kind in {"og:description", "description", "twitter:description"}:
            content = attributes.get("content", "").strip()
            if content and (kind == "og:description" or not self.description):
                self.description = content


def _matches_image_signature(data: bytes, extension: str) -> bool:
    if extension == "jpg":
        return data.startswith(b"\xff\xd8\xff")
    if extension == "png":
        return data.startswith(b"\x89PNG\r\n\x1a\n")
    return len(data) >= 12 and data.startswith(b"RIFF") and data[8:12] == b"WEBP"


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


async def _read_error_response(response: aiohttp.ClientResponse) -> dict:
    try:
        return await _read_response(response)
    except NewsApiError:
        return {}


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
        description=_text(value.get("description")),
        url=url,
        image_url=_safe_http_url(value.get("image_url")),
        source=unquote(_text(value.get("source"))).strip().lower().rstrip("."),
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
    return " ".join(value.split()) if isinstance(value, str) else ""


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


def _retry_after_seconds(headers) -> float | None:
    value = headers.get("Retry-After")
    if value is None:
        return None
    try:
        seconds = float(value)
    except ValueError:
        return None
    return max(0.0, seconds)


__all__ = (
    "NewsApiAuthenticationError",
    "NewsApiError",
    "NewsApiRateLimitError",
    "NewsApiUnavailableError",
    "NewsArticle",
    "NewsFetchResult",
    "NewsImage",
    "TheNewsApiProvider",
    "fetch_article_description",
    "fetch_news",
    "fetch_news_image",
)
