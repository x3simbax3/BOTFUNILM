import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from src.database.admin import (
    AdminActivity,
    AdminActivityDay,
    AdminLibraries,
    AdminNotifications,
    AdminOverview,
    AdminPopularTitle,
    AdminUserDetails,
    AdminUserPage,
    AdminUserSummary,
)
from src.handlers import admin as admin_handlers
from src.keyboards import (
    admin_activity_keyboard,
    admin_libraries_keyboard,
    admin_notifications_keyboard,
    admin_overview_keyboard,
    admin_user_keyboard,
    admin_users_keyboard,
)
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


def user_page() -> AdminUserPage:
    return AdminUserPage(
        users=(
            AdminUserSummary(
                user_id=123,
                username="viewer",
                display_name="Test Viewer",
                is_active=1,
                started_at="2026-08-01 10:00:00",
                last_activity_at="2026-08-04 12:00:00",
                library_items=2,
            ),
        ),
        page=1,
        total_pages=2,
        total_users=11,
    )


def user_details() -> AdminUserDetails:
    return AdminUserDetails(
        user_id=123,
        username="viewer&test",
        display_name="Test <Viewer>",
        is_active=1,
        news_enabled=0,
        started_at="2026-08-01 10:00:00",
        last_started_at="2026-08-02 10:00:00",
        last_activity_at="2026-08-04 12:00:00",
        library_items=2,
        planned_items=1,
        watching_items=1,
        completed_items=0,
        on_hold_items=0,
        dropped_items=0,
        rated_items=1,
        average_rating=8.0,
        tracked_series=1,
    )


def activity() -> AdminActivity:
    return AdminActivity(
        days=7,
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
        daily=(
            AdminActivityDay(
                event_date="2026-08-03",
                active_users=1,
                new_users=0,
                returning_users=1,
            ),
            AdminActivityDay(
                event_date="2026-08-04",
                active_users=2,
                new_users=1,
                returning_users=1,
            ),
        ),
        generated_at="2026-08-04 12:00:00",
    )


def libraries() -> AdminLibraries:
    return AdminLibraries(
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
    )


def notifications() -> AdminNotifications:
    return AdminNotifications(
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

    async def test_shows_users_with_profile_buttons(self) -> None:
        message = MessageStub()
        callback = CallbackStub("admin:users:1", message)

        with patch.object(
            admin_handlers,
            "get_admin_users",
            new=AsyncMock(return_value=user_page()),
        ) as get_users:
            await admin_handlers.show_admin_users(callback)

        get_users.assert_awaited_once_with(1)
        self.assertIn("Всего · <b>11</b>", message.edit_text_calls[0]["text"])
        self.assertEqual(
            message.edit_text_calls[0]["reply_markup"],
            admin_users_keyboard(
                [(123, "● Test Viewer · 2")],
                page=1,
                total_pages=2,
            ),
        )
        self.assertEqual(callback.answers, [{"text": None}])

    async def test_shows_user_card_and_escapes_profile(self) -> None:
        message = MessageStub()
        callback = CallbackStub("admin:user:123:2", message)

        with patch.object(
            admin_handlers,
            "get_admin_user",
            new=AsyncMock(return_value=user_details()),
        ) as get_user:
            await admin_handlers.show_admin_user(callback)

        get_user.assert_awaited_once_with(123)
        text = message.edit_text_calls[0]["text"]
        self.assertIn("Test &lt;Viewer&gt;", text)
        self.assertIn("@viewer&amp;test", text)
        self.assertIn("Хочу посмотреть · 1", text)
        self.assertEqual(
            message.edit_text_calls[0]["reply_markup"],
            admin_user_keyboard(2),
        )
        self.assertEqual(callback.answers, [{"text": None}])

    async def test_rejects_invalid_users_page_callback(self) -> None:
        callback = CallbackStub("admin:users:bad", MessageStub())

        await admin_handlers.show_admin_users(callback)

        self.assertEqual(
            callback.answers,
            [{"text": "Некорректная команда", "show_alert": True}],
        )

    async def test_reports_missing_user(self) -> None:
        callback = CallbackStub("admin:user:999:1", MessageStub())

        with patch.object(
            admin_handlers,
            "get_admin_user",
            new=AsyncMock(return_value=None),
        ):
            await admin_handlers.show_admin_user(callback)

        self.assertEqual(
            callback.answers,
            [{"text": "Пользователь не найден", "show_alert": True}],
        )

    async def test_shows_activity_for_selected_period(self) -> None:
        message = MessageStub()
        callback = CallbackStub("admin:activity:7", message)

        with patch.object(
            admin_handlers,
            "get_admin_activity",
            new=AsyncMock(return_value=activity()),
        ) as get_activity:
            await admin_handlers.show_admin_activity(callback)

        get_activity.assert_awaited_once_with(7)
        text = message.edit_text_calls[0]["text"]
        self.assertIn("DAU / WAU / MAU · <b>2 / 4 / 8</b>", text)
        self.assertIn("04.08 · 2 / +1 / ↩1", text)
        self.assertEqual(
            message.edit_text_calls[0]["reply_markup"],
            admin_activity_keyboard(7),
        )
        self.assertEqual(callback.answers, [{"text": None}])

    async def test_rejects_invalid_activity_period(self) -> None:
        callback = CallbackStub("admin:activity:14", MessageStub())

        await admin_handlers.show_admin_activity(callback)

        self.assertEqual(
            callback.answers,
            [{"text": "Некорректная команда", "show_alert": True}],
        )

    async def test_shows_library_statistics_and_escapes_titles(self) -> None:
        message = MessageStub()
        callback = CallbackStub("admin:libraries", message)

        with patch.object(
            admin_handlers,
            "get_admin_libraries",
            new=AsyncMock(return_value=libraries()),
        ) as get_libraries:
            await admin_handlers.show_admin_libraries(callback)

        get_libraries.assert_awaited_once_with()
        text = message.edit_text_calls[0]["text"]
        self.assertIn("Всего записей · <b>12</b>", text)
        self.assertIn("Movie &lt;One&gt; · 3", text)
        self.assertIn("Series &amp; Two · 2", text)
        self.assertEqual(
            message.edit_text_calls[0]["reply_markup"],
            admin_libraries_keyboard(),
        )
        self.assertEqual(callback.answers, [{"text": None}])

    async def test_shows_notification_statistics(self) -> None:
        message = MessageStub()
        callback = CallbackStub("admin:notifications", message)

        with patch.object(
            admin_handlers,
            "get_admin_notifications",
            new=AsyncMock(return_value=notifications()),
        ) as get_notifications:
            await admin_handlers.show_admin_notifications(callback)

        get_notifications.assert_awaited_once_with()
        text = message.edit_text_calls[0]["text"]
        self.assertIn("Получают новости · 8", text)
        self.assertIn("Доставлено · 26 (86.7%)", text)
        self.assertIn("Ошибки Telegram · 3", text)
        self.assertIn("Заблокировали бота · 2", text)
        self.assertEqual(
            message.edit_text_calls[0]["reply_markup"],
            admin_notifications_keyboard(),
        )
        self.assertEqual(callback.answers, [{"text": None}])

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
