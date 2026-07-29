import unittest
from unittest.mock import AsyncMock, patch

from src.fsm import MenuState
from src.handlers import rating as rating_handlers
from tests.support.telegram import CallbackStub, MessageStub, StateStub


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
        self.assertEqual(state.data, {})
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

        with patch.object(
            rating_handlers,
            "save_completed_movie",
            AsyncMock(return_value=7),
        ) as save:
            await rating_handlers.finish_movie(callback, state, 8.6)

        save.assert_awaited_once_with(
            123,
            {
                "tmdb_id": 42,
                "tmdb_title": "Фильм",
                "content_type": "cartoon",
                "ratings": ratings,
            },
            8.6,
        )
        self.assertEqual(state.state, MenuState.choosing_action)
