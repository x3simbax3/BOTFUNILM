from src import keyboards
from tests.support.keyboards import KeyboardTestCase


class MenuKeyboardTests(KeyboardTestCase):
    def test_main_menu_buttons_have_expected_callbacks(self) -> None:
        keyboard = keyboards.main_menu_keyboard()
        self.assert_callback_rows(
            keyboard,
            [["menu:library", "menu:settings"]],
        )
        self.assertEqual(keyboard.inline_keyboard[0][1].text, "⚙\u00a0Настройки")

    def test_main_menu_shows_disabled_news(self) -> None:
        keyboard = keyboards.settings_keyboard(news_enabled=False)

        self.assertIn("выкл", keyboard.inline_keyboard[0][0].text)

    def test_library_menu_has_library_tracked_and_add_sections(self) -> None:
        self.assert_callback_rows(
            keyboards.library_menu_keyboard(),
            [
                ["menu:library:all"],
                ["menu:tracked"],
                ["menu:add"],
                ["back:main"],
            ],
        )
        self.assertEqual(
            keyboards.library_menu_keyboard().inline_keyboard[0][0].text,
            "♡\u00a0Все сохранённые",
        )
        self.assertEqual(
            keyboards.library_menu_keyboard().inline_keyboard[-1][0].text,
            "⌂\u00a0Главное меню",
        )

    def test_format_buttons_have_expected_callbacks_and_back_to_library_menu(
        self,
    ) -> None:
        self.assert_callback_rows(
            keyboards.format_keyboard("add"),
            [
                ["format:add:full_length", "format:add:series"],
                ["back:library_menu"],
            ],
        )

    def test_content_type_buttons_have_expected_callbacks_and_back_to_format(
        self,
    ) -> None:
        self.assert_callback_rows(
            keyboards.content_type_keyboard("add", "series"),
            [
                ["type:add:series:movie"],
                ["type:add:series:anime"],
                ["type:add:series:cartoon"],
                ["back:format:add"],
            ],
        )

    def test_selected_type_back_returns_to_content_type_step(self) -> None:
        self.assert_callback_rows(
            keyboards.selected_type_keyboard("add", "full_length"),
            [["back:content_type:add:full_length"]],
        )

    def test_tmdb_retry_with_context_returns_to_selected_content_type(self) -> None:
        self.assert_callback_rows(
            keyboards.tmdb_retry_keyboard("add", "full_length"),
            [
                ["title:retry"],
                ["back:content_type:add:full_length"],
            ],
        )

    def test_tmdb_retry_without_context_returns_to_content_type_step(self) -> None:
        self.assert_callback_rows(
            keyboards.tmdb_retry_keyboard(),
            [
                ["title:retry"],
                ["back:content_type"],
            ],
        )
