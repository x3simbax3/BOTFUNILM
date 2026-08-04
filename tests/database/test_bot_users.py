from src.database.bot_users import (
    get_news_enabled,
    get_news_recipients,
    mark_bot_user_inactive,
    register_bot_user,
    toggle_news_enabled,
    touch_bot_user,
)
from tests.support.database import DatabaseTestCase


class BotUserDatabaseTests(DatabaseTestCase):
    async def test_registers_deactivates_and_reactivates_user(self) -> None:
        self.assertTrue(await register_bot_user(123, database_url=self.database_url))
        self.assertEqual(
            await get_news_recipients(database_url=self.database_url),
            [123],
        )

        await mark_bot_user_inactive(123, database_url=self.database_url)
        self.assertEqual(
            await get_news_recipients(database_url=self.database_url),
            [],
        )

        await register_bot_user(123, database_url=self.database_url)
        self.assertEqual(
            await get_news_recipients(database_url=self.database_url),
            [123],
        )

    async def test_reads_active_users_in_stable_batches(self) -> None:
        for user_id in (5, 2, 9):
            await register_bot_user(user_id, database_url=self.database_url)

        first = await get_news_recipients(
            limit=2,
            database_url=self.database_url,
        )
        second = await get_news_recipients(
            after_user_id=first[-1],
            limit=2,
            database_url=self.database_url,
        )

        self.assertEqual(first, [2, 5])
        self.assertEqual(second, [9])

    async def test_news_are_enabled_by_default_and_can_be_toggled(self) -> None:
        await register_bot_user(123, database_url=self.database_url)

        self.assertTrue(await get_news_enabled(123, database_url=self.database_url))
        self.assertFalse(await toggle_news_enabled(123, database_url=self.database_url))
        self.assertEqual(
            await get_news_recipients(database_url=self.database_url),
            [],
        )

        self.assertFalse(await register_bot_user(123, database_url=self.database_url))
        self.assertTrue(await toggle_news_enabled(123, database_url=self.database_url))
        self.assertEqual(
            await get_news_recipients(database_url=self.database_url),
            [123],
        )

    async def test_missing_user_uses_default_until_first_toggle(self) -> None:
        self.assertTrue(await get_news_enabled(456, database_url=self.database_url))
        self.assertFalse(await toggle_news_enabled(456, database_url=self.database_url))

    async def test_touch_registers_and_reactivates_user(self) -> None:
        await touch_bot_user(
            789,
            username="first_name",
            display_name="First Name",
            database_url=self.database_url,
        )
        self.assertEqual(
            await get_news_recipients(database_url=self.database_url),
            [789],
        )

        await mark_bot_user_inactive(789, database_url=self.database_url)
        await touch_bot_user(
            789,
            username=None,
            display_name="New Name",
            database_url=self.database_url,
        )

        self.assertEqual(
            await get_news_recipients(database_url=self.database_url),
            [789],
        )
