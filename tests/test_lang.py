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


if __name__ == "__main__":
    unittest.main()
