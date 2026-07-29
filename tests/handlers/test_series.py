import json
import unittest
from unittest.mock import AsyncMock, patch

from src.fsm import MenuState
from src.handlers import series as series_handlers
from src.services import media as media_service
from src.services import series_metadata, series_tracking
from src.tmdb import TmdbSeasonInfo, TmdbTvDetails
from tests.support.telegram import CallbackStub, MessageStub, StateStub


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
            series_tracking,
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
                series_metadata,
                "fetch_tv_details",
                AsyncMock(return_value=details),
            ),
            patch.object(
                series_tracking,
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
                series_metadata,
                "fetch_tv_details",
                AsyncMock(return_value=details),
            ),
            patch.object(
                series_tracking,
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
                series_metadata,
                "get_media_seasons",
                AsyncMock(return_value=cached_seasons),
            ) as get_seasons,
            patch.object(
                series_tracking,
                "get_user_season_progress",
                AsyncMock(return_value=[{"season_number": 1, "episodes_watched": 3}]),
            ),
            patch.object(
                series_metadata,
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
                series_metadata,
                "fetch_tv_details",
                AsyncMock(return_value=details),
            ) as fetch,
            patch.object(
                series_tracking,
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
                series_tracking,
                "save_user_series_progress",
                AsyncMock(),
            ) as save,
            patch.object(
                series_tracking,
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
        update_release.assert_awaited_once()
        self.assertEqual(update_release.await_args.args, (7,))
        self.assertEqual(update_release.await_args.kwargs["user_id"], 123)
        snapshot = update_release.await_args.kwargs["snapshot"]
        self.assertEqual(snapshot.number_of_seasons, 2)
        self.assertEqual(snapshot.number_of_episodes, 10)
        self.assertEqual(snapshot.available_episode_count, 10)
        self.assertEqual(snapshot.next_episode.season_number, 2)
        self.assertEqual(snapshot.next_episode.episode_number, 3)
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
