from src.keyboards import (
    admin_activity_keyboard,
    admin_libraries_keyboard,
    admin_notifications_keyboard,
    admin_overview_keyboard,
    admin_user_keyboard,
    admin_users_keyboard,
)
from tests.support.keyboards import KeyboardTestCase


class AdminKeyboardTests(KeyboardTestCase):
    def test_overview_has_refresh_button(self) -> None:
        self.assert_callback_rows(
            admin_overview_keyboard(),
            [
                ["admin:users:1"],
                ["admin:activity:7"],
                ["admin:libraries"],
                ["admin:notifications"],
                ["admin:system", "admin:manage"],
                ["admin:overview"],
            ],
        )

    def test_users_have_profile_pagination_and_overview_buttons(self) -> None:
        keyboard = admin_users_keyboard(
            [(123, "● User · 2"), (456, "○ Other · 0")],
            page=2,
            total_pages=3,
        )

        self.assert_callback_rows(
            keyboard,
            [
                ["admin:user:123:2"],
                ["admin:user:456:2"],
                ["admin:users:1", "admin:users:2", "admin:users:3"],
                ["admin:overview"],
            ],
        )

    def test_user_card_returns_to_source_page(self) -> None:
        self.assert_callback_rows(
            admin_user_keyboard(3),
            [["admin:users:3"], ["admin:overview"]],
        )

    def test_activity_switches_period_and_returns_to_overview(self) -> None:
        self.assert_callback_rows(
            admin_activity_keyboard(7),
            [
                ["admin:activity:7", "admin:activity:30"],
                ["admin:overview"],
            ],
        )
        self.assertIn("✓", admin_activity_keyboard(7).inline_keyboard[0][0].text)

    def test_libraries_refresh_and_return_to_overview(self) -> None:
        self.assert_callback_rows(
            admin_libraries_keyboard(),
            [["admin:libraries"], ["admin:overview"]],
        )

    def test_notifications_refresh_and_return_to_overview(self) -> None:
        self.assert_callback_rows(
            admin_notifications_keyboard(),
            [["admin:notifications"], ["admin:overview"]],
        )
