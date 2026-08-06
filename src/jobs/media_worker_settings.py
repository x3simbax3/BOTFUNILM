"""Shared media worker settings helpers."""

from __future__ import annotations

from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from config.config import (
    BOT_TOKEN,
    MEDIA_REFRESH_BATCH_SIZE,
    MEDIA_REFRESH_CONCURRENCY,
    MEDIA_REFRESH_LOCK_TTL_SECONDS,
    MEDIA_REFRESH_RETRIES,
    MEDIA_WORKER_TIMEZONE,
    REDIS_URL,
)


def validate_settings() -> None:
    values = {
        "MEDIA_REFRESH_BATCH_SIZE": MEDIA_REFRESH_BATCH_SIZE,
        "MEDIA_REFRESH_CONCURRENCY": MEDIA_REFRESH_CONCURRENCY,
        "MEDIA_REFRESH_LOCK_TTL_SECONDS": MEDIA_REFRESH_LOCK_TTL_SECONDS,
        "MEDIA_REFRESH_RETRIES": MEDIA_REFRESH_RETRIES,
    }
    for name, value in values.items():
        if value <= 0:
            raise ValueError(f"{name} must be positive")
    if not REDIS_URL:
        raise RuntimeError("REDIS_URL is required for media refresh jobs")
    if not BOT_TOKEN:
        raise RuntimeError("BOT_TOKEN is required for series notifications")


def worker_timezone() -> ZoneInfo:
    try:
        return ZoneInfo(MEDIA_WORKER_TIMEZONE)
    except ZoneInfoNotFoundError as exc:
        raise ValueError(
            f"Unknown media worker timezone: {MEDIA_WORKER_TIMEZONE}"
        ) from exc
