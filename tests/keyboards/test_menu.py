from src import keyboards
from tests.support.keyboards import KeyboardTestCase


class MenuKeyboardTests(KeyboardTestCase):
    def test_main_menu_buttons_have_expected_callbacks(self) -> None:
        keyboard = keyboards.main_menu_keyboard()
        self.assert_callback_rows(
            keyboard,
            [["menu:library"], ["menu:add"], ["menu:tracked"]],
        )
        self.assertEqual(keyboard.inline_keyboard[2][0].text, "◉\u00a0Отслеживаемые")

    def test_format_buttons_have_expected_callbacks_and_back_to_main(self) -> None:
        self.assert_callback_rows(
            keyboards.format_keyboard("add"),
            [
                ["format:add:full_length", "format:add:series"],
                ["back:main"],
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
