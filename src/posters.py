import logging
from urllib.parse import urlsplit

from aiogram.types import FSInputFile

from config.config import MEDIA_ROOT, POSTER_ALLOWED_HOSTS

logger = logging.getLogger(__name__)


def poster_input(poster_path: str | None) -> str | FSInputFile | None:
    """Готовит локальный файл или старый внешний путь для отправки в Telegram."""
    if not poster_path:
        return None
    if poster_path.startswith(("http://", "https://")):
        return poster_path if _is_allowed_poster_url(poster_path) else None
    if poster_path.startswith("/"):
        from src.tmdb import TMDB_IMAGE_URL

        url = f"{TMDB_IMAGE_URL}{poster_path}"
        return url if _is_allowed_poster_url(url) else None

    local_path = (MEDIA_ROOT / poster_path).resolve()
    try:
        local_path.relative_to(MEDIA_ROOT)
    except ValueError:
        logger.warning("Некорректный локальный путь постера: %s", poster_path)
        return None

    return FSInputFile(local_path) if local_path.is_file() else None


def _is_allowed_poster_url(url: str) -> bool:
    try:
        parsed = urlsplit(url)
        hostname = (parsed.hostname or "").lower().rstrip(".")
        _ = parsed.port
    except ValueError:
        hostname = ""
        parsed = None
    allowed = bool(
        parsed
        and parsed.scheme.lower() == "https"
        and hostname in POSTER_ALLOWED_HOSTS
        and parsed.username is None
        and parsed.password is None
        and not parsed.fragment
    )
    if not allowed:
        logger.warning("Отклонён недоверенный URL постера: %s", url)
    return allowed


def sent_photo_file_id(message: object) -> str | None:
    """Return the largest Telegram photo's reusable bot-specific file id."""
    photos = getattr(message, "photo", None)
    if not photos:
        return None
    file_id = getattr(photos[-1], "file_id", None)
    return file_id if isinstance(file_id, str) and file_id else None
