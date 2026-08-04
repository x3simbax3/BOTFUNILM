from src.keyboards import admin_overview_keyboard
from tests.support.keyboards import KeyboardTestCase


class AdminKeyboardTests(KeyboardTestCase):
    def test_overview_has_refresh_button(self) -> None:
        self.assert_callback_rows(
            admin_overview_keyboard(),
            [["admin:overview"]],
        )
