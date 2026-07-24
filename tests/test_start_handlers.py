import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from src.fsm import MenuState
from src.handlers import start
from src.keyboards import (
    content_type_keyboard,
    format_keyboard,
    main_menu_keyboard,
    selected_type_keyboard,
)
from src.texts import (
    START_TEXT,
    TMDB_SEARCHING,
    TMDB_TOO_LONG,
    action_text,
    content_type_text,
    selected_type_text,
    tmdb_found_text,
    tmdb_not_found_text,
)
from src.tmdb import (
    TmdbAuthenticationError,
    TmdbError,
    TmdbNotConfiguredError,
    TmdbNotFoundError,
    TmdbRateLimitError,
    TmdbTitle,
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


class CallbackStub:
    def __init__(
        self,
        data: str | None,
        message: MessageStub | None = None,
    ) -> None:
        self.data = data
        self.message = message
        self.from_user = SimpleNamespace(id=123)
        self.answers = []

    async def answer(self, text: str | None = None, **kwargs) -> None:
        self.answers.append({"text": text, **kwargs})


class StartHandlerTests(unittest.IsolatedAsyncioTestCase):
    async def test_start_clears_state_sets_choosing_action_and_sends_menu(self) -> None:
        message = MessageStub()
        state = StateStub({"action": "add"})

        await start.start(message, state)

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

    async def test_choose_action_saves_action_and_moves_to_choosing_format(self) -> None:
        message = MessageStub()
        callback = CallbackStub("menu:add", message)
        state = StateStub()

        await start.choose_action(callback, state)

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

        await start.choose_format(callback, state)

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

        await start.choose_content_type(callback, state)

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


class SearchTitleHandlerTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        patcher = patch.object(
            start,
            "find_media_by_title",
            AsyncMock(return_value=None),
        )
        self.local_search = patcher.start()
        self.addCleanup(patcher.stop)
        poster_patcher = patch.object(
            start,
            "download_poster",
            AsyncMock(return_value=None),
        )
        self.poster_download = poster_patcher.start()
        self.addCleanup(poster_patcher.stop)

    async def test_search_title_without_text_asks_for_text(self) -> None:
        message = MessageStub(text=None)
        state = StateStub({"content_format": "full_length"})

        await start.search_title(message, state)

        self.assertEqual(message.answers[0]["text"], "Введи название текстом.")

    async def test_search_title_with_empty_text_rejects_title(self) -> None:
        message = MessageStub(text="   ")
        state = StateStub({"content_format": "full_length"})

        await start.search_title(message, state)

        self.assertEqual(
            message.answers[0]["text"],
            "Название не может быть пустым. Введи название ещё раз.",
        )

    async def test_search_title_without_content_format_asks_to_restart(self) -> None:
        message = MessageStub(text="Матрица")
        state = StateStub()

        await start.search_title(message, state)

        self.assertEqual(
            message.answers[0]["text"],
            "Не найден выбранный формат. Начни заново через /start.",
        )

    async def test_search_title_too_long_rejects(self) -> None:
        message = MessageStub(text="x" * 343)
        state = StateStub({"content_format": "full_length"})

        await start.search_title(message, state)

        self.assertEqual(message.answers[0]["text"], TMDB_TOO_LONG)

    async def test_search_title_found_with_poster_sends_photo_guess(self) -> None:
        message = MessageStub(text="Матрица")
        state = StateStub({"content_format": "full_length"})
        guess = TmdbTitle("Матрица", "Описание", "https://image.test/poster.jpg", "Матрица", "Матрица")

        with patch.object(start, "find_title_guess", AsyncMock(return_value=guess)):
            await start.search_title(message, state)

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

        with patch.object(start, "find_title_guess", AsyncMock(return_value=guess)):
            await start.search_title(message, state)

        self.assertEqual(message.answers[0]["text"], TMDB_SEARCHING)
        status_stub = message.answers[0]["stub"]
        self.assertIn("Матрица", status_stub.last_text)
        self.assertEqual(state.data["tmdb_guess_message_id"], 101)
        self.assertEqual(state.state, MenuState.confirming_tmdb_guess)

    async def test_search_title_uses_local_media_without_tmdb_request(self) -> None:
        message = MessageStub(text="матрица")
        state = StateStub(
            {"content_format": "full_length", "content_type": "movie"}
        )
        self.local_search.return_value = {
            "id": 7,
            "tmdb_id": 42,
            "title": "Матрица",
            "description": "Описание",
            "poster_path": "/poster.jpg",
        }

        with patch.object(start, "find_title_guess", AsyncMock()) as tmdb_search:
            await start.search_title(message, state)

        tmdb_search.assert_not_awaited()
        self.assertEqual(state.data["media_id"], 7)
        self.assertEqual(state.data["tmdb_id"], 42)
        self.assertEqual(
            message.photo_answers[0]["photo"],
            f"{start.TMDB_IMAGE_URL}/poster.jpg",
        )

    async def test_search_title_falls_back_to_tmdb(self) -> None:
        message = MessageStub(text="Матрица")
        state = StateStub({"content_format": "full_length"})
        guess = TmdbTitle("Матрица", None, None, "Матрица", "Матрица", 42)

        with patch.object(
            start,
            "find_title_guess",
            AsyncMock(return_value=guess),
        ) as tmdb_search:
            await start.search_title(message, state)

        self.local_search.assert_awaited_once_with(
            "Матрица",
            "full_length",
            "movie",
        )
        tmdb_search.assert_awaited_once_with("Матрица", "full_length", "movie")
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
            start,
            "find_title_guess",
            AsyncMock(side_effect=TmdbNotFoundError),
        ):
            await start.search_title(message, state)

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
            start,
            "find_title_guess",
            AsyncMock(side_effect=error_class),
        ):
            await start.search_title(message, state)

        self.assertEqual(message.answers[0]["text"], TMDB_SEARCHING)
        status_stub = message.answers[0]["stub"]
        self.assertEqual(status_stub.last_text, expected_text)


class TmdbRejectRetryHandlerTests(unittest.IsolatedAsyncioTestCase):
    async def test_reject_tmdb_guess_ignores_stale_guess(self) -> None:
        message = MessageStub(message_id=99)
        callback = CallbackStub("tmdb_guess:no", message)
        state = StateStub({"tmdb_guess_message_id": 100})
        state.state = MenuState.confirming_tmdb_guess

        await start.reject_tmdb_guess(callback, state)

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

        await start.reject_tmdb_guess(callback, state)

        self.assertEqual(state.state, MenuState.choosing_tmdb_retry)
        self.assertIsNone(state.data["tmdb_guess_message_id"])
        self.assertEqual(message.answers[0]["text"], "Ок, не оно. Что сделать?")
        self.assertEqual(callback.answers, [{"text": None}])

    async def test_retry_title_moves_back_to_waiting_title(self) -> None:
        message = MessageStub()
        callback = CallbackStub("title:retry", message)
        state = StateStub()

        await start.retry_title(callback, state)

        self.assertEqual(state.state, MenuState.waiting_title)
        self.assertEqual(
            message.edit_text_calls,
            [{"text": "Введи название ещё раз.", "parse_mode": None, "reply_markup": None}],
        )
        self.assertEqual(callback.answers, [{"text": None}])


class MovieSavingHandlerTests(unittest.IsolatedAsyncioTestCase):
    async def test_finish_movie_saves_completed_media_and_returns_to_menu(self) -> None:
        message = MessageStub()
        callback = CallbackStub("rate:8", message)
        state = StateStub(
            {
                "tmdb_id": 42,
                "tmdb_title": "Фильм",
                "content_type": "cartoon",
            }
        )

        with (
            patch.object(start, "upsert_media", AsyncMock(return_value=7)) as upsert,
            patch.object(start, "save_user_media", AsyncMock()) as save,
        ):
            await start._finish_movie(callback, state, 8.6)

        upsert.assert_awaited_once_with(
            tmdb_id=42,
            content_format="full_length",
            content_type="cartoon",
            title="Фильм",
            description=None,
            poster_path=None,
        )
        save.assert_awaited_once_with(
            user_id=123,
            media_id=7,
            status="completed",
            user_rating=9,
        )
        self.assertEqual(state.state, MenuState.choosing_action)

    async def test_finish_movie_reuses_local_media(self) -> None:
        message = MessageStub()
        callback = CallbackStub("rate:8", message)
        state = StateStub(
            {
                "media_id": 7,
                "tmdb_id": 42,
                "tmdb_title": "Фильм",
                "content_type": "movie",
            }
        )

        with (
            patch.object(start, "upsert_media", AsyncMock()) as upsert,
            patch.object(start, "save_user_media", AsyncMock()) as save,
        ):
            await start._finish_movie(callback, state, 8.0)

        upsert.assert_not_awaited()
        save.assert_awaited_once_with(
            user_id=123,
            media_id=7,
            status="completed",
            user_rating=8,
        )


class SeriesProgressHandlerTests(unittest.IsolatedAsyncioTestCase):
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
                "watched_by_season": {1: 8, 2: 2},
                "episodes_watched_total": 10,
                "rating_average": 8.6,
            }
        )

        with (
            patch.object(start, "upsert_media", AsyncMock(return_value=7)) as upsert,
            patch.object(start, "save_user_series_progress", AsyncMock()) as save,
        ):
            await start._finish_series_tracking(callback, state)

        upsert.assert_awaited_once_with(
            tmdb_id=42,
            content_format="series",
            content_type="movie",
            title="Сериал",
            description=None,
            poster_path=None,
            number_of_seasons=2,
            number_of_episodes=10,
        )
        save.assert_awaited_once_with(
            user_id=123,
            media_id=7,
            seasons={1: 8, 2: 2},
            total_episodes=10,
            user_rating=9,
        )
        self.assertEqual(state.state, MenuState.choosing_action)
        self.assertEqual(callback.answers, [{"text": None}])


if __name__ == "__main__":
    unittest.main()
