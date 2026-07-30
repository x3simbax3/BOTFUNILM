from src import keyboards
from tests.support.keyboards import KeyboardTestCase


class SearchKeyboardTests(KeyboardTestCase):
    def test_tmdb_guess_buttons_have_expected_callbacks(self) -> None:
        self.assert_callback_rows(
            keyboards.tmdb_guess_keyboard(),
            [["tmdb_guess:yes", "tmdb_guess:no"]],
        )

    def test_tmdb_guess_carousel_has_navigation(self) -> None:
        keyboard = keyboards.tmdb_guess_keyboard(position=1, total=5)

        self.assert_callback_rows(
            keyboard,
            [
                [
                    "tmdb_guess:previous",
                    "tmdb_guess:position",
                    "tmdb_guess:next",
                ],
                ["tmdb_guess:yes", "tmdb_guess:no"],
            ],
        )
        self.assertEqual(keyboard.inline_keyboard[0][1].text, "2 / 5")

    def test_watch_status_buttons_have_expected_callbacks(self) -> None:
        self.assert_callback_rows(
            keyboards.watch_status_keyboard(),
            [["watch_status:completed"], ["watch_status:planned"]],
        )

    def test_unreleased_title_can_only_be_planned(self) -> None:
        self.assert_callback_rows(
            keyboards.watch_status_keyboard(allow_completed=False),
            [["watch_status:planned"]],
        )
