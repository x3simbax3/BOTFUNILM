import unittest

from src import lang


class LocalizationTests(unittest.TestCase):
    def test_normalizes_telegram_language_codes(self) -> None:
        self.assertEqual(lang.normalize_locale("ru-RU"), "ru")
        self.assertEqual(lang.normalize_locale("ru_RU"), "ru")

    def test_unknown_and_missing_locales_fall_back_to_default(self) -> None:
        self.assertEqual(lang.normalize_locale(None), lang.DEFAULT_LOCALE)
        self.assertEqual(lang.normalize_locale("en-US"), lang.DEFAULT_LOCALE)

    def test_locale_exposes_domain_modules(self) -> None:
        locale = lang.get_locale("ru-RU")

        self.assertEqual(locale.menu.START_TEXT, lang.START_TEXT)
        self.assertEqual(locale.keyboards.MAIN_ADD, "➕ Добавить")
        self.assertIs(locale, lang.get_locale("ru"))

    def test_animation_uses_its_own_rating_categories(self) -> None:
        for content_type in ("anime", "cartoon"):
            with self.subTest(content_type=content_type):
                categories = lang.rating_categories(content_type)

                self.assertEqual(categories[0], ("animation", "Анимация"))
                self.assertIn(("characters", "Персонажи"), categories)
                self.assertNotIn(("acting", "Актёрская игра"), categories)

    def test_movie_keeps_acting_rating_category(self) -> None:
        self.assertIn(
            ("acting", "Актёрская игра"),
            lang.rating_categories("movie"),
        )

    def test_tmdb_guess_text_escapes_title_and_overview_html(self) -> None:
        result = lang.tmdb_guess_text(
            "full_length",
            "Tom & Jerry <Best>",
            "A > B & C < D",
        )

        self.assertIn("Tom &amp; Jerry &lt;Best&gt;", result)
        self.assertIn("A &gt; B &amp; C &lt; D", result)
        self.assertNotIn("Tom & Jerry <Best>", result)
        self.assertNotIn("A > B & C < D", result)

    def test_unknown_keys_raise_key_error(self) -> None:
        cases = [
            (lang.action_text, ("unknown",)),
            (lang.content_type_text, ("unknown", "full_length")),
            (lang.content_type_text, ("add", "unknown")),
            (lang.selected_type_text, ("add", "full_length", "unknown")),
            (lang.tmdb_guess_text, ("unknown", "Название", "Описание")),
        ]

        for function, args in cases:
            with self.subTest(function=function.__name__, args=args):
                with self.assertRaises(KeyError):
                    function(*args)

    def test_library_text_numbers_and_escapes_clickable_titles(self) -> None:
        result = lang.library_text(
            [{"id": 7, "title": "Tom & Jerry"}],
            "BotFunilmBot",
            offset=20,
        )

        self.assertIn("21.", result)
        self.assertIn(
            '<a href="https://t.me/BotFunilmBot?start=media_7">Tom &amp; Jerry</a>',
            result,
        )

    def test_series_text_rejects_progress_above_total(self) -> None:
        with self.assertRaises(ValueError):
            lang.tracking_complete_text("Series", 10, 11, 8.0)

        with self.assertRaises(ValueError):
            lang.episodes_prompt_text("Series", "Season 1", 10, -1)


if __name__ == "__main__":
    unittest.main()
