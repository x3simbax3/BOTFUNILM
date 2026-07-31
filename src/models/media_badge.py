"""Supported user badges for saved titles."""

MEDIA_BADGES = frozenset({"cry", "sad", "top", "funny"})


def validate_media_badge(value: str | None) -> None:
    if value is not None and value not in MEDIA_BADGES:
        raise ValueError("Unknown media badge")


__all__ = ("MEDIA_BADGES", "validate_media_badge")
