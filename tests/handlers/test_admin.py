import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from src.database.admin import AdminOverview
from src.handlers import admin as admin_handlers
from src.keyboards import admin_overview_keyboard
from tests.support.telegram import CallbackStub, MessageStub


def overview() -> AdminOverview:
    return AdminOverview(
        total_users=4,
        active_users=3,
        inactive_users=1,
        new_24h=1,
        new_7d=2,
        new_30d=4,
        active_24h=2,
        active_7d=3,
        active_30d=4,
        activated_users=2,
        library_items=9,
        rated_items=5,
        tracked_series=2,
        news_users=3,
        generated_at="2026-08-04 12:00:00",
    )


class AdminFilterTests(unittest.IsolatedAsyncioTestCase):
    async def test_allows_configured_user(self) -> None:
        event = SimpleNamespace(from_user=SimpleNamespace(id=123))

        self.assertTrue(await admin_handlers.AdminFilter({123, 456})(event))

    async def test_rejects_other_user(self) -> None:
        event = SimpleNamespace(from_user=SimpleNamespace(id=999))

        self.assertFalse(await admin_handlers.AdminFilter({123, 456})(event))


class AdminHandlerTests(unittest.IsolatedAsyncioTestCase):
    async def test_show_overview_sends_statistics(self) -> None:
        message = MessageStub("/admin")

        with patch.object(
            admin_handlers,
            "get_admin_overview",
            new=AsyncMock(return_value=overview()),
        ):
            await admin_handlers.show_admin_overview(message)

        self.assertIn("Всего · <b>4</b>", message.answers[0]["text"])
        self.assertIn("2 (50.0%)", message.answers[0]["text"])
        self.assertEqual(message.answers[0]["parse_mode"], "HTML")
        self.assertEqual(
            message.answers[0]["reply_markup"],
            admin_overview_keyboard(),
        )

    async def test_refresh_edits_existing_message(self) -> None:
        message = MessageStub()
        callback = CallbackStub("admin:overview", message)

        with patch.object(
            admin_handlers,
            "get_admin_overview",
            new=AsyncMock(return_value=overview()),
        ):
            await admin_handlers.refresh_admin_overview(callback)

        self.assertIn("Всего · <b>4</b>", message.edit_text_calls[0]["text"])
        self.assertEqual(callback.answers, [{"text": "Обновлено"}])

    async def test_denies_unconfigured_user_command(self) -> None:
        message = MessageStub("/admin")

        await admin_handlers.deny_admin_overview(message)

        self.assertEqual(message.answers[0]["text"], "Команда недоступна.")

    async def test_denies_forged_admin_callback(self) -> None:
        callback = CallbackStub("admin:overview", MessageStub())

        await admin_handlers.deny_admin_callback(callback)

        self.assertEqual(
            callback.answers,
            [{"text": "Недостаточно прав", "show_alert": True}],
        )


if __name__ == "__main__":
    unittest.main()
