from src.database.connection import connection_scope
from src.database.series_subscriptions import (
    SeriesSubscriptionLimitError,
    SeriesSubscriptionUnavailableError,
    get_notification_batch,
    list_tracked_series,
    prepare_notification_batches,
    record_series_release,
    set_series_subscription,
)
from tests.support.database import DatabaseTestCase


class SeriesSubscriptionDatabaseTests(DatabaseTestCase):
    async def _active_user_series(self, tmdb_id: int, *, user_id: int = 123) -> int:
        media_id = await self.create_user_media(
            user_id=user_id,
            media_kwargs={
                "tmdb_id": tmdb_id,
                "content_format": "series",
                "content_type": "movie",
                "title": f"Series {tmdb_id}",
                "number_of_episodes": 4,
                "available_episode_count": 3,
            },
        )
        async with connection_scope(self.database_url) as connection:
            await connection.execute(
                "UPDATE media SET tmdb_status = 'Returning Series' WHERE id = ?",
                (media_id,),
            )
        return media_id

    async def test_subscription_can_only_be_enabled_for_active_series(self) -> None:
        media_id = await self.create_user_media(
            media_kwargs={
                "content_format": "series",
                "content_type": "movie",
                "title": "Ended",
            }
        )

        with self.assertRaises(SeriesSubscriptionUnavailableError):
            await set_series_subscription(
                123,
                media_id,
                True,
                database_url=self.database_url,
            )

    async def test_subscription_list_contains_enabled_series(self) -> None:
        media_id = await self._active_user_series(100)

        enabled = await set_series_subscription(
            123,
            media_id,
            True,
            database_url=self.database_url,
        )
        items = await list_tracked_series(123, database_url=self.database_url)

        self.assertTrue(enabled)
        self.assertEqual([int(item["id"]) for item in items], [media_id])

    async def test_subscription_limit_is_fifty(self) -> None:
        for tmdb_id in range(1000, 1050):
            media_id = await self._active_user_series(tmdb_id)
            await set_series_subscription(
                123,
                media_id,
                True,
                database_url=self.database_url,
            )
        extra_id = await self._active_user_series(1050)

        with self.assertRaises(SeriesSubscriptionLimitError):
            await set_series_subscription(
                123,
                extra_id,
                True,
                database_url=self.database_url,
            )

    async def test_release_is_queued_for_each_subscriber_and_disables_ended(
        self,
    ) -> None:
        media_id = await self._active_user_series(200, user_id=123)
        await self.create_user_media(user_id=456, media_id=media_id)
        for user_id in (123, 456):
            await set_series_subscription(
                user_id,
                media_id,
                True,
                database_url=self.database_url,
            )

        async with connection_scope(self.database_url) as connection:
            await record_series_release(
                connection,
                media_id,
                3,
                4,
                season_number=1,
                episode_number=4,
                active=False,
            )

        batches = await prepare_notification_batches(database_url=self.database_url)
        self.assertEqual([batch.user_id for batch in batches], [123, 456])
        for batch in batches:
            items = await get_notification_batch(
                batch.batch_id,
                batch.user_id,
                database_url=self.database_url,
            )
            self.assertEqual(items[0].released_count, 1)
            self.assertEqual(items[0].episode_number, 4)
        self.assertEqual(
            await list_tracked_series(123, database_url=self.database_url),
            [],
        )
