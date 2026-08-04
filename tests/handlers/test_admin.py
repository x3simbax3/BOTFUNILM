import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from src.database.admin import (
    AdminActivity,
    AdminLibraries,
    AdminNotifications,
    AdminOverview,
    AdminPopularTitle,
)
from src.database.news_api_usage import NewsApiUsage
from src.fsm import AdminState
from src.handlers import admin as admin_handlers
from src.keyboards import admin_menu_keyboard, admin_statistics_keyboard
from tests.support.telegram import CallbackStub, MessageStub, StateStub


def statistics():
    return (
        AdminOverview(
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
        ),
        AdminActivity(
            days=30,
            dau=2,
            wau=4,
            mau=8,
            new_users=3,
            returning_users=2,
            searches=10,
            library_opens=7,
            media_added=5,
            ratings_set=4,
            progress_updates=3,
            daily=(),
            generated_at="2026-08-04 12:00:00",
        ),
        AdminLibraries(
            total_items=12,
            users_with_library=3,
            planned_items=3,
            watching_items=2,
            completed_items=5,
            on_hold_items=1,
            dropped_items=1,
            full_length_items=7,
            series_items=5,
            movie_items=6,
            anime_items=4,
            cartoon_items=2,
            rated_items=6,
            average_rating=8.5,
            tracked_series=2,
            popular_movies=(AdminPopularTitle(1, "Movie <One>", 3),),
            popular_series=(AdminPopularTitle(2, "Series & Two", 2),),
            generated_at="2026-08-04 12:00:00",
        ),
        AdminNotifications(
            news_subscribers=8,
            news_opted_out=2,
            series_subscribers=4,
            series_subscriptions=7,
            pending_series_notifications=3,
            sent_series_notifications=12,
            pending_release_notifications=2,
            sent_release_notifications=5,
            news_sent_30d=20,
            release_messages_sent_30d=6,
            selected_30d=30,
            sent_30d=26,
            failed_30d=3,
            deactivated_30d=1,
            blocked_users=2,
            last_delivery_at="2026-08-04 12:00:00",
            generated_at="2026-08-04 12:05:00",
        ),
        NewsApiUsage("2026-08-04", 7, 100, 93),
    )


class AdminFilterTests(unittest.IsolatedAsyncioTestCase):
    async def test_allows_only_configured_user(self) -> None:
        allowed = SimpleNamespace(from_user=SimpleNamespace(id=123))
        denied = SimpleNamespace(from_user=SimpleNamespace(id=999))
        admin_filter = admin_handlers.AdminFilter({123})

        self.assertTrue(await admin_filter(allowed))
        self.assertFalse(await admin_filter(denied))


class AdminHandlerTests(unittest.IsolatedAsyncioTestCase):
    async def test_admin_command_opens_minimal_menu(self) -> None:
        message = MessageStub("/admin")
        state = StateStub()

        await admin_handlers.show_admin_menu(message, state)

        self.assertTrue(state.cleared)
        self.assertEqual(message.answers[0]["reply_markup"], admin_menu_keyboard())

    async def test_statistics_are_shown_on_one_screen(self) -> None:
        message = MessageStub()
        callback = CallbackStub("admin:stats", message)

        with patch.object(
            admin_handlers,
            "_load_statistics",
            AsyncMock(return_value=statistics()),
        ):
            await admin_handlers.show_admin_statistics(callback)

        text = message.edit_text_calls[0]["text"]
        self.assertIn("Всего · <b>4</b>", text)
        self.assertIn("Отложено / брошено · 1 / 1", text)
        self.assertIn("Осталось по тарифу · <b>93 из 100</b>", text)
        self.assertEqual(
            message.edit_text_calls[0]["reply_markup"],
            admin_statistics_keyboard(),
        )

    async def test_text_broadcast_is_previewed_and_queued(self) -> None:
        message = MessageStub("Текст рассылки")
        state = StateStub()

        await admin_handlers.accept_broadcast_text(message, state)

        self.assertEqual(state.state, AdminState.confirming_broadcast)
        callback = CallbackStub("admin:broadcast:send", message)
        with patch.object(
            admin_handlers,
            "enqueue_custom_broadcast",
            AsyncMock(),
        ) as enqueue:
            await admin_handlers.send_custom_broadcast(callback, state)

        enqueue.assert_awaited_once_with(123, "Текст рассылки", photo_file_id=None)
        self.assertTrue(state.cleared)

    async def test_photo_broadcast_requires_caption(self) -> None:
        message = MessageStub()
        message.photo = [SimpleNamespace(file_id="photo-id")]
        message.caption = None
        state = StateStub()

        await admin_handlers.accept_broadcast_photo(message, state)

        self.assertIn("Подпись должна", message.answers[0]["text"])

    async def test_news_is_not_queued_after_daily_budget(self) -> None:
        callback = CallbackStub("admin:execute:news", MessageStub())
        with (
            patch.object(
                admin_handlers,
                "get_news_api_usage",
                AsyncMock(return_value=NewsApiUsage("2026-08-04", 20, 100, 80)),
            ),
            patch.object(
                admin_handlers,
                "enqueue_admin_job",
                AsyncMock(),
            ) as enqueue,
        ):
            await admin_handlers.execute_api_news(callback)

        enqueue.assert_not_awaited()
        self.assertEqual(callback.answers[0]["show_alert"], True)

    async def test_denies_unconfigured_user_command(self) -> None:
        message = MessageStub("/admin")

        await admin_handlers.deny_admin_menu(message)

        self.assertEqual(message.answers[0]["text"], "Команда недоступна.")


if __name__ == "__main__":
    unittest.main()
