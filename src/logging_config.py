"""Application logging configuration with privacy-safe exception reporting."""

from __future__ import annotations

import logging
from types import TracebackType

LOG_FORMAT = "%(asctime)s %(levelname)s %(name)s: %(message)s"


def configure_logging(*, debug: bool) -> None:
    """Configure useful application logs without verbose dependency payloads."""
    application_level = logging.DEBUG if debug else logging.INFO
    logging.basicConfig(level=application_level, format=LOG_FORMAT)
    logging.getLogger("src").setLevel(application_level)

    # Dependency DEBUG logs may contain HTTP parameters or serialized updates.
    logging.getLogger("aiohttp").setLevel(logging.WARNING)
    logging.getLogger("aiogram").setLevel(logging.WARNING)
    logging.getLogger("redis").setLevel(logging.WARNING)


def safe_exception_info(
    exception: BaseException,
) -> tuple[type[BaseException], BaseException, TracebackType | None]:
    """Keep traceback locations while removing the exception message."""
    sanitized = RuntimeError(f"{type(exception).__name__} (details redacted)")
    return RuntimeError, sanitized, exception.__traceback__


__all__ = ("configure_logging", "safe_exception_info")
