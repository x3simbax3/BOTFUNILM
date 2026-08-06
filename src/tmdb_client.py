"""Low-level HTTP transport for the TMDB API."""

import asyncio
import json
import logging
from urllib.parse import urlsplit

import aiohttp

from config.config import (
    TMDB_ALLOWED_HOSTS,
    TMDB_MAX_RESPONSE_BYTES,
    TMDB_RATE_LIMIT_COOLDOWN_SECONDS,
    validate_tmdb_url,
)
from src.observability import record_api_error
from src.tmdb_limiter import get_tmdb_request_limiter
from src.tmdb_models import (
    TmdbAuthenticationError,
    TmdbError,
    TmdbNotFoundError,
    TmdbRateLimitError,
    TmdbUnavailableError,
)

logger = logging.getLogger(__name__)
DEFAULT_RATE_LIMIT_COOLDOWN = TMDB_RATE_LIMIT_COOLDOWN_SECONDS
MAX_RATE_LIMIT_RETRIES = 1
RESPONSE_READ_CHUNK_BYTES = 64 * 1024
_request_count = 0


async def fetch_json(
    session: aiohttp.ClientSession,
    url: str,
    params: dict[str, str],
    api_token: str,
) -> dict:
    """Fetch one JSON document and translate HTTP failures to domain errors."""
    validate_tmdb_url(url, TMDB_ALLOWED_HOSTS)
    headers = {"Authorization": f"Bearer {api_token}"}
    try:
        limiter = get_tmdb_request_limiter()
        for attempt in range(MAX_RATE_LIMIT_RETRIES + 1):
            async with limiter.request():
                _increment_request_count()
                async with session.get(
                    url,
                    params=params,
                    headers=headers,
                    timeout=aiohttp.ClientTimeout(total=15),
                    allow_redirects=False,
                ) as response:
                    if response.status in (401, 403):
                        raise TmdbAuthenticationError
                    if response.status == 429:
                        retry_after = _retry_after_seconds(response)
                        await limiter.penalize(retry_after)
                        if attempt < MAX_RATE_LIMIT_RETRIES:
                            continue
                        raise TmdbRateLimitError
                    if response.status >= 500:
                        raise TmdbUnavailableError
                    if response.status == 404:
                        raise TmdbNotFoundError
                    if response.status != 200:
                        raise TmdbError(f"TMDB вернул HTTP {response.status}")

                    try:
                        return await _read_json_response(response)
                    except (UnicodeDecodeError, ValueError) as exc:
                        raise TmdbError("TMDB вернул некорректный ответ") from exc
        raise TmdbRateLimitError
    except TmdbError as exc:
        record_api_error("tmdb", exc)
        logger.warning(
            "TMDB request failed host=%s error=%s",
            _request_host(url),
            type(exc).__name__,
        )
        raise
    except asyncio.TimeoutError:
        record_api_error("tmdb", TmdbUnavailableError())
        logger.warning("TMDB request timed out host=%s", _request_host(url))
        raise TmdbUnavailableError from None
    except aiohttp.ClientError as exc:
        record_api_error("tmdb", exc)
        logger.warning(
            "TMDB network failure host=%s error=%s",
            _request_host(url),
            type(exc).__name__,
        )
        raise TmdbUnavailableError from exc


def _retry_after_seconds(response: aiohttp.ClientResponse) -> float:
    headers = getattr(response, "headers", {})
    value = headers.get("Retry-After") if headers is not None else None
    try:
        delay = float(value)
    except (TypeError, ValueError):
        return DEFAULT_RATE_LIMIT_COOLDOWN
    return max(0.0, delay)


async def _read_json_response(response: aiohttp.ClientResponse) -> dict:
    if TMDB_MAX_RESPONSE_BYTES <= 0:
        raise ValueError("TMDB_MAX_RESPONSE_BYTES must be positive")
    if (
        response.content_length is not None
        and response.content_length > TMDB_MAX_RESPONSE_BYTES
    ):
        raise TmdbError("TMDB response body is too large")

    body = bytearray()
    while len(body) <= TMDB_MAX_RESPONSE_BYTES:
        chunk = await response.content.read(
            min(
                RESPONSE_READ_CHUNK_BYTES,
                TMDB_MAX_RESPONSE_BYTES + 1 - len(body),
            )
        )
        if not chunk:
            break
        body.extend(chunk)
    if len(body) > TMDB_MAX_RESPONSE_BYTES:
        raise TmdbError("TMDB response body is too large")

    data = json.loads(body)
    if not isinstance(data, dict):
        raise ValueError("TMDB response must be a JSON object")
    return data


def _request_host(url: str) -> str:
    return urlsplit(url).hostname or "unknown"


def _increment_request_count() -> None:
    global _request_count
    _request_count += 1


def reset_tmdb_request_count() -> None:
    global _request_count
    _request_count = 0


def get_tmdb_request_count() -> int:
    return _request_count


__all__ = ("fetch_json", "get_tmdb_request_count", "reset_tmdb_request_count")
