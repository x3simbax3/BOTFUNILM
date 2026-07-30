"""Release availability rules shared by handlers and background jobs."""

from __future__ import annotations

from datetime import date


def release_date_has_passed(value: object, *, today: date | None = None) -> bool:
    """Treat missing or malformed dates as available instead of blocking a title."""
    if not isinstance(value, str) or not value:
        return True
    try:
        release_date = date.fromisoformat(value)
    except ValueError:
        return True
    return release_date <= (today or date.today())


__all__ = ("release_date_has_passed",)
