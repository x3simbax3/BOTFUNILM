"""Low-level HTTP transport for the TMDB API."""

import asyncio
import logging

import aiohttp

from src.tmdb_models import (
    TmdbAuthenticationError,
    TmdbError,
    TmdbRateLimitError,
    TmdbUnavailableError,
)


logger = logging.getLogger(__name__)


async def fetch_json(
    session: aiohttp.ClientSession,
    url: str,
    params: dict[str, str],
    api_token: str,
) -> dict:
    """Fetch one JSON document and translate HTTP failures to domain errors."""
    headers = {"Authorization": f"Bearer {api_token}"}
    try:
        async with session.get(
            url,
            params=params,
            headers=headers,
            timeout=aiohttp.ClientTimeout(total=15),
        ) as response:
            if response.status in (401, 403):
                raise TmdbAuthenticationError
            if response.status == 429:
                raise TmdbRateLimitError
            if response.status >= 500:
                raise TmdbUnavailableError
            if response.status != 200:
                raise TmdbError(f"TMDB вернул HTTP {response.status}")

            try:
                return await response.json(content_type=None)
            except (aiohttp.ContentTypeError, ValueError) as exc:
                raise TmdbError("TMDB вернул некорректный ответ") from exc
    except TmdbError as exc:
        logger.warning("TMDB %s вернул ошибку: %s", url, type(exc).__name__)
        raise
    except asyncio.TimeoutError:
        logger.warning("TMDB %s: таймаут", url)
        raise TmdbUnavailableError from None
    except aiohttp.ClientError as exc:
        logger.warning("TMDB %s: сетевая ошибка: %s", url, exc)
        raise TmdbUnavailableError from exc


__all__ = ("fetch_json",)
