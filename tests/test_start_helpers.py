import unittest

from src.handlers import start


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


class StartHelpersTests(unittest.TestCase):
    def test_limit_caption_description_keeps_short_description(self) -> None:
        self.assertEqual(
            start._limit_caption_description("Short description", 100),
            "Short description",
        )

    def test_limit_caption_description_returns_empty_for_tiny_limit(self) -> None:
        self.assertEqual(start._limit_caption_description("Description", 1), "")

    def test_tmdb_guess_caption_fits_telegram_photo_caption_limit(self) -> None:
        caption = start._tmdb_guess_caption(
            "full_length",
            "Movie title",
            "A" * 2_000,
        )

        self.assertLessEqual(len(caption), start.PHOTO_CAPTION_LIMIT)

    def test_clear_step_data_clears_only_target_step_fields(self) -> None:
        data = {
            "action": "add",
            "content_format": "series",
            "content_type": "anime",
            "tmdb_guess_message_id": 123,
        }

        start._clear_step_data(data, "format")

        self.assertEqual(
            data,
            {
                "action": "add",
                "tmdb_guess_message_id": 123,
            },
        )


class ActiveTmdbGuessTests(unittest.IsolatedAsyncioTestCase):
    async def test_is_active_tmdb_guess_accepts_current_message(self) -> None:
        callback = CallbackStub(MessageStub(123))
        state = StateStub({"tmdb_guess_message_id": 123})

        self.assertTrue(await start._is_active_tmdb_guess(callback, state))

    async def test_is_active_tmdb_guess_rejects_stale_message(self) -> None:
        callback = CallbackStub(MessageStub(456))
        state = StateStub({"tmdb_guess_message_id": 123})

        self.assertFalse(await start._is_active_tmdb_guess(callback, state))

    async def test_is_active_tmdb_guess_rejects_missing_message(self) -> None:
        callback = CallbackStub(None)
        state = StateStub({"tmdb_guess_message_id": 123})

        self.assertFalse(await start._is_active_tmdb_guess(callback, state))


if __name__ == "__main__":
    unittest.main()
