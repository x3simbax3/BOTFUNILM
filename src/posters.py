import logging
from pathlib import Path
from urllib.parse import urlparse
from uuid import uuid4

import aiohttp
from aiogram.types import FSInputFile

from config.config import MEDIA_ROOT


logger = logging.getLogger(__name__)

POSTERS_DIR = "posters"
MAX_POSTER_SIZE = 10 * 1024 * 1024


async def download_poster(
    poster_url: str | None,
    tmdb_id: int,
    content_format: str,
) -> str | None:
    """Скачивает постер и возвращает путь относительно MEDIA_ROOT."""
    if not poster_url or tmdb_id <= 0:
        return None

    extension = _image_extension(poster_url)
    format_name = "series" if content_format == "series" else "movie"
    relative_path = Path(POSTERS_DIR) / f"tmdb_{format_name}_{tmdb_id}{extension}"
    destination = MEDIA_ROOT / relative_path
    temporary = destination.with_name(f".{destination.name}.{uuid4().hex}.tmp")

    if destination.is_file():
        return relative_path.as_posix()

    destination.parent.mkdir(parents=True, exist_ok=True)

    try:
        timeout = aiohttp.ClientTimeout(total=30)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.get(poster_url) as response:
                if response.status != 200:
                    logger.warning(
                        "Не удалось скачать постер TMDB %s: HTTP %s",
                        tmdb_id,
                        response.status,
                    )
                    return None

                content_type = response.headers.get("Content-Type", "")
                if not content_type.startswith("image/"):
                    logger.warning("TMDB %s вернул не изображение", tmdb_id)
                    return None

                size = 0
                with temporary.open("wb") as poster_file:
                    async for chunk in response.content.iter_chunked(64 * 1024):
                        size += len(chunk)
                        if size > MAX_POSTER_SIZE:
                            raise ValueError("постер превышает 10 МБ")
                        poster_file.write(chunk)

        temporary.replace(destination)
        return relative_path.as_posix()
    except (aiohttp.ClientError, TimeoutError, OSError, ValueError) as exc:
        logger.warning("Не удалось сохранить постер TMDB %s: %s", tmdb_id, exc)
        temporary.unlink(missing_ok=True)
        return None


def poster_input(poster_path: str | None) -> str | FSInputFile | None:
    """Готовит локальный файл или старый внешний путь для отправки в Telegram."""
    if not poster_path:
        return None
    if poster_path.startswith(("http://", "https://")):
        return poster_path
    if poster_path.startswith("/"):
        from src.tmdb import TMDB_IMAGE_URL

        return f"{TMDB_IMAGE_URL}{poster_path}"

    local_path = (MEDIA_ROOT / poster_path).resolve()
    try:
        local_path.relative_to(MEDIA_ROOT)
    except ValueError:
        logger.warning("Некорректный локальный путь постера: %s", poster_path)
        return None

    return FSInputFile(local_path) if local_path.is_file() else None


def _image_extension(url: str) -> str:
    suffix = Path(urlparse(url).path).suffix.lower()
    return suffix if suffix in {".jpg", ".jpeg", ".png", ".webp"} else ".jpg"
