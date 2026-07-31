from src import keyboards
from tests.support.keyboards import KeyboardTestCase


class RatingKeyboardTests(KeyboardTestCase):
    def test_rating_keyboard_has_back_button(self) -> None:
        self.assert_callback_rows(
            keyboards.rating_keyboard(),
            [
                ["rate:1", "rate:2", "rate:3", "rate:4", "rate:5"],
                ["rate:6", "rate:7", "rate:8", "rate:9", "rate:10"],
                ["rating:back"],
            ],
        )

    def test_badge_keyboard_has_four_options_none_and_back(self) -> None:
        self.assert_callback_rows(
            keyboards.badge_keyboard("rating_badge"),
            [
                ["rating_badge:cry", "rating_badge:sad"],
                ["rating_badge:top", "rating_badge:funny"],
                ["rating_badge:none"],
                ["rating_badge:back"],
            ],
        )
