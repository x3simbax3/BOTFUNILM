import sqlite3
import tempfile
import unittest
from pathlib import Path
from typing import Any

from src.database.media import upsert_media
from src.database.user_media import save_user_media

PROJECT_ROOT = Path(__file__).resolve().parents[2]
MIGRATIONS = sorted((PROJECT_ROOT / "migrations").glob("*.sql"))


class DatabaseTestCase(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        self._temporary_directory = tempfile.TemporaryDirectory()
        database_file = Path(self._temporary_directory.name) / "test.db"
        self.database_url = f"sqlite:///{database_file}"

        with sqlite3.connect(database_file) as connection:
            for migration in MIGRATIONS:
                connection.executescript(migration.read_text(encoding="utf-8"))

    def tearDown(self) -> None:
        self._temporary_directory.cleanup()

    async def create_media(
        self,
        *,
        tmdb_id: int | None = 42,
        content_format: str = "full_length",
        content_type: str = "movie",
        title: str = "Movie",
        **kwargs: Any,
    ) -> int:
        return await upsert_media(
            tmdb_id=tmdb_id,
            content_format=content_format,
            content_type=content_type,
            title=title,
            database_url=self.database_url,
            **kwargs,
        )

    async def create_user_media(
        self,
        *,
        user_id: int = 123,
        media_id: int | None = None,
        status: str = "planned",
        media_kwargs: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> int:
        if media_id is None:
            media_id = await self.create_media(**(media_kwargs or {}))
        await save_user_media(
            user_id=user_id,
            media_id=media_id,
            status=status,
            database_url=self.database_url,
            **kwargs,
        )
        return media_id

    async def create_series(
        self,
        *,
        tmdb_id: int | None = 42,
        title: str = "TV",
        **kwargs: Any,
    ) -> int:
        return await self.create_media(
            tmdb_id=tmdb_id,
            content_format="series",
            content_type="movie",
            title=title,
            **kwargs,
        )
