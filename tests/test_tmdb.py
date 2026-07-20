import json
import unittest
from urllib.error import HTTPError, URLError
from unittest.mock import patch

from src import tmdb


class ResponseMock:
    def __init__(self, payload: bytes) -> None:
        self.payload = payload

    def __enter__(self) -> "ResponseMock":
        return self

    def __exit__(self, exc_type, exc_value, traceback) -> None:
        return None

    def read(self) -> bytes:
        return self.payload


class TmdbSearchTests(unittest.TestCase):
    def test_empty_query_raises_value_error(self) -> None:
        empty_queries = ["", "   ", "\"\"", "«»", "  ' `  "]

        for query in empty_queries:
            with self.subTest(query=query):
                with self.assertRaises(ValueError):
                    tmdb._find_title_guess(query, "full_length")

    def test_series_uses_tv_search_endpoint(self) -> None:
        with patch.object(tmdb, "TMDB_API", "token"), patch.object(
            tmdb,
            "_request_json",
            return_value={"results": [{"name": "Во все тяжкие"}]},
        ) as request_json:
            tmdb._find_title_guess("Во все тяжкие", "series")

        request_json.assert_called_once_with(
            f"{tmdb.TMDB_URL.rstrip('/')}/search/tv",
            "Во все тяжкие",
        )

    def test_non_series_uses_movie_search_endpoint(self) -> None:
        with patch.object(tmdb, "TMDB_API", "token"), patch.object(
            tmdb,
            "_request_json",
            return_value={"results": [{"title": "Ёлки"}]},
        ) as request_json:
            tmdb._find_title_guess("Ёлки", "full_length")

        request_json.assert_called_once_with(
            f"{tmdb.TMDB_URL.rstrip('/')}/search/movie",
            "Ёлки",
        )

    def test_request_json_without_api_token_raises_not_configured(self) -> None:
        with patch.object(tmdb, "TMDB_API", ""):
            with self.assertRaises(tmdb.TmdbNotConfiguredError):
                tmdb._request_json("https://example.test/search/movie", "Ёлки")

    def test_empty_results_raise_not_found(self) -> None:
        with patch.object(tmdb, "TMDB_API", "token"), patch.object(
            tmdb,
            "_request_json",
            return_value={"results": []},
        ):
            with self.assertRaises(tmdb.TmdbNotFoundError):
                tmdb._find_title_guess("Неизвестный тайтл", "full_length")

    def test_result_without_title_fields_raises_not_found(self) -> None:
        with patch.object(tmdb, "TMDB_API", "token"), patch.object(
            tmdb,
            "_request_json",
            return_value={"results": [{"overview": "Описание без названия"}]},
        ):
            with self.assertRaises(tmdb.TmdbNotFoundError):
                tmdb._find_title_guess("Тайтл", "full_length")

    def test_parse_title_with_poster(self) -> None:
        result = tmdb._parse_title(
            {
                "title": "Ёлки",
                "overview": "Новогодняя комедия.",
                "poster_path": "/poster.jpg",
            }
        )

        self.assertEqual(result.title, "Ёлки")
        self.assertEqual(result.overview, "Новогодняя комедия.")
        self.assertEqual(result.poster_url, f"{tmdb.TMDB_IMAGE_URL}/poster.jpg")

    def test_parse_title_without_poster(self) -> None:
        result = tmdb._parse_title(
            {
                "title": "Ёлки",
                "overview": "Новогодняя комедия.",
                "poster_path": None,
            }
        )

        self.assertEqual(result.poster_url, None)

    def test_parse_title_allows_empty_overview(self) -> None:
        result = tmdb._parse_title({"title": "Ёлки", "overview": None})

        self.assertEqual(result.overview, None)

    def test_request_json_wraps_http_url_timeout_and_json_errors(self) -> None:
        errors = [
            HTTPError("https://example.test", 500, "Server Error", {}, None),
            URLError("connection failed"),
            TimeoutError("timeout"),
            json.JSONDecodeError("bad json", "", 0),
        ]

        for error in errors:
            with self.subTest(error=type(error).__name__):
                with patch.object(tmdb, "TMDB_API", "token"), patch.object(
                    tmdb,
                    "urlopen",
                    side_effect=error,
                ):
                    with self.assertRaises(tmdb.TmdbError):
                        tmdb._request_json(
                            "https://example.test/search/movie",
                            "Ёлки",
                        )

    def test_request_json_wraps_invalid_response_json(self) -> None:
        with patch.object(tmdb, "TMDB_API", "token"), patch.object(
            tmdb,
            "urlopen",
            return_value=ResponseMock(b"{not-json"),
        ):
            with self.assertRaises(tmdb.TmdbError):
                tmdb._request_json("https://example.test/search/movie", "Ёлки")

    def test_normalize_query_trims_spaces_and_quotes(self) -> None:
        self.assertEqual(tmdb._normalize_query("  «  Ёлки   новые  »  "), "Ёлки новые")

    def test_normalize_for_match_ignores_case_and_yo_letter(self) -> None:
        self.assertEqual(tmdb._normalize_for_match("  «ЁЛКИ» "), "елки")

    def test_select_best_result_treats_yo_and_e_as_equal(self) -> None:
        results = [
            {"title": "Елки 5"},
            {"title": "Ёлки"},
            {"title": "Ёлки новые"},
        ]

        result = tmdb._select_best_result(results, "елки")

        self.assertEqual(result["title"], "Ёлки")

    def test_select_best_result_uses_title_name_and_original_titles(self) -> None:
        cases = [
            ("Матрица", "title"),
            ("Клиника", "name"),
            ("Spirited Away", "original_title"),
            ("Breaking Bad", "original_name"),
        ]

        for query, field_name in cases:
            with self.subTest(field_name=field_name):
                results = [
                    {"title": "Похожий, но не тот"},
                    {field_name: query},
                ]

                result = tmdb._select_best_result(results, query)

                self.assertEqual(result[field_name], query)


if __name__ == "__main__":
    unittest.main()
