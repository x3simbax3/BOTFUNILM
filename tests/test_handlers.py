import json
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from src.fsm import MenuState
from src.handlers import library as library_handlers
from src.handlers import menu as menu_handlers
from src.handlers import rating as rating_handlers
from src.handlers import search as search_handlers
from src.handlers import series as series_handlers
from src.keyboards import (
    content_type_keyboard,
    format_keyboard,
    main_menu_keyboard,
    selected_type_keyboard,
)
from src.lang import (
    START_TEXT,
    TMDB_SEARCHING,
    TMDB_TOO_LONG,
    action_text,
    content_type_text,
    selected_type_text,
)
from src.services import media as media_service
from src.tmdb import (
    TMDB_IMAGE_URL,
    TmdbAuthenticationError,
    TmdbEpisodeAirInfo,
    TmdbError,
    TmdbNotConfiguredError,
    TmdbNotFoundError,
    TmdbRateLimitError,
    TmdbSeasonInfo,
    TmdbTitle,
    TmdbTvDetails,
    TmdbUnavailableError,
)


class StateStub:
    def __init__(self, data: dict | None = None) -> None:
        self.data = data or {}
        self.state = None
        self.cleared = False

    async def clear(self) -> None:
        self.data.clear()
        self.state = None
        self.cleared = True

    async def set_state(self, state) -> None:
        self.state = state

    async def get_data(self) -> dict:
        return self.data

    async def set_data(self, data: dict) -> None:
        self.data = data

    async def update_data(self, **kwargs) -> None:
        self.data.update(kwargs)


class SentMessageStub:
    def __init__(self, message_id: int) -> None:
        self.message_id = message_id
        self.last_text = None

    async def edit_text(self, text: str, **kwargs) -> None:
        self.last_text = text


class MessageStub:
    def __init__(self, text: str | None = "Title", message_id: int = 10) -> None:
        self.text = text
        self.message_id = message_id
        self.answers = []
        self.photo_answers = []
        self.edit_text_calls = []
        self.photo = []
        self.deleted = False
        self.from_user = SimpleNamespace(id=123)
        self.chat = SimpleNamespace(id=123)
        self.bot = SimpleNamespace(delete_message=AsyncMock())

    async def answer(self, text: str, **kwargs) -> SentMessageStub:
        stub = SentMessageStub(100 + len(self.answers) + len(self.photo_answers))
        self.answers.append({"text": text, "stub": stub, **kwargs})
        return stub

    async def answer_photo(self, photo: str, **kwargs) -> SentMessageStub:
        stub = SentMessageStub(200 + len(self.answers) + len(self.photo_answers))
        self.photo_answers.append({"photo": photo, "stub": stub, **kwargs})
        return stub

    async def edit_text(self, text: str, **kwargs) -> None:
        self.edit_text_calls.append({"text": text, **kwargs})

    async def delete(self) -> None:
        self.deleted = True


class CallbackStub:
    def __init__(
        self,
        data: str | None,
        message: MessageStub | None = None,
    ) -> None:
        self.data = data
        self.message = message
        self.from_user = SimpleNamespace(id=123)
        self.bot = SimpleNamespace(
            me=AsyncMock(return_value=SimpleNamespace(username="BotFunilmBot"))
        )
        self.answers = []

    async def answer(self, text: str | None = None, **kwargs) -> None:
        self.answers.append({"text": text, **kwargs})


class MenuHandlerTests(unittest.IsolatedAsyncioTestCase):
    async def test_start_clears_state_sets_choosing_action_and_sends_menu(self) -> None:
        message = MessageStub()
        state = StateStub({"action": "add"})

        await menu_handlers.start(message, state)

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

    async def test_start_deep_link_opens_owned_library_item(self) -> None:
        message = MessageStub(text="/start media_7")
        state = StateStub({"library_message_id": 55})
        item = {
            "id": 7,
            "title": "Матрица",
            "original_title": "The Matrix",
            "description": "Описание",
            "poster_path": None,
            "content_format": "full_length",
            "content_type": "movie",
            "user_status": "completed",
            "user_rating": 9,
            "rating": 8.2,
            "release_date": "1999-03-31",
            "first_air_date": None,
            "number_of_seasons": None,
            "number_of_episodes": None,
            "episodes_watched": None,
            "library_users_count": 3,
        }

        with patch.object(
            library_handlers,
            "get_user_library_item",
            AsyncMock(return_value=item),
        ):
            await menu_handlers.start(message, state)

        self.assertEqual(state.state, MenuState.viewing_media)
        self.assertIn("Матрица", message.answers[0]["text"])
        self.assertIn("Описание", message.answers[0]["text"])
        message.bot.delete_message.assert_awaited_once_with(
            chat_id=123,
            message_id=55,
        )

    async def test_opening_old_item_repairs_missing_poster_and_tmdb_rating(
        self,
    ) -> None:
        message = MessageStub()
        state = StateStub()
        item = {
            "id": 7,
            "tmdb_id": 42,
            "title": "Матрица",
            "original_title": "The Matrix",
            "description": "Описание",
            "poster_path": None,
            "content_format": "full_length",
            "content_type": "movie",
            "user_status": "completed",
            "user_rating": 9,
            "rating": None,
            "release_date": "1999-03-31",
            "first_air_date": None,
            "number_of_seasons": None,
            "number_of_episodes": None,
            "episodes_watched": None,
            "library_users_count": 3,
        }
        details = TmdbTitle(
            "Матрица",
            "Описание",
            f"{TMDB_IMAGE_URL}/poster.jpg",
            "",
            "",
            42,
            "/poster.jpg",
            8.7,
        )

        with (
            patch.object(
                library_handlers,
                "get_user_library_item",
                AsyncMock(return_value=item),
            ),
            patch.object(
                library_handlers,
                "fetch_title_details",
                AsyncMock(return_value=details),
            ),
            patch.object(
                library_handlers,
                "update_media_metadata",
                AsyncMock(),
            ) as update_metadata,
        ):
            await library_handlers.show_library_item(message, state, 123, 7)

        update_metadata.assert_awaited_once_with(
            7,
            poster_path="/poster.jpg",
            rating=8.7,
        )
        self.assertEqual(
            message.photo_answers[0]["photo"],
            f"{TMDB_IMAGE_URL}/poster.jpg",
        )
        self.assertIn("TMDB · <b>8.7/10</b>", message.photo_answers[0]["caption"])

    async def test_opening_active_series_uses_cached_release_info(
        self,
    ) -> None:
        message = MessageStub()
        state = StateStub()
        item = {
            "id": 8,
            "tmdb_id": 84,
            "title": "Сериал",
            "original_title": None,
            "description": "Описание",
            "poster_path": "/poster.jpg",
            "content_format": "series",
            "content_type": "movie",
            "user_status": "watching",
            "user_rating": None,
            "rating": 8.0,
            "release_date": None,
            "first_air_date": "2025-01-01",
            "number_of_seasons": 1,
            "number_of_episodes": 8,
            "episodes_watched": 4,
            "library_users_count": 5,
            "tmdb_status": "Returning Series",
            "tmdb_in_production": 1,
            "next_episode_air_date": "2026-08-01",
            "next_episode_season_number": 1,
            "next_episode_number": 8,
        }
        with (
            patch.object(
                library_handlers,
                "get_user_library_item",
                AsyncMock(return_value=item),
            ),
            patch.object(
                library_handlers,
                "fetch_title_details",
                AsyncMock(),
            ) as fetch_metadata,
        ):
            await library_handlers.show_library_item(message, state, 123, 8)

        fetch_metadata.assert_not_awaited()
        self.assertIn(
            "Следующая серия · <b>1 сезон, 8 серия · 01.08.2026</b>",
            message.photo_answers[0]["caption"],
        )

    async def test_opening_ended_series_does_not_refresh_release_info(self) -> None:
        item = {
            "id": 8,
            "content_format": "series",
            "tmdb_id": 84,
            "poster_path": None,
            "rating": None,
            "tmdb_status": "Ended",
            "tmdb_in_production": 0,
        }

        with (
            patch.object(
                library_handlers,
                "fetch_title_details",
                AsyncMock(),
            ) as fetch_metadata,
        ):
            await library_handlers._refresh_item_metadata(item)

        fetch_metadata.assert_not_awaited()

    async def test_open_library_shows_only_first_ten_and_more_button(self) -> None:
        message = MessageStub()
        callback = CallbackStub("menu:library", message)
        state = StateStub()
        filters = {
            "full_length": True,
            "series": True,
            "movie": True,
            "anime": True,
            "cartoon": True,
            "completed": True,
            "planned": True,
        }
        items = [
            {
                "id": index,
                "title": f"Title {index}",
                "content_format": "full_length",
            }
            for index in range(1, 12)
        ]

        with (
            patch.object(
                library_handlers,
                "get_user_library_filters",
                AsyncMock(return_value=filters),
            ),
            patch.object(
                library_handlers,
                "list_user_library",
                AsyncMock(return_value=items),
            ),
        ):
            await library_handlers.open_library(callback, state)

        rendered = message.edit_text_calls[0]
        self.assertIn("1.", rendered["text"])
        self.assertIn("10.", rendered["text"])
        self.assertNotIn("Title 11", rendered["text"])
        self.assertTrue(rendered["link_preview_options"].is_disabled)
        callbacks = [
            button.callback_data
            for row in rendered["reply_markup"].inline_keyboard
            for button in row
        ]
        self.assertIn("library:page:1", callbacks)
        self.assertEqual(state.data["library_sort"], "recent")
        self.assertEqual(state.data["library_message_id"], 10)
        self.assertEqual(state.state, MenuState.viewing_library)

    async def test_sort_buttons_select_rating_and_recent_order(self) -> None:
        rating_callback = CallbackStub("library:sort:rating", MessageStub())
        recent_callback = CallbackStub("library:sort:recent", MessageStub())
        state = StateStub({"library_sort": "recent"})

        with patch.object(
            library_handlers,
            "open_library_page",
            AsyncMock(),
        ) as open_page:
            await library_handlers.change_library_sort(rating_callback, state)
            self.assertEqual(state.data["library_sort"], "rating")

            await library_handlers.change_library_sort(recent_callback, state)
            self.assertEqual(state.data["library_sort"], "recent")

        self.assertEqual(open_page.await_count, 2)

    async def test_library_filter_group_opens_and_returns_to_compact_menu(
        self,
    ) -> None:
        state = StateStub({"library_page": 2})
        category = CallbackStub("library:filters:category", MessageStub())
        back = CallbackStub("library:filters:back", MessageStub())

        with patch.object(
            library_handlers,
            "open_library_page",
            AsyncMock(),
        ) as open_page:
            await library_handlers.open_library_filter_group(category, state)
            self.assertEqual(state.data["library_filter_group"], "category")
            await library_handlers.open_library_filter_group(back, state)

        self.assertIsNone(state.data["library_filter_group"])
        self.assertEqual(open_page.await_count, 2)
        open_page.assert_awaited_with(back, state, 2)

    async def test_clicking_selected_sort_keeps_its_selection(self) -> None:
        callback = CallbackStub("library:sort:rating", MessageStub())
        state = StateStub({"library_sort": "rating"})

        with patch.object(
            library_handlers,
            "open_library_page",
            AsyncMock(),
        ) as open_page:
            await library_handlers.change_library_sort(callback, state)

        self.assertEqual(state.data["library_sort"], "rating")
        open_page.assert_awaited_once_with(callback, state, 0)

    async def test_reset_filters_restores_recent_sort(self) -> None:
        callback = CallbackStub("library:filter:all", MessageStub())
        state = StateStub({"library_sort": "rating"})

        with (
            patch.object(
                library_handlers,
                "update_user_library_filter",
                AsyncMock(),
            ) as update_filter,
            patch.object(
                library_handlers,
                "open_library_page",
                AsyncMock(),
            ) as open_page,
        ):
            await library_handlers.change_library_filter(callback, state)

        update_filter.assert_awaited_once_with(123, "all")
        self.assertEqual(state.data["library_sort"], "recent")
        open_page.assert_awaited_once_with(callback, state, 0)

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


class SearchTitleHandlerTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        patcher = patch.object(
            search_handlers,
            "find_media_by_title",
            AsyncMock(return_value=None),
        )
        self.local_search = patcher.start()
        self.addCleanup(patcher.stop)
        poster_patcher = patch.object(
            search_handlers,
            "download_poster",
            AsyncMock(return_value=None),
        )
        self.poster_download = poster_patcher.start()
        self.addCleanup(poster_patcher.stop)

    async def test_search_title_without_text_asks_for_text(self) -> None:
        message = MessageStub(text=None)
        state = StateStub({"content_format": "full_length"})

        await search_handlers.search_title(message, state)

        self.assertEqual(message.answers[0]["text"], "Введи название текстом.")

    async def test_search_title_with_empty_text_rejects_title(self) -> None:
        message = MessageStub(text="   ")
        state = StateStub({"content_format": "full_length"})

        await search_handlers.search_title(message, state)

        self.assertEqual(
            message.answers[0]["text"],
            "Название не может быть пустым. Введи название ещё раз.",
        )

    async def test_search_title_without_content_format_asks_to_restart(self) -> None:
        message = MessageStub(text="Матрица")
        state = StateStub()

        await search_handlers.search_title(message, state)

        self.assertEqual(
            message.answers[0]["text"],
            "Не найден выбранный формат. Начни заново через /start.",
        )

    async def test_search_title_too_long_rejects(self) -> None:
        message = MessageStub(text="x" * 343)
        state = StateStub({"content_format": "full_length"})

        await search_handlers.search_title(message, state)

        self.assertEqual(message.answers[0]["text"], TMDB_TOO_LONG)

    async def test_search_title_found_with_poster_sends_photo_guess(self) -> None:
        message = MessageStub(text="Матрица")
        state = StateStub({"content_format": "full_length"})
        guess = TmdbTitle(
            "Матрица", "Описание", "https://image.test/poster.jpg", "Матрица", "Матрица"
        )

        with patch.object(
            search_handlers,
            "find_title_candidates",
            AsyncMock(return_value=[guess]),
        ):
            await search_handlers.search_title(message, state)

        self.assertEqual(message.answers[0]["text"], TMDB_SEARCHING)
        self.assertEqual(message.photo_answers[0]["photo"], guess.poster_url)
        self.assertIn("Матрица", message.photo_answers[0]["caption"])
        self.assertEqual(message.photo_answers[0]["parse_mode"], "HTML")
        self.assertEqual(state.data["tmdb_guess_message_id"], 201)
        self.assertEqual(state.state, MenuState.confirming_tmdb_guess)

    async def test_search_title_found_without_poster_sends_text_guess(self) -> None:
        message = MessageStub(text="Матрица")
        state = StateStub({"content_format": "full_length"})
        guess = TmdbTitle("Матрица", None, None, "Матрица", "Матрица")

        with patch.object(
            search_handlers,
            "find_title_candidates",
            AsyncMock(return_value=[guess]),
        ):
            await search_handlers.search_title(message, state)

        self.assertEqual(message.answers[0]["text"], TMDB_SEARCHING)
        status_stub = message.answers[0]["stub"]
        self.assertIn("Матрица", status_stub.last_text)
        self.assertEqual(state.data["tmdb_guess_message_id"], 101)
        self.assertEqual(state.state, MenuState.confirming_tmdb_guess)

    async def test_search_title_reuses_matching_local_media(self) -> None:
        message = MessageStub(text="матрица")
        state = StateStub({"content_format": "full_length", "content_type": "movie"})
        self.local_search.return_value = {
            "id": 7,
            "tmdb_id": 42,
            "title": "Матрица",
            "original_title": "The Matrix",
            "description": "Описание",
            "poster_path": "/poster.jpg",
            "rating": 8.2,
            "first_air_date": None,
            "release_date": "1999-03-31",
        }
        guess = TmdbTitle(
            "Матрица",
            "Описание",
            "https://image.test/poster.jpg",
            "матрица",
            "матрица",
            42,
        )

        with patch.object(
            search_handlers,
            "find_title_candidates",
            AsyncMock(return_value=[guess]),
        ) as tmdb_search:
            await search_handlers.search_title(message, state)

        tmdb_search.assert_not_awaited()
        self.assertEqual(state.data["media_id"], 7)
        self.assertEqual(state.data["tmdb_id"], 42)
        self.assertEqual(state.data["tmdb_rating"], 8.2)
        self.assertEqual(
            message.photo_answers[0]["photo"],
            f"{TMDB_IMAGE_URL}/poster.jpg",
        )

    async def test_search_title_falls_back_to_tmdb(self) -> None:
        message = MessageStub(text="Матрица")
        state = StateStub({"content_format": "full_length"})
        guess = TmdbTitle("Матрица", None, None, "Матрица", "Матрица", 42)

        with patch.object(
            search_handlers,
            "find_title_candidates",
            AsyncMock(return_value=[guess]),
        ) as tmdb_search:
            await search_handlers.search_title(message, state)

        self.local_search.assert_awaited_once_with(
            "Матрица",
            "full_length",
            "movie",
        )
        tmdb_search.assert_awaited_once_with(
            "Матрица",
            "full_length",
            "movie",
            limit=5,
        )
        self.assertIsNone(state.data["media_id"])

    async def test_search_title_handles_tmdb_not_configured(self) -> None:
        await self._assert_tmdb_error_answer(
            TmdbNotConfiguredError,
            "TMDB_API не настроен. Добавь ключ в config/.env.",
        )

    async def test_search_title_handles_tmdb_not_found(self) -> None:
        message = MessageStub(text="Матрица")
        state = StateStub({"content_format": "full_length"})

        with patch.object(
            search_handlers,
            "find_title_candidates",
            AsyncMock(side_effect=TmdbNotFoundError),
        ):
            await search_handlers.search_title(message, state)

        self.assertEqual(message.answers[0]["text"], TMDB_SEARCHING)
        status_stub = message.answers[0]["stub"]
        self.assertIn("Матрица", status_stub.last_text)

    async def test_search_title_handles_common_tmdb_error(self) -> None:
        await self._assert_tmdb_error_answer(
            TmdbError,
            "Не удалось получить ответ от TMDB. Попробуй позже.",
        )

    async def test_search_title_explains_tmdb_errors(self) -> None:
        cases = (
            (
                TmdbAuthenticationError,
                "TMDB отклонил ключ доступа. Проверь настройку TMDB_API.",
            ),
            (
                TmdbRateLimitError,
                "TMDB временно ограничил запросы. Попробуй через минуту.",
            ),
            (
                TmdbUnavailableError,
                "TMDB сейчас недоступен. Попробуй немного позже.",
            ),
        )

        for error_type, text in cases:
            with self.subTest(error=error_type.__name__):
                await self._assert_tmdb_error_answer(error_type, text)

    async def _assert_tmdb_error_answer(
        self,
        error_class: type[Exception],
        expected_text: str,
    ) -> None:
        message = MessageStub(text="Матрица")
        state = StateStub({"content_format": "full_length"})

        with patch.object(
            search_handlers,
            "find_title_candidates",
            AsyncMock(side_effect=error_class),
        ):
            await search_handlers.search_title(message, state)

        self.assertEqual(message.answers[0]["text"], TMDB_SEARCHING)
        status_stub = message.answers[0]["stub"]
        self.assertEqual(status_stub.last_text, expected_text)


class TmdbRejectRetryHandlerTests(unittest.IsolatedAsyncioTestCase):
    async def test_confirm_guess_asks_for_watch_status(self) -> None:
        message = MessageStub(message_id=100)
        callback = CallbackStub("tmdb_guess:yes", message)
        state = StateStub(
            {
                "tmdb_guess_message_id": 100,
                "tmdb_title": "Сериал",
                "content_format": "series",
                "content_type": "movie",
            }
        )

        await search_handlers.confirm_tmdb_guess(callback, state)

        self.assertEqual(state.state, MenuState.choosing_watch_status)
        self.assertIsNone(state.data["tmdb_guess_message_id"])
        self.assertTrue(message.deleted)
        status_keyboard = message.answers[0]["reply_markup"]
        self.assertEqual(
            [
                button.callback_data
                for row in status_keyboard.inline_keyboard
                for button in row
            ],
            ["watch_status:completed", "watch_status:planned"],
        )

    async def test_confirm_guess_keeps_stale_button_fallback_if_delete_fails(
        self,
    ) -> None:
        message = MessageStub(message_id=100)
        callback = CallbackStub("tmdb_guess:yes", message)
        state = StateStub({"tmdb_guess_message_id": 100})

        with patch.object(
            search_handlers,
            "delete_message_safely",
            AsyncMock(return_value=False),
        ):
            await search_handlers.confirm_tmdb_guess(callback, state)

        self.assertIsNone(state.data["tmdb_guess_message_id"])
        self.assertEqual(state.state, MenuState.choosing_watch_status)

    async def test_confirm_guess_shows_alert_for_existing_library_item(self) -> None:
        message = MessageStub(message_id=100)
        callback = CallbackStub("tmdb_guess:yes", message)
        state = StateStub(
            {
                "tmdb_guess_message_id": 100,
                "media_id": 7,
                "tmdb_title": "Уже добавлено",
                "content_format": "full_length",
                "content_type": "movie",
            }
        )

        with patch.object(
            search_handlers,
            "_already_in_library",
            AsyncMock(return_value=True),
        ):
            await search_handlers.confirm_tmdb_guess(callback, state)

        self.assertEqual(
            callback.answers,
            [{"text": "Уже добавлено в библиотеку", "show_alert": True}],
        )
        self.assertEqual(state.state, None)
        self.assertFalse(message.deleted)

    async def test_planned_status_saves_without_rating(self) -> None:
        message = MessageStub()
        callback = CallbackStub("watch_status:planned", message)
        state = StateStub(
            {
                "tmdb_id": 42,
                "tmdb_title": "На потом",
                "content_format": "series",
                "content_type": "anime",
            }
        )
        details = TmdbTvDetails(
            number_of_seasons=1,
            number_of_episodes=12,
            seasons=[TmdbSeasonInfo(1, "Сезон 1", 12, 4)],
            status="Returning Series",
            in_production=True,
            next_episode_to_air=TmdbEpisodeAirInfo(1, 5, "2026-08-01"),
        )

        with (
            patch.object(
                media_service,
                "upsert_media",
                AsyncMock(return_value=7),
            ),
            patch.object(
                search_handlers,
                "save_user_media",
                AsyncMock(),
            ) as save,
            patch.object(
                search_handlers,
                "fetch_tv_details",
                AsyncMock(return_value=details),
            ),
            patch.object(
                search_handlers,
                "update_media_series_release_info",
                AsyncMock(),
            ) as update_release,
        ):
            await search_handlers.choose_watch_status(callback, state)

        save.assert_awaited_once_with(user_id=123, media_id=7, status="planned")
        update_release.assert_awaited_once_with(
            7,
            user_id=123,
            status="Returning Series",
            in_production=True,
            number_of_seasons=1,
            number_of_episodes=12,
            available_episode_count=4,
            seasons=[
                {
                    "season_number": 1,
                    "name": "Сезон 1",
                    "announced_episode_count": 12,
                    "episode_count": 4,
                }
            ],
            poster_path=None,
            rating=None,
            next_episode_air_date="2026-08-01",
            next_episode_season_number=1,
            next_episode_number=5,
        )
        self.assertEqual(state.state, MenuState.choosing_action)
        self.assertNotIn("ratings", state.data)

    async def test_completed_status_starts_rating(self) -> None:
        message = MessageStub()
        callback = CallbackStub("watch_status:completed", message)
        state = StateStub(
            {
                "tmdb_title": "Просмотрено",
                "content_type": "movie",
            }
        )

        await search_handlers.choose_watch_status(callback, state)

        self.assertEqual(state.state, MenuState.rating_category)
        self.assertEqual(state.data["ratings"], {})
        self.assertEqual(state.data["rating_index"], 0)

    async def test_reject_tmdb_guess_ignores_stale_guess(self) -> None:
        message = MessageStub(message_id=99)
        callback = CallbackStub("tmdb_guess:no", message)
        state = StateStub({"tmdb_guess_message_id": 100})
        state.state = MenuState.confirming_tmdb_guess

        await search_handlers.reject_tmdb_guess(callback, state)

        self.assertEqual(callback.answers, [{"text": "Это старый вариант."}])
        self.assertEqual(state.data["tmdb_guess_message_id"], 100)
        self.assertEqual(state.state, MenuState.confirming_tmdb_guess)
        self.assertEqual(message.answers, [])

    async def test_reject_tmdb_guess_current_guess_moves_to_retry(self) -> None:
        message = MessageStub(message_id=100)
        callback = CallbackStub("tmdb_guess:no", message)
        state = StateStub(
            {
                "action": "add",
                "content_format": "series",
                "tmdb_guess_message_id": 100,
            }
        )

        await search_handlers.reject_tmdb_guess(callback, state)

        self.assertEqual(state.state, MenuState.choosing_tmdb_retry)
        self.assertIsNone(state.data["tmdb_guess_message_id"])
        self.assertEqual(
            message.answers[0]["text"],
            "Не тот результат. Измени название или категорию.",
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


class RatingNavigationHandlerTests(unittest.IsolatedAsyncioTestCase):
    async def test_back_from_first_rating_returns_to_watch_status(self) -> None:
        message = MessageStub()
        callback = CallbackStub("rating:back", message)
        state = StateStub(
            {
                "tmdb_title": "Фильм",
                "content_type": "movie",
                "ratings": {},
                "rating_index": 0,
            }
        )

        await rating_handlers.back_from_rating(callback, state)

        self.assertEqual(state.state, MenuState.choosing_watch_status)
        self.assertTrue(message.deleted)
        self.assertEqual(callback.answers, [{"text": None}])

    async def test_back_from_later_rating_reopens_previous_category(self) -> None:
        message = MessageStub()
        callback = CallbackStub("rating:back", message)
        state = StateStub(
            {
                "tmdb_title": "Фильм",
                "content_type": "movie",
                "ratings": {"acting": 8, "story": 7},
                "rating_index": 2,
            }
        )

        await rating_handlers.back_from_rating(callback, state)

        self.assertEqual(state.data["rating_index"], 1)
        self.assertEqual(state.data["ratings"], {"acting": 8})
        self.assertIn("Сюжет", message.edit_text_calls[0]["text"])


class MovieSavingHandlerTests(unittest.IsolatedAsyncioTestCase):
    async def test_library_rating_edit_updates_existing_item_without_status_change(
        self,
    ) -> None:
        message = MessageStub()
        callback = CallbackStub("rate:9", message)
        ratings = {
            "acting": 8,
            "story": 9,
            "visuals": 8,
            "sound": 9,
            "overall": 9,
        }
        state = StateStub(
            {"media_id": 7, "library_rating_edit": True, "ratings": ratings}
        )

        with patch.object(
            rating_handlers,
            "update_user_media_rating",
            AsyncMock(return_value=True),
        ) as update_rating:
            await rating_handlers.finish_library_rating_edit(callback, state, 8.6)

        update_rating.assert_awaited_once_with(
            123,
            7,
            9,
            rating_details=ratings,
        )
        self.assertFalse(state.data["library_rating_edit"])
        self.assertEqual(state.state, MenuState.choosing_action)

    async def test_finish_movie_saves_completed_media_and_returns_to_menu(self) -> None:
        message = MessageStub()
        callback = CallbackStub("rate:8", message)
        ratings = {
            "animation": 9,
            "story": 8,
            "characters": 9,
            "sound": 8,
            "overall": 9,
        }
        state = StateStub(
            {
                "tmdb_id": 42,
                "tmdb_title": "Фильм",
                "content_type": "cartoon",
                "ratings": ratings,
            }
        )

        with (
            patch.object(
                media_service,
                "upsert_media",
                AsyncMock(return_value=7),
            ) as upsert,
            patch.object(rating_handlers, "save_user_media", AsyncMock()) as save,
        ):
            await rating_handlers.finish_movie(callback, state, 8.6)

        upsert.assert_awaited_once_with(
            tmdb_id=42,
            content_format="full_length",
            content_type="cartoon",
            title="Фильм",
            original_title=None,
            description=None,
            poster_path=None,
            release_date=None,
        )
        save.assert_awaited_once_with(
            user_id=123,
            media_id=7,
            status="completed",
            user_rating=9,
            rating_details=ratings,
        )
        self.assertEqual(state.state, MenuState.choosing_action)

    async def test_finish_movie_reuses_local_media(self) -> None:
        message = MessageStub()
        callback = CallbackStub("rate:8", message)
        ratings = {
            "acting": 8,
            "story": 8,
            "visuals": 8,
            "sound": 8,
            "overall": 8,
        }
        state = StateStub(
            {
                "media_id": 7,
                "tmdb_id": 42,
                "tmdb_title": "Фильм",
                "content_type": "movie",
                "ratings": ratings,
            }
        )

        with (
            patch.object(media_service, "upsert_media", AsyncMock()) as upsert,
            patch.object(rating_handlers, "save_user_media", AsyncMock()) as save,
        ):
            await rating_handlers.finish_movie(callback, state, 8.0)

        upsert.assert_not_awaited()
        save.assert_awaited_once_with(
            user_id=123,
            media_id=7,
            status="completed",
            user_rating=8,
            rating_details=ratings,
        )


class SeriesProgressHandlerTests(unittest.IsolatedAsyncioTestCase):
    async def test_episode_page_navigation_keeps_current_season(self) -> None:
        message = MessageStub()
        callback = CallbackStub("ep:page:1", message)
        state = StateStub(
            {
                "tmdb_title": "Сериал",
                "current_season": 1,
                "seasons_data": [
                    {"season_number": 1, "name": "Сезон 1", "episode_count": 120}
                ],
                "watched_by_season": {"1": 75},
            }
        )

        await series_handlers.handle_episode_selection(callback, state)

        self.assertEqual(state.data["current_season"], 1)
        rendered = message.edit_text_calls[0]
        rows = rendered["reply_markup"].inline_keyboard
        self.assertEqual(rows[1][0].callback_data, "ep:1:51")
        self.assertEqual([button.text for button in rows[11]], ["‹", "2/3", "›"])
        self.assertEqual(callback.answers, [{"text": None}])

    async def test_all_seasons_selection_fills_complete_progress(self) -> None:
        message = MessageStub()
        callback = CallbackStub("season:all", message)
        state = StateStub(
            {
                "tmdb_title": "Сериал",
                "total_episodes": 10,
                "seasons_data": [
                    {"season_number": 1, "name": "Сезон 1", "episode_count": 8},
                    {"season_number": 2, "name": "Сезон 2", "episode_count": 2},
                ],
                "watched_by_season": {},
            }
        )

        await series_handlers.handle_season_selection(callback, state)

        self.assertEqual(state.data["watched_by_season"], {1: 8, 2: 2})
        self.assertEqual(state.data["episodes_watched_total"], 10)
        self.assertEqual(callback.answers, [{"text": None}])
        self.assertEqual(len(message.edit_text_calls), 1)

    async def test_finish_series_rejects_empty_progress_without_saving(self) -> None:
        message = MessageStub()
        callback = CallbackStub("season:done", message)
        state = StateStub(
            {
                "tmdb_title": "Сериал",
                "total_episodes": 8,
                "seasons_data": [
                    {"season_number": 1, "name": "Сезон 1", "episode_count": 8}
                ],
                "watched_by_season": {},
            }
        )

        with patch.object(
            series_handlers,
            "save_user_series_progress",
            AsyncMock(),
        ) as save:
            await series_handlers.finish_series_tracking(callback, state)

        save.assert_not_awaited()
        self.assertEqual(
            callback.answers,
            [
                {
                    "text": "Отметь хотя бы одну просмотренную серию",
                    "show_alert": True,
                }
            ],
        )

    async def test_episode_selection_accepts_progress_serialized_by_redis(self) -> None:
        message = MessageStub()
        callback = CallbackStub("ep:1:5", message)
        state = StateStub(
            {
                "tmdb_title": "Сериал",
                "current_season": 1,
                "total_episodes": 10,
                "seasons_data": [
                    {"season_number": 1, "name": "Сезон 1", "episode_count": 8},
                    {"season_number": 2, "name": "Сезон 2", "episode_count": 2},
                ],
                # JSON object keys are always strings in RedisStorage.
                "watched_by_season": {"1": 3},
            }
        )

        await series_handlers.handle_episode_selection(callback, state)

        self.assertEqual(state.data["watched_by_season"], {1: 5})
        self.assertEqual(state.data["episodes_watched_total"], 5)
        self.assertEqual(callback.answers, [{"text": None}])
        self.assertEqual(len(message.edit_text_calls), 1)

    async def test_episode_back_returns_to_season_list_without_saving(self) -> None:
        message = MessageStub()
        callback = CallbackStub("ep:back", message)
        seasons = [{"season_number": 1, "name": "Сезон 1", "episode_count": 8}]
        state = StateStub(
            {
                "tmdb_title": "Сериал",
                "current_season": 1,
                "seasons_data": seasons,
                "watched_by_season": {"1": 3},
            }
        )

        await series_handlers.handle_episode_selection(callback, state)

        self.assertIsNone(state.data["current_season"])
        self.assertEqual(state.data["watched_by_season"], {"1": 3})
        self.assertEqual(callback.answers, [{"text": None}])
        self.assertEqual(len(message.edit_text_calls), 1)

    async def test_start_series_tracking_ignores_specials_and_legacy_progress(
        self,
    ) -> None:
        message = MessageStub()
        callback = CallbackStub("rate:8", message)
        state = StateStub(
            {
                "media_id": 7,
                "tmdb_id": 42,
                "tmdb_title": "Сериал",
                "content_type": "movie",
            }
        )
        details = TmdbTvDetails(
            number_of_seasons=1,
            number_of_episodes=8,
            seasons=[
                TmdbSeasonInfo(0, "Спецвыпуски", 20),
                TmdbSeasonInfo(1, "Сезон 1", 8),
            ],
        )
        saved_progress = [
            {"season_number": 0, "episodes_watched": 5},
            {"season_number": 1, "episodes_watched": 3},
        ]

        with (
            patch.object(
                series_handlers,
                "fetch_tv_details",
                AsyncMock(return_value=details),
            ),
            patch.object(
                series_handlers,
                "get_user_season_progress",
                AsyncMock(return_value=saved_progress),
            ),
        ):
            await series_handlers.start_series_tracking(callback, state)

        self.assertEqual(
            state.data["seasons_data"],
            [
                {
                    "season_number": 1,
                    "name": "Сезон 1",
                    "episode_count": 8,
                    "announced_episode_count": 8,
                }
            ],
        )
        self.assertEqual(state.data["watched_by_season"], {1: 3})
        self.assertEqual(state.data["total_episodes"], 8)
        self.assertEqual(state.data["episodes_watched_total"], 3)
        self.assertNotIn("tv_details", state.data)
        json.dumps(state.data)

    async def test_start_series_tracking_restores_saved_progress(self) -> None:
        message = MessageStub()
        callback = CallbackStub("rate:8", message)
        state = StateStub(
            {
                "media_id": 7,
                "tmdb_id": 42,
                "tmdb_title": "Сериал",
                "content_type": "movie",
            }
        )
        details = TmdbTvDetails(
            number_of_seasons=2,
            number_of_episodes=10,
            seasons=[
                TmdbSeasonInfo(1, "Сезон 1", 8),
                TmdbSeasonInfo(2, "Сезон 2", 2),
            ],
        )
        saved_progress = [
            {"season_number": 1, "episodes_watched": 6},
            {"season_number": 2, "episodes_watched": 1},
        ]

        with (
            patch.object(
                series_handlers,
                "fetch_tv_details",
                AsyncMock(return_value=details),
            ),
            patch.object(
                series_handlers,
                "get_user_season_progress",
                AsyncMock(return_value=saved_progress),
            ) as get_progress,
        ):
            await series_handlers.start_series_tracking(callback, state)

        get_progress.assert_awaited_once_with(123, 7)
        self.assertEqual(state.data["watched_by_season"], {1: 6, 2: 1})
        self.assertEqual(state.data["episodes_watched_total"], 7)
        self.assertEqual(state.state, MenuState.tracking_series)

    async def test_library_progress_edit_uses_cached_seasons_without_tmdb(self) -> None:
        message = MessageStub()
        callback = CallbackStub("library:item:edit:progress", message)
        state = StateStub(
            {
                "library_progress_edit": True,
                "media_id": 7,
                "tmdb_id": 42,
                "tmdb_title": "Сериал",
                "content_type": "movie",
                "total_seasons": 2,
                "announced_total_episodes": 12,
                "tmdb_series_status": "Returning Series",
                "tmdb_series_in_production": True,
                "tmdb_next_episode_air_date": "2026-08-01",
                "tmdb_next_episode_season_number": 2,
                "tmdb_next_episode_number": 5,
            }
        )
        cached_seasons = [
            {
                "season_number": 1,
                "name": "Сезон 1",
                "announced_episode_count": 8,
                "available_episode_count": 8,
            },
            {
                "season_number": 2,
                "name": "Сезон 2",
                "announced_episode_count": 4,
                "available_episode_count": 2,
            },
        ]

        with (
            patch.object(
                series_handlers,
                "get_media_seasons",
                AsyncMock(return_value=cached_seasons),
            ) as get_seasons,
            patch.object(
                series_handlers,
                "get_user_season_progress",
                AsyncMock(return_value=[{"season_number": 1, "episodes_watched": 3}]),
            ),
            patch.object(
                series_handlers,
                "fetch_tv_details",
                AsyncMock(),
            ) as fetch,
        ):
            await series_handlers.start_series_tracking(callback, state)

        get_seasons.assert_awaited_once_with(7)
        fetch.assert_not_awaited()
        self.assertEqual(state.data["total_episodes"], 10)
        self.assertEqual(state.data["announced_total_episodes"], 12)
        self.assertEqual(state.data["watched_by_season"], {1: 3})
        self.assertEqual(state.state, MenuState.tracking_series)

    async def test_active_series_clamps_progress_to_aired_episodes(self) -> None:
        message = MessageStub()
        callback = CallbackStub("rate:8", message)
        state = StateStub(
            {
                "media_id": 7,
                "tmdb_id": 42,
                "tmdb_title": "Сериал",
                "content_type": "movie",
            }
        )
        details = TmdbTvDetails(
            number_of_seasons=1,
            number_of_episodes=12,
            seasons=[TmdbSeasonInfo(1, "Сезон 1", 12, 5)],
            status="Returning Series",
            in_production=True,
        )

        with (
            patch.object(
                series_handlers,
                "fetch_tv_details",
                AsyncMock(return_value=details),
            ) as fetch,
            patch.object(
                series_handlers,
                "get_user_season_progress",
                AsyncMock(return_value=[{"season_number": 1, "episodes_watched": 12}]),
            ),
        ):
            await series_handlers.start_series_tracking(callback, state)

        fetch.assert_awaited_once_with(42, include_episode_availability=True)
        self.assertEqual(state.data["total_episodes"], 5)
        self.assertEqual(state.data["announced_total_episodes"], 12)
        self.assertEqual(state.data["watched_by_season"], {1: 5})
        self.assertTrue(state.data["is_ongoing"])
        self.assertIn("вышло 5 из 12 сер.", message.answers[0]["text"])

    async def test_finish_series_saves_progress_and_returns_to_menu(self) -> None:
        message = MessageStub()
        callback = CallbackStub("season:done", message)
        state = StateStub(
            {
                "tmdb_id": 42,
                "tmdb_title": "Сериал",
                "content_type": "movie",
                "total_seasons": 2,
                "total_episodes": 10,
                "seasons_data": [
                    {"season_number": 1, "name": "Сезон 1", "episode_count": 8},
                    {"season_number": 2, "name": "Сезон 2", "episode_count": 2},
                ],
                "watched_by_season": {1: 8, 2: 2},
                "episodes_watched_total": 10,
                "rating_average": 8.6,
                "ratings": {
                    "acting": 9,
                    "story": 8,
                    "visuals": 9,
                    "sound": 8,
                    "overall": 9,
                },
                "is_ongoing": True,
                "tmdb_series_status": "Returning Series",
                "tmdb_series_in_production": True,
                "tmdb_next_episode_air_date": "2026-08-01",
                "tmdb_next_episode_season_number": 2,
                "tmdb_next_episode_number": 3,
            }
        )

        with (
            patch.object(
                media_service,
                "upsert_media",
                AsyncMock(return_value=7),
            ) as upsert,
            patch.object(
                series_handlers,
                "save_user_series_progress",
                AsyncMock(),
            ) as save,
            patch.object(
                series_handlers,
                "update_media_series_release_info",
                AsyncMock(),
            ) as update_release,
        ):
            await series_handlers.finish_series_tracking(callback, state)

        upsert.assert_awaited_once_with(
            tmdb_id=42,
            content_format="series",
            content_type="movie",
            title="Сериал",
            original_title=None,
            description=None,
            poster_path=None,
            first_air_date=None,
            number_of_seasons=2,
            number_of_episodes=10,
            available_episode_count=10,
        )
        update_release.assert_awaited_once_with(
            7,
            user_id=123,
            status="Returning Series",
            in_production=True,
            number_of_seasons=2,
            number_of_episodes=10,
            available_episode_count=10,
            seasons=[
                {
                    "season_number": 1,
                    "name": "Сезон 1",
                    "episode_count": 8,
                },
                {
                    "season_number": 2,
                    "name": "Сезон 2",
                    "episode_count": 2,
                },
            ],
            poster_path=None,
            rating=None,
            next_episode_air_date="2026-08-01",
            next_episode_season_number=2,
            next_episode_number=3,
        )
        save.assert_awaited_once_with(
            user_id=123,
            media_id=7,
            seasons={1: 8, 2: 2},
            total_episodes=10,
            is_ongoing=True,
            user_rating=9,
            rating_details={
                "acting": 9,
                "story": 8,
                "visuals": 9,
                "sound": 8,
                "overall": 9,
            },
        )
        self.assertEqual(state.state, MenuState.choosing_action)
        self.assertEqual(callback.answers, [{"text": None}])

    async def test_episode_selection_rejects_stale_season_callback(self) -> None:
        message = MessageStub()
        callback = CallbackStub("ep:1:5", message)
        state = StateStub(
            {
                "current_season": 2,
                "total_episodes": 10,
                "seasons_data": [
                    {"season_number": 1, "name": "Сезон 1", "episode_count": 8},
                    {"season_number": 2, "name": "Сезон 2", "episode_count": 2},
                ],
                "watched_by_season": {1: 3},
            }
        )

        await series_handlers.handle_episode_selection(callback, state)

        self.assertEqual(state.data["watched_by_season"], {1: 3})
        self.assertEqual(
            callback.answers,
            [{"text": "Некорректный переход прогресса", "show_alert": True}],
        )
        self.assertEqual(message.edit_text_calls, [])

    async def test_episode_selection_rejects_count_above_season_limit(self) -> None:
        message = MessageStub()
        callback = CallbackStub("ep:1:9", message)
        state = StateStub(
            {
                "current_season": 1,
                "total_episodes": 8,
                "seasons_data": [
                    {"season_number": 1, "name": "Сезон 1", "episode_count": 8},
                ],
                "watched_by_season": {},
            }
        )

        await series_handlers.handle_episode_selection(callback, state)

        self.assertEqual(state.data["watched_by_season"], {})
        self.assertEqual(
            callback.answers,
            [{"text": "Некорректный переход прогресса", "show_alert": True}],
        )


if __name__ == "__main__":
    unittest.main()
