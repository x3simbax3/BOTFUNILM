from src.database.bot_users import (
    get_active_bot_users,
    mark_bot_user_inactive,
    register_bot_user,
)
from tests.support.database import DatabaseTestCase


class BotUserDatabaseTests(DatabaseTestCase):
    async def test_registers_deactivates_and_reactivates_user(self) -> None:
        await register_bot_user(123, database_url=self.database_url)
        self.assertEqual(
            await get_active_bot_users(database_url=self.database_url),
            [123],
        )

        await mark_bot_user_inactive(123, database_url=self.database_url)
        self.assertEqual(
            await get_active_bot_users(database_url=self.database_url),
            [],
        )

        await register_bot_user(123, database_url=self.database_url)
        self.assertEqual(
            await get_active_bot_users(database_url=self.database_url),
            [123],
        )

    async def test_reads_active_users_in_stable_batches(self) -> None:
        for user_id in (5, 2, 9):
            await register_bot_user(user_id, database_url=self.database_url)

        first = await get_active_bot_users(
            limit=2,
            database_url=self.database_url,
        )
        second = await get_active_bot_users(
            after_user_id=first[-1],
            limit=2,
            database_url=self.database_url,
        )

        self.assertEqual(first, [2, 5])
        self.assertEqual(second, [9])
