from unittest.mock import AsyncMock, patch

from src.database.connection import connection_scope
from src.jobs.custom_broadcast import send_custom_broadcast
from tests.support.database import DatabaseTestCase


class CustomBroadcastTests(DatabaseTestCase):
    async def test_sends_text_to_all_active_users_and_records_result(self) -> None:
        async with connection_scope(self.database_url) as connection:
            await connection.executemany(
                "INSERT INTO bot_users (user_id, is_active) VALUES (?, ?)",
                ((1, 1), (2, 1), (3, 0)),
            )
        bot = AsyncMock()

        with patch("src.jobs.custom_broadcast.asyncio.sleep", new=AsyncMock()):
            stats = await send_custom_broadcast(
                bot,
                "Важная новость",
                database_url=self.database_url,
            )

        self.assertEqual((stats.selected, stats.sent, stats.failed), (2, 2, 0))
        self.assertEqual(bot.send_message.await_count, 2)
        bot.send_photo.assert_not_awaited()
        async with connection_scope(self.database_url) as connection:
            async with connection.execute(
                """
                SELECT notification_type, selected, sent
                FROM notification_delivery_runs
                """
            ) as cursor:
                row = await cursor.fetchone()
        self.assertEqual(
            (row["notification_type"], row["selected"], row["sent"]),
            ("broadcast", 2, 2),
        )

    async def test_sends_photo_with_plain_text_caption(self) -> None:
        async with connection_scope(self.database_url) as connection:
            await connection.execute("INSERT INTO bot_users (user_id) VALUES (1)")
        bot = AsyncMock()

        with patch("src.jobs.custom_broadcast.asyncio.sleep", new=AsyncMock()):
            await send_custom_broadcast(
                bot,
                "<b>Без HTML</b>",
                photo_file_id="photo-id",
                database_url=self.database_url,
            )

        bot.send_photo.assert_awaited_once_with(
            chat_id=1,
            photo="photo-id",
            caption="<b>Без HTML</b>",
            parse_mode=None,
        )
