import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from aiogram.types import FSInputFile

from src import posters


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

        self.assertEqual(result, "https://image.tmdb.org/t/p/w500/poster.jpg")

    def test_accepts_allowed_https_poster_url(self) -> None:
        url = "https://image.tmdb.org/t/p/w500/poster.jpg"

        self.assertEqual(posters.poster_input(url), url)

    def test_rejects_untrusted_or_insecure_poster_url(self) -> None:
        for url in (
            "https://attacker.example/poster.jpg",
            "http://image.tmdb.org/poster.jpg",
            "https://user:password@image.tmdb.org/poster.jpg",
        ):
            with self.subTest(url=url):
                self.assertIsNone(posters.poster_input(url))

    def test_rejected_url_log_does_not_include_path_or_query(self) -> None:
        url = "https://attacker.example/private-title.jpg?user-input=secret"

        with self.assertLogs(posters.logger, level="WARNING") as captured:
            self.assertIsNone(posters.poster_input(url))

        rendered = "\n".join(captured.output)
        self.assertIn("attacker.example", rendered)
        self.assertNotIn("private-title", rendered)
        self.assertNotIn("user-input", rendered)

    def test_extracts_largest_sent_photo_file_id(self) -> None:
        message = SimpleNamespace(
            photo=[SimpleNamespace(file_id="small"), SimpleNamespace(file_id="large")]
        )

        self.assertEqual(posters.sent_photo_file_id(message), "large")


if __name__ == "__main__":
    unittest.main()
