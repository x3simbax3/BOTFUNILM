import unittest
from unittest.mock import AsyncMock

from aiogram.exceptions import TelegramBadRequest

from src.handlers import common, menu


class StateStub:
    def __init__(self, data: dict) -> None:
        self.data = data

    async def get_data(self) -> dict:
        return self.data


class MessageStub:
    def __init__(self, message_id: int) -> None:
        self.message_id = message_id


class CallbackStub:
    def __init__(self, message: MessageStub | None) -> None:
        self.message = message


class HandlerHelpersTests(unittest.TestCase):
    def test_limit_caption_description_keeps_short_description(self) -> None:
        self.assertEqual(
            common.limit_caption_description("Short description", 100),
            "Short description",
        )

    def test_limit_caption_description_returns_empty_for_tiny_limit(self) -> None:
        self.assertEqual(common.limit_caption_description("Description", 1), "")

    def test_tmdb_guess_caption_fits_telegram_photo_caption_limit(self) -> None:
        caption = common.tmdb_guess_caption(
            "full_length",
            "Movie title",
            "A" * 2_000,
        )

        self.assertLessEqual(len(caption), common.PHOTO_CAPTION_LIMIT)

    def test_clear_step_data_clears_only_target_step_fields(self) -> None:
        data = {
            "action": "add",
            "content_format": "series",
            "content_type": "anime",
            "tmdb_guess_message_id": 123,
        }

        menu.clear_step_data(data, "format")

        self.assertEqual(
            data,
            {
                "action": "add",
                "tmdb_guess_message_id": 123,
            },
        )


class EditMessageTests(unittest.IsolatedAsyncioTestCase):
    async def test_identical_message_is_a_safe_noop(self) -> None:
        message = AsyncMock()
        message.photo = []
        message.edit_text.side_effect = TelegramBadRequest(
            method=AsyncMock(),
            message="Bad Request: message is not modified",
        )

        await common.edit_message(message, "Same text")

        message.edit_text.assert_awaited_once()

    async def test_other_bad_requests_are_not_hidden(self) -> None:
        message = AsyncMock()
        message.photo = []
        error = TelegramBadRequest(
            method=AsyncMock(),
            message="Bad Request: message can't be edited",
        )
        message.edit_text.side_effect = error

        with self.assertRaises(TelegramBadRequest) as raised:
            await common.edit_message(message, "New text")

        self.assertIs(raised.exception, error)


class ActiveTmdbGuessTests(unittest.IsolatedAsyncioTestCase):
    async def test_is_active_tmdb_guess_accepts_current_message(self) -> None:
        callback = CallbackStub(MessageStub(123))
        state = StateStub({"tmdb_guess_message_id": 123})

        self.assertTrue(await common.is_active_tmdb_guess(callback, state))

    async def test_is_active_tmdb_guess_rejects_stale_message(self) -> None:
        callback = CallbackStub(MessageStub(456))
        state = StateStub({"tmdb_guess_message_id": 123})

        self.assertFalse(await common.is_active_tmdb_guess(callback, state))

    async def test_is_active_tmdb_guess_rejects_missing_message(self) -> None:
        callback = CallbackStub(None)
        state = StateStub({"tmdb_guess_message_id": 123})

        self.assertFalse(await common.is_active_tmdb_guess(callback, state))


if __name__ == "__main__":
    unittest.main()
