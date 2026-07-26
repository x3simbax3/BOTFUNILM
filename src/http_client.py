"""Shared HTTP client lifecycle for outbound application requests."""

import asyncio

import aiohttp

_session: aiohttp.ClientSession | None = None
_session_lock = asyncio.Lock()


async def get_http_session() -> aiohttp.ClientSession:
    """Return the process-wide session, creating it on first use."""
    global _session

    if _session is not None and not _session.closed:
        return _session

    async with _session_lock:
        if _session is None or _session.closed:
            _session = aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=30),
            )
        return _session


async def close_http_session() -> None:
    """Close the shared session during application shutdown."""
    global _session

    if _session is not None and not _session.closed:
        await _session.close()
    _session = None


__all__ = ("close_http_session", "get_http_session")
