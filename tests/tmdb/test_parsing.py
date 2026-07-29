import unittest

from src import tmdb


class TmdbParsingTests(unittest.TestCase):
    def test_parse_title_with_poster(self) -> None:
        result = tmdb._parse_title(
            {
                "title": "Форсаж",
                "overview": "desc",
                "poster_path": "/p.jpg",
                "vote_average": 7.8,
            },
            "Форсаж",
        )
        self.assertEqual(result.title, "Форсаж")
        self.assertEqual(result.poster_url, f"{tmdb.TMDB_IMAGE_URL}/p.jpg")
        self.assertEqual(result.rating, 7.8)

    def test_parse_title_without_poster(self) -> None:
        result = tmdb._parse_title({"title": "Форсаж"}, "Форсаж")
        self.assertIsNone(result.poster_url)

    def test_parse_title_missing_title_raises(self) -> None:
        with self.assertRaises(tmdb.TmdbNotFoundError):
            tmdb._parse_title({"overview": "no title"})

    # --- async ---
