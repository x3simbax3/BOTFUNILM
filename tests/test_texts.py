import unittest

from src import texts


class TextsTests(unittest.TestCase):
    def test_animation_uses_its_own_rating_categories(self) -> None:
        for content_type in ("anime", "cartoon"):
            with self.subTest(content_type=content_type):
                categories = texts.rating_categories(content_type)

                self.assertEqual(categories[0], ("animation", "Анимация"))
                self.assertIn(("characters", "Персонажи"), categories)
                self.assertNotIn(("acting", "Актёрская игра"), categories)

    def test_movie_keeps_acting_rating_category(self) -> None:
        self.assertIn(
            ("acting", "Актёрская игра"),
            texts.rating_categories("movie"),
        )

    def test_tmdb_guess_text_escapes_title_and_overview_html(self) -> None:
        result = texts.tmdb_guess_text(
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
            (texts.action_text, ("unknown",)),
            (texts.content_type_text, ("unknown", "full_length")),
            (texts.content_type_text, ("add", "unknown")),
            (texts.selected_type_text, ("add", "full_length", "unknown")),
            (texts.tmdb_guess_text, ("unknown", "Название", "Описание")),
        ]

        for function, args in cases:
            with self.subTest(function=function.__name__, args=args):
                with self.assertRaises(KeyError):
                    function(*args)


if __name__ == "__main__":
    unittest.main()
