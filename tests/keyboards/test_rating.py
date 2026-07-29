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
