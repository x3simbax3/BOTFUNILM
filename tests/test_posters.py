import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from aiogram.types import FSInputFile

from src import posters


class ContentStub:
    async def iter_chunked(self, size: int):
        yield b"poster-data"


class ResponseStub:
    status = 200
    headers = {"Content-Type": "image/jpeg"}
    content = ContentStub()

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, traceback) -> None:
        pass


class SessionStub:
    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, traceback) -> None:
        pass

    def get(self, url: str) -> ResponseStub:
        return ResponseStub()


class PosterInputTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.media_root = Path(self.temporary_directory.name).resolve()
        self.media_root_patcher = patch.object(posters, "MEDIA_ROOT", self.media_root)
        self.media_root_patcher.start()

    def tearDown(self) -> None:
        self.media_root_patcher.stop()
        self.temporary_directory.cleanup()

    def test_returns_local_file(self) -> None:
        poster_path = self.media_root / "posters" / "tmdb_movie_42.jpg"
        poster_path.parent.mkdir()
        poster_path.write_bytes(b"image")

        result = posters.poster_input("posters/tmdb_movie_42.jpg")

        self.assertIsInstance(result, FSInputFile)
        self.assertEqual(Path(result.path), poster_path)

    def test_rejects_path_outside_media_root(self) -> None:
        result = posters.poster_input("../secret.jpg")

        self.assertIsNone(result)

    def test_keeps_legacy_tmdb_path(self) -> None:
        result = posters.poster_input("/poster.jpg")

        self.assertEqual(result, "https://image.tmdb.org/t/p/original/poster.jpg")


class PosterDownloadTests(unittest.IsolatedAsyncioTestCase):
    async def test_without_url_does_not_create_file(self) -> None:
        result = await posters.download_poster(None, 42, "full_length")

        self.assertIsNone(result)

    async def test_downloads_poster_to_media_root(self) -> None:
        with (
            tempfile.TemporaryDirectory() as temporary_directory,
            patch.object(posters, "MEDIA_ROOT", Path(temporary_directory)),
            patch.object(posters.aiohttp, "ClientSession", return_value=SessionStub()),
        ):
            result = await posters.download_poster(
                "https://image.test/poster.jpg",
                42,
                "series",
            )

            self.assertEqual(result, "posters/tmdb_series_42.jpg")
            saved = Path(temporary_directory) / result
            self.assertEqual(saved.read_bytes(), b"poster-data")

    def test_image_extension_ignores_query_string(self) -> None:
        self.assertEqual(posters._image_extension("https://test/p.webp?v=1"), ".webp")
        self.assertEqual(posters._image_extension("https://test/poster"), ".jpg")


if __name__ == "__main__":
    unittest.main()
