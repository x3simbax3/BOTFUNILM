import unittest
from unittest.mock import ANY, AsyncMock, patch

from aiogram.exceptions import TelegramBadRequest

from src.fsm import MenuState
from src.handlers import search as search_handlers
from src.handlers.search import candidates as candidate_handlers
from src.lang import TMDB_SEARCHING, TMDB_TOO_LONG
from src.services import media as media_service
from src.services import planned_media, title_search
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
from src.tmdb_models import TmdbMovieDetails
from tests.support.telegram import CallbackStub, MessageStub, StateStub


class SearchTitleHandlerTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        patcher = patch.object(
            title_search,
            "find_media_by_title",
            AsyncMock(return_value=None),
        )
        self.local_search = patcher.start()
        self.addCleanup(patcher.stop)

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
            "Матрица",
            "Описание",
            "https://image.tmdb.org/t/p/w500/poster.jpg",
            "Матрица",
            "Матрица",
        )

        with patch.object(
            title_search,
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
            title_search,
            "find_title_candidates",
            AsyncMock(return_value=[guess]),
        ):
            await search_handlers.search_title(message, state)

        self.assertEqual(message.answers[0]["text"], TMDB_SEARCHING)
        status_stub = message.answers[0]["stub"]
        self.assertIn("Матрица", status_stub.last_text)
        self.assertEqual(state.data["tmdb_guess_message_id"], 101)
        self.assertEqual(state.state, MenuState.confirming_tmdb_guess)

    async def test_stale_candidate_photo_is_cleared_and_sent_as_text(self) -> None:
        message = MessageStub()
        message.answer_photo = AsyncMock(
            side_effect=TelegramBadRequest(method=AsyncMock(), message="bad file id")
        )
        candidate = {
            "media_id": 7,
            "title": "Матрица",
            "poster_path": None,
            "poster_url": None,
            "telegram_poster_file_id": "stale-file-id",
        }

        with patch.object(
            candidate_handlers,
            "clear_media_telegram_poster_file_id",
            AsyncMock(),
        ) as clear_file_id:
            sent = await candidate_handlers._send_candidate(
                message,
                candidate,
                "full_length",
                0,
                1,
            )

        clear_file_id.assert_awaited_once_with(7)
        self.assertIsNone(candidate["telegram_poster_file_id"])
        self.assertEqual(sent.message_id, message.answers[0]["stub"].message_id)
        self.assertIn("Матрица", message.answers[0]["text"])

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
            title_search,
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
            title_search,
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
            title_search,
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
            title_search,
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

    async def test_future_movie_does_not_show_completed_status(self) -> None:
        message = MessageStub(message_id=100)
        callback = CallbackStub("tmdb_guess:yes", message)
        state = StateStub(
            {
                "tmdb_guess_message_id": 100,
                "tmdb_id": 969681,
                "tmdb_title": "Человек-паук: Новый день",
                "content_format": "full_length",
                "content_type": "movie",
                "is_released": True,
            }
        )
        details = TmdbMovieDetails(
            title="Человек-паук: Новый день",
            original_title="Spider-Man: Brand New Day",
            description=None,
            poster_path=None,
            rating=None,
            release_date="2999-08-06",
            status="Released",
        )

        with (
            patch.object(
                candidate_handlers,
                "_already_in_library",
                AsyncMock(return_value=False),
            ),
            patch.object(
                candidate_handlers,
                "fetch_movie_details",
                AsyncMock(return_value=details),
            ),
        ):
            await search_handlers.confirm_tmdb_guess(callback, state)

        status_keyboard = message.answers[0]["reply_markup"]
        self.assertEqual(
            [
                button.callback_data
                for row in status_keyboard.inline_keyboard
                for button in row
            ],
            ["watch_status:planned"],
        )
        self.assertFalse(state.data["is_released"])
        self.assertEqual(state.data["tmdb_release_date"], "2999-08-06")

    async def test_confirm_guess_keeps_stale_button_fallback_if_delete_fails(
        self,
    ) -> None:
        message = MessageStub(message_id=100)
        callback = CallbackStub("tmdb_guess:yes", message)
        state = StateStub({"tmdb_guess_message_id": 100})

        with patch.object(
            candidate_handlers,
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
            candidate_handlers,
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
                planned_media,
                "save_user_media",
                AsyncMock(),
            ) as save,
            patch.object(
                planned_media,
                "fetch_tv_details",
                AsyncMock(return_value=details),
            ),
            patch.object(
                planned_media,
                "update_media_series_release_info",
                AsyncMock(),
            ) as update_release,
        ):
            await search_handlers.choose_watch_status(callback, state)

        save.assert_awaited_once_with(
            user_id=123,
            media_id=7,
            status="planned",
            is_tracking=False,
            connection=ANY,
        )
        update_release.assert_awaited_once_with(
            7,
            user_id=123,
            snapshot=details,
            connection=ANY,
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
