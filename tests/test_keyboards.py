import unittest

from aiogram.types import InlineKeyboardMarkup

from src import keyboards


def callback_rows(markup: InlineKeyboardMarkup) -> list[list[str]]:
    return [
        [button.callback_data for button in row]
        for row in markup.inline_keyboard
    ]


class KeyboardsTests(unittest.TestCase):
    def test_main_menu_buttons_have_expected_callbacks(self) -> None:
        self.assertEqual(
            callback_rows(keyboards.main_menu_keyboard()),
            [["menu:library", "menu:add"]],
        )

    def test_format_buttons_have_expected_callbacks_and_back_to_main(self) -> None:
        self.assertEqual(
            callback_rows(keyboards.format_keyboard("add")),
            [
                ["format:add:full_length", "format:add:series"],
                ["back:main"],
            ],
        )

    def test_content_type_buttons_have_expected_callbacks_and_back_to_format(self) -> None:
        self.assertEqual(
            callback_rows(keyboards.content_type_keyboard("add", "series")),
            [
                ["type:add:series:movie"],
                ["type:add:series:anime"],
                ["type:add:series:cartoon"],
                ["back:format:add"],
            ],
        )

    def test_selected_type_back_returns_to_content_type_step(self) -> None:
        self.assertEqual(
            callback_rows(keyboards.selected_type_keyboard("add", "full_length")),
            [["back:content_type:add:full_length"]],
        )

    def test_tmdb_guess_buttons_have_expected_callbacks(self) -> None:
        self.assertEqual(
            callback_rows(keyboards.tmdb_guess_keyboard()),
            [["tmdb_guess:yes", "tmdb_guess:no"]],
        )

    def test_tmdb_retry_with_context_returns_to_selected_content_type(self) -> None:
        self.assertEqual(
            callback_rows(keyboards.tmdb_retry_keyboard("add", "full_length")),
            [
                ["title:retry"],
                ["back:content_type:add:full_length"],
            ],
        )

    def test_tmdb_retry_without_context_returns_to_content_type_step(self) -> None:
        self.assertEqual(
            callback_rows(keyboards.tmdb_retry_keyboard()),
            [
                ["title:retry"],
                ["back:content_type"],
            ],
        )


if __name__ == "__main__":
    unittest.main()
