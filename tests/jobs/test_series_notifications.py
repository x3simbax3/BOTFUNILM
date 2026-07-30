from unittest.mock import AsyncMock

from src.database.connection import connection_scope
from src.database.series_subscriptions import (
    prepare_notification_batches,
    record_series_release,
    set_series_subscription,
)
from src.jobs.series_notifications import send_release_notifications
from tests.support.database import DatabaseTestCase


class SeriesNotificationJobTests(DatabaseTestCase):
    async def test_sends_one_message_and_marks_batch_sent(self) -> None:
        media_id = await self.create_user_media(
            media_kwargs={
                "content_format": "series",
                "content_type": "anime",
                "title": "Табакошка",
                "number_of_episodes": 4,
                "available_episode_count": 3,
            }
        )
        async with connection_scope(self.database_url) as connection:
            await connection.execute(
                "UPDATE media SET tmdb_status = 'Returning Series' WHERE id = ?",
                (media_id,),
            )
        await set_series_subscription(
            123,
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
                active=True,
            )
        bot = AsyncMock()

        stats = await send_release_notifications(
            bot,
            database_url=self.database_url,
        )

        self.assertEqual(stats.sent, 1)
        bot.send_message.assert_awaited_once()
        self.assertIn("Табакошка", bot.send_message.await_args.kwargs["text"])
        self.assertIn("вышло 1 серия", bot.send_message.await_args.kwargs["text"])
        self.assertEqual(
            await prepare_notification_batches(database_url=self.database_url),
            [],
        )
