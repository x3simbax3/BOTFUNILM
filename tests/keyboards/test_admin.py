from src.keyboards import (
    admin_broadcast_confirmation_keyboard,
    admin_broadcast_format_keyboard,
    admin_confirmation_keyboard,
    admin_menu_keyboard,
    admin_statistics_keyboard,
)
from tests.support.keyboards import KeyboardTestCase


class AdminKeyboardTests(KeyboardTestCase):
    def test_menu_contains_only_required_sections(self) -> None:
        self.assert_callback_rows(
            admin_menu_keyboard(),
            [["admin:stats"], ["admin:broadcast"], ["admin:confirm:news"]],
        )

    def test_statistics_can_be_exported_and_refreshed(self) -> None:
        self.assert_callback_rows(
            admin_statistics_keyboard(),
            [["admin:export:users"], ["admin:stats"], ["admin:menu"]],
        )

    def test_broadcast_format_and_confirmation(self) -> None:
        self.assert_callback_rows(
            admin_broadcast_format_keyboard(),
            [
                ["admin:broadcast:text"],
                ["admin:broadcast:photo"],
                ["admin:menu"],
            ],
        )
        self.assert_callback_rows(
            admin_broadcast_confirmation_keyboard(),
            [["admin:broadcast:send"], ["admin:menu"]],
        )
        self.assertEqual(
            admin_broadcast_confirmation_keyboard().inline_keyboard[0][0].text,
            "Отправить",
        )

    def test_news_confirmation_returns_to_menu(self) -> None:
        self.assert_callback_rows(
            admin_confirmation_keyboard("news"),
            [["admin:execute:news"], ["admin:menu"]],
        )
