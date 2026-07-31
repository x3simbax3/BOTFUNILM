import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from aiogram.exceptions import TelegramBadRequest

from src.fsm import MenuState
from src.handlers import library as library_handlers
from src.handlers import menu as menu_handlers
from src.tmdb import TMDB_IMAGE_URL, TmdbTitle
from tests.support.telegram import CallbackStub, MessageStub, StateStub


class PhotoCachingMessageStub(MessageStub):
    async def answer_photo(self, photo: str, **kwargs):
        sent = await super().answer_photo(photo, **kwargs)
        sent.photo = [SimpleNamespace(file_id="telegram-file-id")]
        return sent


class LibraryHandlerTests(unittest.IsolatedAsyncioTestCase):
    async def test_badge_can_be_changed_from_library_item(self) -> None:
        message = MessageStub()
        callback = CallbackStub("library_badge:funny", message)
        state = StateStub({"media_id": 7})
        item = {
            "id": 7,
            "content_format": "full_length",
            "user_status": "completed",
        }

        with (
            patch.object(
                library_handlers,
                "get_user_library_item",
                AsyncMock(side_effect=[item, item | {"badge": "funny"}]),
            ),
            patch.object(
                library_handlers,
                "update_user_media_badge",
                AsyncMock(return_value=True),
            ) as update_badge,
            patch.object(
                library_handlers,
                "_edit_library_item_message",
                AsyncMock(),
            ) as edit_item,
        ):
            await library_handlers.change_library_item_badge(callback, state)

        update_badge.assert_awaited_once_with(123, 7, "funny")
        edit_item.assert_awaited_once()
        self.assertEqual(state.state, MenuState.viewing_media)

    async def test_opening_item_caches_telegram_photo_file_id(self) -> None:
        message = PhotoCachingMessageStub()
        state = StateStub()
        item = {
            "id": 7,
            "tmdb_id": 42,
            "title": "Матрица",
            "original_title": "The Matrix",
            "description": "Описание",
            "poster_path": "/poster.jpg",
            "telegram_poster_file_id": None,
            "content_format": "full_length",
            "content_type": "movie",
            "user_status": "completed",
            "user_rating": 9,
            "rating": 8.7,
            "release_date": "1999-03-31",
            "first_air_date": None,
            "number_of_seasons": None,
            "number_of_episodes": None,
            "episodes_watched": None,
            "library_users_count": 1,
        }
        with (
            patch.object(
                library_handlers,
                "get_user_library_item",
                AsyncMock(return_value=item),
            ),
            patch.object(
                library_handlers,
                "update_media_telegram_poster_file_id",
                AsyncMock(),
            ) as update_file_id,
        ):
            await library_handlers.show_library_item(message, state, 123, 7)

        self.assertEqual(
            message.photo_answers[0]["photo"],
            f"{TMDB_IMAGE_URL}/poster.jpg",
        )
        update_file_id.assert_awaited_once_with(7, "telegram-file-id")

    async def test_stale_cached_photo_is_cleared_and_card_becomes_text(self) -> None:
        message = MessageStub()
        message.answer_photo = AsyncMock(
            side_effect=TelegramBadRequest(method=AsyncMock(), message="bad file id")
        )
        state = StateStub()
        item = {
            "id": 7,
            "tmdb_id": None,
            "title": "Матрица",
            "original_title": None,
            "description": "Описание",
            "poster_path": None,
            "telegram_poster_file_id": "stale-file-id",
            "content_format": "full_length",
            "content_type": "movie",
            "user_status": "completed",
            "user_rating": 9,
            "rating": 8.7,
            "release_date": "1999-03-31",
            "first_air_date": None,
            "number_of_seasons": None,
            "number_of_episodes": None,
            "episodes_watched": None,
            "library_users_count": 1,
        }

        with (
            patch.object(
                library_handlers,
                "get_user_library_item",
                AsyncMock(return_value=item),
            ),
            patch.object(
                library_handlers,
                "clear_media_telegram_poster_file_id",
                AsyncMock(),
            ) as clear_file_id,
        ):
            opened = await library_handlers.show_library_item(
                message,
                state,
                123,
                7,
            )

        self.assertTrue(opened)
        clear_file_id.assert_awaited_once_with(7)
        self.assertEqual(len(message.answers), 1)
        self.assertIn("Матрица", message.answers[0]["text"])

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

        with (
            patch.object(
                library_handlers,
                "get_user_library_item",
                AsyncMock(return_value=item),
            ),
            patch.object(
                menu_handlers,
                "register_bot_user",
                new=AsyncMock(),
            ) as register_user,
        ):
            await menu_handlers.start(message, state)

        register_user.assert_awaited_once_with(123)
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

    async def test_empty_library_prompts_user_to_add_first_item(self) -> None:
        message = MessageStub()
        callback = CallbackStub("menu:library", message)
        state = StateStub()

        with (
            patch.object(
                library_handlers,
                "get_user_library_filters",
                AsyncMock(return_value={"movie": True, "series": True}),
            ),
            patch.object(
                library_handlers,
                "list_user_library",
                AsyncMock(return_value=[]),
            ),
        ):
            await library_handlers.open_library(callback, state)

        self.assertIn(
            "Добавь первую запись в библиотеку.",
            message.edit_text_calls[0]["text"],
        )

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
