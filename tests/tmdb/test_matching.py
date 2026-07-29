import unittest

from src import tmdb


class TmdbMatchingTests(unittest.TestCase):
    def test_exact_match(self) -> None:
        score = tmdb._relevance_score({"title": "Форсаж"}, "Форсаж")
        self.assertEqual(score, 1000.0)

    def test_normalization_handles_case_punctuation_and_yo(self) -> None:
        self.assertEqual(
            tmdb._normalize_text("  МОЁ_Кино!!! "),
            "мое кино",
        )

    def test_punctuation_only_query_does_not_match(self) -> None:
        score = tmdb._relevance_score({"title": "Форсаж"}, "!!!")
        self.assertEqual(score, 0.0)

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
        self.assertEqual(score, 2.5)

    def test_original_title_checked(self) -> None:
        result = {"title": "Неправильное", "original_title": "Форсаж", "popularity": 50}
        score = tmdb._relevance_score(result, "Форсаж")
        self.assertGreater(score, 1000)

    def test_word_overlap(self) -> None:
        result = {"title": "Матрица Перезагрузка", "popularity": 50}
        score = tmdb._relevance_score(result, "Матрица")
        self.assertGreater(score, 200)

    def test_one_shared_word_does_not_make_long_query_relevant(self) -> None:
        result = {"title": "Матрица времени", "popularity": 1000}
        score = tmdb._relevance_score(
            result,
            "длинное название матрица совершенно другого фильма",
        )
        self.assertLess(score, tmdb.MIN_RELEVANCE)

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

    # --- _parse_title ---
