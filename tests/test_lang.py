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
        self.assertEqual(locale.keyboards.MAIN_ADD, "＋\u00a0Добавить")
        self.assertIs(locale, lang.get_locale("ru"))

    def test_start_text_uses_asymmetric_action_heading(self) -> None:
        self.assertNotIn("(˶ᵔ ᵕ ᵔ˶)", lang.START_TEXT)
        self.assertIn("━━━  <b>BotFunilm</b>  ━━━", lang.START_TEXT)
        self.assertIn("╭ <b>Куда дальше?</b>", lang.START_TEXT)
        self.assertIn("╰ <i>Выбери действие ниже</i>", lang.START_TEXT)

    def test_selected_cartoon_series_is_named_multiseries(self) -> None:
        result = lang.selected_type_text("add", "series", "cartoon")

        self.assertIn("Мультсериал", result)
        self.assertNotIn("Сериалы · Мультфильм", result)

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
            [
                {
                    "id": 7,
                    "title": "Tom & Jerry",
                    "content_format": "full_length",
                },
                {
                    "id": 8,
                    "title": "Second title",
                    "content_format": "full_length",
                },
            ],
            "BotFunilmBot",
            offset=20,
        )

        self.assertIn("21.", result)
        self.assertIn(
            '<a href="https://t.me/BotFunilmBot?start=media_7">21. Tom &amp; Jerry</a>',
            result,
        )
        self.assertIn("╭ <b>Моя библиотека</b>", result)
        self.assertIn(
            "╰ <i>Сортировка по дате</i>",
            result,
        )
        self.assertEqual(result.count("•  ◇  •"), 1)

        rating_result = lang.library_text(
            [
                {
                    "id": 7,
                    "title": "Tom & Jerry",
                    "content_format": "full_length",
                }
            ],
            "BotFunilmBot",
            sort_order="rating",
        )
        self.assertIn(
            "╰ <i>Сортировка по моей оценке</i>",
            rating_result,
        )

        badge_result = lang.library_text(
            [
                {
                    "id": 7,
                    "title": "Топовый фильм",
                    "content_format": "full_length",
                    "badge": "top",
                }
            ],
            "BotFunilmBot",
        )
        self.assertIn(">1. Топовый фильм</a> 🔥", badge_result)

    def test_empty_library_text_differs_from_empty_filtered_results(self) -> None:
        empty_library = lang.library_text(
            [],
            "BotFunilmBot",
            library_is_empty=True,
        )
        empty_filters = lang.library_text([], "BotFunilmBot")

        self.assertIn("Добавь первую запись в библиотеку.", empty_library)
        self.assertNotIn("Измени фильтры", empty_library)
        self.assertIn("Измени фильтры и попробуй снова.", empty_filters)

    def test_library_text_shows_series_progress_status_and_rating(self) -> None:
        result = lang.library_text(
            [
                {
                    "id": 7,
                    "title": "Сериал",
                    "content_format": "series",
                    "user_status": "watching",
                    "episodes_watched": 7,
                    "number_of_episodes": 10,
                    "user_rating": 8,
                    "rating": 8.4,
                    "tmdb_status": "Returning Series",
                    "tmdb_in_production": 1,
                }
            ],
            "BotFunilmBot",
        )

        self.assertIn(
            "7 из 10 серий · Смотрю · Моя · 8/10 · TMDB · 8.4/10",
            result,
        )
        self.assertIn(">1. Сериал</a> 🔴", result)
        self.assertNotIn(
            '<a href="https://t.me/BotFunilmBot?start=media_7">7 из 10',
            result,
        )

    def test_search_result_shows_description_as_plain_text(self) -> None:
        result = lang.tmdb_guess_text("full_length", "Фильм", "Описание")

        self.assertIn("<b>Описание</b>\nОписание", result)
        self.assertNotIn("<blockquote>", result)

    def test_unreleased_item_without_date_shows_unknown_premiere(self) -> None:
        result = lang.library_item_text(
            {
                "title": "Будущий фильм",
                "original_title": None,
                "description": None,
                "content_format": "full_length",
                "content_type": "movie",
                "user_status": "planned",
                "user_rating": None,
                "rating": None,
                "release_date": None,
                "first_air_date": None,
                "number_of_seasons": None,
                "number_of_episodes": None,
                "library_users_count": 1,
                "is_released": False,
            }
        )

        self.assertIn("Дата премьеры пока неизвестна", result)

    def test_library_item_uses_combined_media_kind_and_styled_watching_icon(
        self,
    ) -> None:
        item = {
            "title": "Мультсериал",
            "original_title": None,
            "description": "Описание",
            "content_format": "series",
            "content_type": "cartoon",
            "user_status": "watching",
            "user_rating": None,
            "rating": None,
            "release_date": None,
            "first_air_date": None,
            "number_of_seasons": 1,
            "number_of_episodes": 10,
            "episodes_watched": 3,
            "library_users_count": 12,
            "tmdb_status": "Returning Series",
            "tmdb_in_production": 1,
            "next_episode_air_date": "2026-08-17",
            "next_episode_season_number": 2,
            "next_episode_number": 6,
        }

        result = lang.library_item_text(item)

        self.assertIn("<i>Мультсериал</i>", result)
        self.assertNotIn("Сериалы · Мультфильм", result)
        self.assertIn("Статус · <b>◉ Смотрю</b>", result)
        self.assertIn("Добавили · <b>12</b>", result)
        self.assertIn(
            "Следующая серия · <b>2 сезон, 6 серия · 17.08.2026</b>",
            result,
        )
        self.assertIn("🔴 <b>Сейчас выходит</b>", result)

    def test_active_series_tracking_shows_aired_and_announced_totals(self) -> None:
        result = lang.series_tracking_text(
            "Сериал",
            [
                {
                    "season_number": 1,
                    "name": "Сезон 1",
                    "episode_count": 5,
                    "announced_episode_count": 12,
                }
            ],
            is_ongoing=True,
        )

        self.assertIn("вышло 5 из 12 сер.", result)
        self.assertIn("🔴 <b>Сейчас выходит</b>", result)

    def test_series_text_rejects_progress_above_total(self) -> None:
        with self.assertRaises(ValueError):
            lang.tracking_complete_text("Series", 10, 11, 8.0)

        with self.assertRaises(ValueError):
            lang.episodes_prompt_text("Series", "Season 1", 10, -1)

    def test_saved_series_progress_uses_styled_series_symbol(self) -> None:
        result = lang.tracking_complete_text("Series", 10, 10, 8.0)

        self.assertIn("▣\u00a0<b>Series</b>", result)
        self.assertNotIn("📺", result)


if __name__ == "__main__":
    unittest.main()
