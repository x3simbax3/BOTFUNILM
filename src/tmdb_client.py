"""Low-level HTTP transport for the TMDB API."""

import asyncio
import logging

import aiohttp

from config.config import TMDB_RATE_LIMIT_COOLDOWN_SECONDS
from src.tmdb_limiter import get_tmdb_request_limiter
from src.tmdb_models import (
    TmdbAuthenticationError,
    TmdbError,
    TmdbRateLimitError,
    TmdbUnavailableError,
)

logger = logging.getLogger(__name__)
DEFAULT_RATE_LIMIT_COOLDOWN = TMDB_RATE_LIMIT_COOLDOWN_SECONDS
MAX_RATE_LIMIT_RETRIES = 1


async def fetch_json(
    session: aiohttp.ClientSession,
    url: str,
    params: dict[str, str],
    api_token: str,
) -> dict:
    """Fetch one JSON document and translate HTTP failures to domain errors."""
    headers = {"Authorization": f"Bearer {api_token}"}
    try:
        limiter = get_tmdb_request_limiter()
        for attempt in range(MAX_RATE_LIMIT_RETRIES + 1):
            async with limiter.request():
                async with session.get(
                    url,
                    params=params,
                    headers=headers,
                    timeout=aiohttp.ClientTimeout(total=15),
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
                    if response.status != 200:
                        raise TmdbError(f"TMDB вернул HTTP {response.status}")

                    try:
                        return await response.json(content_type=None)
                    except (aiohttp.ContentTypeError, ValueError) as exc:
                        raise TmdbError("TMDB вернул некорректный ответ") from exc
        raise TmdbRateLimitError
    except TmdbError as exc:
        logger.warning("TMDB %s вернул ошибку: %s", url, type(exc).__name__)
        raise
    except asyncio.TimeoutError:
        logger.warning("TMDB %s: таймаут", url)
        raise TmdbUnavailableError from None
    except aiohttp.ClientError as exc:
        logger.warning("TMDB %s: сетевая ошибка: %s", url, exc)
        raise TmdbUnavailableError from exc


def _retry_after_seconds(response: aiohttp.ClientResponse) -> float:
    headers = getattr(response, "headers", {})
    value = headers.get("Retry-After") if headers is not None else None
    try:
        delay = float(value)
    except (TypeError, ValueError):
        return DEFAULT_RATE_LIMIT_COOLDOWN
    return max(0.0, delay)


__all__ = ("fetch_json",)
