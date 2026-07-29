import unittest
from unittest.mock import AsyncMock, patch

from src.database import media


class MediaCompatibilityTests(unittest.IsolatedAsyncioTestCase):
    async def test_old_replace_media_seasons_signature_builds_snapshot(self) -> None:
        seasons = [
            {
                "season_number": 1,
                "name": "Сезон 1",
                "announced_episode_count": 12,
                "episode_count": 5,
            }
        ]
        with patch.object(media, "_replace_media_seasons", AsyncMock()) as replace:
            await media.replace_media_seasons(7, seasons, database_url="db.sqlite")

        replace.assert_awaited_once()
        self.assertEqual(replace.await_args.args[0], 7)
        snapshot = replace.await_args.args[1]
        self.assertEqual(snapshot.number_of_episodes, 12)
        self.assertEqual(snapshot.available_episode_count, 5)
        self.assertEqual(replace.await_args.kwargs["database_url"], "db.sqlite")

    async def test_old_release_update_signature_builds_typed_snapshot(self) -> None:
        with patch.object(
            media,
            "_update_media_series_release_info",
            AsyncMock(),
        ) as update:
            await media.update_media_series_release_info(
                7,
                user_id=123,
                status="Returning Series",
                in_production=True,
                number_of_seasons=1,
                number_of_episodes=12,
                available_episode_count=5,
                seasons=[
                    {
                        "season_number": 1,
                        "name": "Сезон 1",
                        "announced_episode_count": 12,
                        "episode_count": 5,
                    }
                ],
                poster_path="/poster.jpg",
                rating=8.7,
                next_episode_air_date="2026-08-01",
                next_episode_season_number=1,
                next_episode_number=6,
                database_url="db.sqlite",
            )

        update.assert_awaited_once()
        self.assertEqual(update.await_args.args, (7,))
        self.assertEqual(update.await_args.kwargs["user_id"], 123)
        snapshot = update.await_args.kwargs["snapshot"]
        self.assertEqual(snapshot.next_episode.episode_number, 6)
        self.assertEqual(snapshot.available_episode_count, 5)

    async def test_old_release_update_rejects_inconsistent_availability(self) -> None:
        with self.assertRaisesRegex(ValueError, "availability"):
            await media.update_media_series_release_info(
                7,
                user_id=123,
                status=None,
                in_production=None,
                number_of_seasons=1,
                number_of_episodes=12,
                available_episode_count=6,
                seasons=[
                    {
                        "season_number": 1,
                        "name": "Сезон 1",
                        "announced_episode_count": 12,
                        "episode_count": 5,
                    }
                ],
                poster_path=None,
                rating=None,
                next_episode_air_date=None,
                next_episode_season_number=None,
                next_episode_number=None,
            )


if __name__ == "__main__":
    unittest.main()
