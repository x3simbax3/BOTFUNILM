import asyncio
import unittest
from unittest.mock import AsyncMock, patch

from src import tmdb


class TmdbSearchTests(unittest.IsolatedAsyncioTestCase):
    # --- _make_queries ---

    def test_make_queries_returns_original_first(self) -> None:
        queries = tmdb._make_queries("О моем перерождении в слизь")
        self.assertEqual(queries[0], "О моем перерождении в слизь")

    def test_make_queries_removes_stop_words(self) -> None:
        queries = tmdb._make_queries("О моем перерождении в слизь")
        self.assertIn("моем перерождении слизь", queries)

    def test_make_queries_keeps_long_words(self) -> None:
        queries = tmdb._make_queries("Токийский гуль")
        self.assertIn("Токийский гуль", queries)

    def test_make_queries_deduplicates(self) -> None:
        queries = tmdb._make_queries("Аниме")
        # "Аниме" без стоп-слов = "Аниме" (дубликат)
        normalized = [tmdb._normalize_text(q) for q in queries]
        self.assertEqual(len(normalized), len(set(normalized)))

    # --- _relevance_score ---

    def test_exact_match(self) -> None:
        score = tmdb._relevance_score({"title": "Форсаж"}, "Форсаж")
        self.assertEqual(score, 1000.0)

    def test_cyrillic_variants_match(self) -> None:
        result = {"title": "О моём перерождении в слизь", "popularity": 200}
        score = tmdb._relevance_score(result, "о моем перерождении в сизь")
        self.assertGreater(score, 400)

    def test_wrong_title_scores_low(self) -> None:
        result = {"title": "Реинкарнация безработного", "popularity": 300}
        score = tmdb._relevance_score(result, "о моем перерождении в сизь")
        self.assertLess(score, 350)

    def test_exact_match_beats_popularity(self) -> None:
        popular = {"title": "Дом дракона", "popularity": 1000}
        exact = {"title": "Форсаж", "popularity": 10}
        scored = [(tmdb._relevance_score(r, "Форсаж"), r) for r in (popular, exact)]
        scored.sort(key=lambda x: x[0], reverse=True)
        self.assertEqual(scored[0][1]["title"], "Форсаж")

    def test_tokisky_goul_match(self) -> None:
        """Токийский гурь -> Токийский гуль"""
        result = {"title": "Токийский гуль", "popularity": 200}
        score = tmdb._relevance_score(result, "Токийский гурь")
        self.assertGreater(score, 300)

    def test_no_match(self) -> None:
        result = {"title": "Дом дракона", "popularity": 50}
        score = tmdb._relevance_score(result, "Форсаж")
        self.assertEqual(score, 5.0)

    def test_original_title_checked(self) -> None:
        result = {"title": "Неправильное", "original_title": "Форсаж", "popularity": 50}
        score = tmdb._relevance_score(result, "Форсаж")
        self.assertGreater(score, 1000)

    def test_word_overlap(self) -> None:
        result = {"title": "Матрица Перезагрузка", "popularity": 50}
        score = tmdb._relevance_score(result, "Матрица")
        self.assertGreater(score, 200)

    # --- _pick_best ---

    def test_pick_best_prefers_relevant(self) -> None:
        results = [
            {"title": "Реинкарнация безработного", "popularity": 500, "genre_ids": [16], "original_language": "ja"},
            {"title": "О моём перерождении в слизь", "popularity": 200, "genre_ids": [16], "original_language": "ja"},
        ]
        best = tmdb._pick_best(results, "о моем перерождении в сизь")
        self.assertEqual(best.title, "О моём перерождении в слизь")

    # --- _merge_search_results ---

    def test_merge_deduplicates(self) -> None:
        item = {"id": 1, "title": "Movie", "media_type": "movie"}
        merged = tmdb._merge_search_results({"results": [item]}, {"results": [item]}, "movie")
        self.assertEqual(len(merged), 1)

    def test_merge_filters_wrong_media_type(self) -> None:
        movie = {"id": 1, "media_type": "movie"}
        tv = {"id": 2, "media_type": "tv"}
        merged = tmdb._merge_search_results({"results": [movie, tv]}, {"results": []}, "movie")
        self.assertEqual(len(merged), 1)

    # --- _filter_by_content_type ---

    def test_filter_anime_with_genre_ids(self) -> None:
        results = [
            {"genre_ids": [16], "original_language": "ja"},
            {"genre_ids": [16], "original_language": "en"},
            {"genre_ids": [28], "original_language": "en"},
        ]
        self.assertEqual(len(tmdb._filter_by_content_type(results, "anime")), 1)

    def test_filter_anime_without_genre_ids_uses_language(self) -> None:
        results = [
            {"original_language": "ja"},
            {"original_language": "en"},
        ]
        filtered = tmdb._filter_by_content_type(results, "anime")
        self.assertEqual(len(filtered), 1)
        self.assertEqual(filtered[0]["original_language"], "ja")

    def test_filter_cartoon(self) -> None:
        results = [
            {"genre_ids": [16], "original_language": "ja"},
            {"genre_ids": [16], "original_language": "en"},
        ]
        self.assertEqual(len(tmdb._filter_by_content_type(results, "cartoon")), 1)

    def test_filter_movie_excludes_animation(self) -> None:
        results = [
            {"genre_ids": [16], "original_language": "ja"},
            {"genre_ids": [28], "original_language": "en"},
        ]
        self.assertEqual(len(tmdb._filter_by_content_type(results, "movie")), 1)

    def test_filter_movie_keeps_unknown_genre(self) -> None:
        results = [{"original_language": "en"}]
        self.assertEqual(len(tmdb._filter_by_content_type(results, "movie")), 1)

    # --- edge cases ---

    def test_is_anime_without_genre_ids_ja(self) -> None:
        self.assertTrue(tmdb._is_anime({"original_language": "ja"}))

    def test_is_anime_without_genre_ids_non_ja(self) -> None:
        self.assertFalse(tmdb._is_anime({"original_language": "en"}))

    def test_is_animation_without_genre_ids(self) -> None:
        self.assertFalse(tmdb._is_animation({"original_language": "ja"}))

    def test_discover_genre_filter(self) -> None:
        self.assertEqual(tmdb._discover_genre_filter("anime")["with_original_language"], "ja")
        self.assertEqual(tmdb._discover_genre_filter("cartoon")["with_original_language.not"], "ja")
        self.assertEqual(tmdb._discover_genre_filter("movie")["without_genres"], "16")

    # --- _parse_title ---

    def test_parse_title_with_poster(self) -> None:
        result = tmdb._parse_title({"title": "Форсаж", "overview": "desc", "poster_path": "/p.jpg"}, "Форсаж")
        self.assertEqual(result.title, "Форсаж")
        self.assertEqual(result.poster_url, f"{tmdb.TMDB_IMAGE_URL}/p.jpg")

    def test_parse_title_without_poster(self) -> None:
        result = tmdb._parse_title({"title": "Форсаж"}, "Форсаж")
        self.assertIsNone(result.poster_url)

    def test_parse_title_missing_title_raises(self) -> None:
        with self.assertRaises(tmdb.TmdbNotFoundError):
            tmdb._parse_title({"overview": "no title"})

    # --- async ---

    async def test_empty_query_raises(self) -> None:
        with self.assertRaises(ValueError):
            await tmdb.find_title_guess("", "full_length", "movie")

    async def test_no_api_key_raises(self) -> None:
        with patch.object(tmdb, "TMDB_API", ""):
            with self.assertRaises(tmdb.TmdbNotConfiguredError):
                await tmdb.find_title_guess("test", "full_length", "movie")


if __name__ == "__main__":
    unittest.main()
