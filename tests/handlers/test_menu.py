import unittest
from unittest.mock import AsyncMock, patch

from src.fsm import MenuState
from src.handlers import menu as menu_handlers
from src.keyboards import (
    content_type_keyboard,
    format_keyboard,
    main_menu_keyboard,
    selected_type_keyboard,
)
from src.lang import START_TEXT, action_text, content_type_text, selected_type_text
from tests.support.telegram import CallbackStub, MessageStub, StateStub


class MenuHandlerTests(unittest.IsolatedAsyncioTestCase):
    async def test_start_clears_state_sets_choosing_action_and_sends_menu(self) -> None:
        message = MessageStub()
        state = StateStub({"action": "add"})

        with patch.object(
            menu_handlers,
            "register_bot_user",
            new=AsyncMock(),
        ) as register_user:
            await menu_handlers.start(message, state)

        register_user.assert_awaited_once_with(123)

        self.assertTrue(state.cleared)
        self.assertEqual(state.data, {})
        self.assertEqual(state.state, MenuState.choosing_action)
        self.assertEqual(
            message.answers,
            [
                {
                    "text": START_TEXT,
                    "parse_mode": "HTML",
                    "reply_markup": main_menu_keyboard(),
                    "stub": message.answers[0]["stub"],
                }
            ],
        )

    async def test_choose_action_saves_action_and_moves_to_choosing_format(
        self,
    ) -> None:
        message = MessageStub()
        callback = CallbackStub("menu:add", message)
        state = StateStub()

        await menu_handlers.choose_action(callback, state)

        self.assertEqual(state.data, {"action": "add"})
        self.assertEqual(state.state, MenuState.choosing_format)
        self.assertEqual(
            message.edit_text_calls,
            [
                {
                    "text": action_text("add"),
                    "parse_mode": "HTML",
                    "reply_markup": format_keyboard("add"),
                }
            ],
        )
        self.assertEqual(callback.answers, [{"text": None}])

    async def test_choose_format_saves_format_and_moves_to_choosing_content_type(
        self,
    ) -> None:
        message = MessageStub()
        callback = CallbackStub("format:add:series", message)
        state = StateStub()

        await menu_handlers.choose_format(callback, state)

        self.assertEqual(state.data, {"action": "add", "content_format": "series"})
        self.assertEqual(state.state, MenuState.choosing_content_type)
        self.assertEqual(
            message.edit_text_calls,
            [
                {
                    "text": content_type_text("add", "series"),
                    "parse_mode": "HTML",
                    "reply_markup": content_type_keyboard("add", "series"),
                }
            ],
        )
        self.assertEqual(callback.answers, [{"text": None}])

    async def test_choose_content_type_saves_type_and_moves_to_waiting_title(
        self,
    ) -> None:
        message = MessageStub()
        callback = CallbackStub("type:add:series:anime", message)
        state = StateStub()

        await menu_handlers.choose_content_type(callback, state)

        self.assertEqual(
            state.data,
            {
                "action": "add",
                "content_format": "series",
                "content_type": "anime",
            },
        )
        self.assertEqual(state.state, MenuState.waiting_title)
        self.assertEqual(
            message.edit_text_calls,
            [
                {
                    "text": selected_type_text("add", "series", "anime"),
                    "parse_mode": "HTML",
                    "reply_markup": selected_type_keyboard("add", "series"),
                }
            ],
        )
        self.assertEqual(callback.answers, [{"text": "Выбор сохранен"}])

    async def test_back_to_main_clears_all_scenario_data(self) -> None:
        message = MessageStub()
        callback = CallbackStub("back:main", message)
        state = StateStub(
            {
                "action": "add",
                "content_format": "series",
                "content_type": "anime",
                "media_id": 7,
                "tmdb_id": 42,
                "tmdb_title": "Сериал",
                "ratings": {"story": 9},
                "seasons_data": [{"season_number": 1, "episode_count": 12}],
                "watched_by_season": {1: 4},
            }
        )

        await menu_handlers.go_back(callback, state)

        self.assertEqual(state.data, {})
        self.assertEqual(state.state, MenuState.choosing_action)
        self.assertEqual(message.edit_text_calls[0]["text"], START_TEXT)
        self.assertEqual(
            message.edit_text_calls[0]["reply_markup"],
            main_menu_keyboard(),
        )
        self.assertEqual(callback.answers, [{"text": None}])

    async def test_retry_title_moves_back_to_waiting_title(self) -> None:
        message = MessageStub()
        callback = CallbackStub("title:retry", message)
        state = StateStub()

        await menu_handlers.retry_title(callback, state)

        self.assertEqual(state.state, MenuState.waiting_title)
        self.assertEqual(
            message.edit_text_calls,
            [
                {
                    "text": "Введи название ещё раз.",
                    "parse_mode": None,
                    "reply_markup": None,
                }
            ],
        )
        self.assertEqual(callback.answers, [{"text": None}])
