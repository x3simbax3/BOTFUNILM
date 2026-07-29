from src.database.connection import connection_scope
from src.database.library import (
    get_user_library_filters,
    get_user_library_item,
    list_user_library,
    update_user_library_filter,
)
from tests.support.database import DatabaseTestCase


class LibraryTests(DatabaseTestCase):
    async def test_library_filters_are_persisted_per_user(self) -> None:
        defaults = await get_user_library_filters(123, database_url=self.database_url)
        changed = await update_user_library_filter(
            123,
            "anime",
            database_url=self.database_url,
        )
        other_user = await get_user_library_filters(456, database_url=self.database_url)

        self.assertTrue(defaults["completed"])
        self.assertTrue(defaults["planned"])
        self.assertTrue(all(defaults.values()))
        self.assertTrue(changed["anime"])
        self.assertFalse(changed["movie"])
        self.assertFalse(changed["cartoon"])
        self.assertTrue(changed["series"])
        self.assertTrue(changed["full_length"])
        self.assertTrue(other_user["completed"])
        self.assertTrue(other_user["planned"])

    async def test_library_filters_are_exclusive_within_each_group(self) -> None:
        series = await update_user_library_filter(
            123,
            "series",
            database_url=self.database_url,
        )
        anime = await update_user_library_filter(
            123,
            "anime",
            database_url=self.database_url,
        )
        planned = await update_user_library_filter(
            123,
            "planned",
            database_url=self.database_url,
        )
        reset = await update_user_library_filter(
            123,
            "all",
            database_url=self.database_url,
        )

        self.assertTrue(series["series"])
        self.assertFalse(series["full_length"])
        self.assertTrue(anime["series"])
        self.assertFalse(anime["full_length"])
        self.assertTrue(anime["anime"])
        self.assertFalse(anime["movie"])
        self.assertFalse(anime["cartoon"])
        self.assertTrue(planned["planned"])
        self.assertFalse(planned["completed"])
        self.assertTrue(reset["completed"])
        self.assertTrue(reset["planned"])
        self.assertTrue(all(reset.values()))

    async def test_clicking_selected_filter_restores_its_group(self) -> None:
        for filter_name, group in (
            ("series", ("series", "full_length")),
            ("anime", ("movie", "anime", "cartoon")),
        ):
            with self.subTest(filter_name=filter_name):
                selected = await update_user_library_filter(
                    123,
                    filter_name,
                    database_url=self.database_url,
                )
                restored = await update_user_library_filter(
                    123,
                    filter_name,
                    database_url=self.database_url,
                )

                self.assertTrue(selected[filter_name])
                self.assertTrue(all(restored[name] for name in group))

    async def test_clicking_selected_status_restores_all_statuses(self) -> None:
        selected = await update_user_library_filter(
            123,
            "planned",
            database_url=self.database_url,
        )
        restored = await update_user_library_filter(
            123,
            "planned",
            database_url=self.database_url,
        )

        self.assertTrue(selected["planned"])
        self.assertFalse(selected["completed"])
        self.assertTrue(
            all(
                restored[name]
                for name in ("completed", "planned", "unfinished", "ongoing")
            )
        )

    async def test_library_can_be_filtered_by_watch_status(self) -> None:
        completed_id = await self.create_media(
            tmdb_id=301,
            content_format="full_length",
            content_type="movie",
            title="Просмотрено",
        )
        planned_id = await self.create_media(
            tmdb_id=302,
            content_format="full_length",
            content_type="movie",
            title="На потом",
        )
        watching_id = await self.create_media(
            tmdb_id=303,
            content_format="series",
            content_type="movie",
            title="Начато",
            number_of_episodes=10,
        )
        await self.create_user_media(
            user_id=123,
            media_id=completed_id,
            status="completed",
        )
        await self.create_user_media(
            user_id=123,
            media_id=watching_id,
            status="watching",
            episodes_watched=1,
        )
        await self.create_user_media(
            user_id=123,
            media_id=planned_id,
            status="planned",
        )

        filters = await update_user_library_filter(
            123,
            "planned",
            database_url=self.database_url,
        )
        rows = await list_user_library(
            123,
            filters,
            database_url=self.database_url,
        )

        self.assertEqual([row["title"] for row in rows], ["На потом"])

        completed_filters = await update_user_library_filter(
            123,
            "completed",
            database_url=self.database_url,
        )
        watched_rows = await list_user_library(
            123,
            completed_filters,
            database_url=self.database_url,
        )
        self.assertEqual(
            {row["title"] for row in watched_rows},
            {"Просмотрено"},
        )

        unfinished_filters = await update_user_library_filter(
            123,
            "unfinished",
            database_url=self.database_url,
        )
        unfinished_rows = await list_user_library(
            123,
            unfinished_filters,
            database_url=self.database_url,
        )
        self.assertEqual([row["title"] for row in unfinished_rows], ["Начато"])

        async with connection_scope(self.database_url) as connection:
            await connection.execute(
                "UPDATE media SET tmdb_status = 'Returning Series' WHERE id = ?",
                (watching_id,),
            )
        ongoing_filters = await update_user_library_filter(
            123,
            "ongoing",
            database_url=self.database_url,
        )
        ongoing_rows = await list_user_library(
            123,
            ongoing_filters,
            database_url=self.database_url,
        )
        self.assertEqual([row["title"] for row in ongoing_rows], ["Начато"])

    async def test_library_is_filtered_and_paginated_newest_first(self) -> None:
        for index in range(25):
            media_id = await self.create_media(
                tmdb_id=index + 1,
                content_format="series" if index % 2 else "full_length",
                content_type="anime" if index % 3 == 0 else "movie",
                title=f"Title {index + 1}",
            )
            await self.create_user_media(
                user_id=123,
                media_id=media_id,
                status="completed",
            )

        filters = await get_user_library_filters(123, database_url=self.database_url)
        first_page = await list_user_library(
            123,
            filters,
            limit=20,
            database_url=self.database_url,
        )
        second_page = await list_user_library(
            123,
            filters,
            limit=20,
            offset=20,
            database_url=self.database_url,
        )
        filters["series"] = False
        full_length_only = await list_user_library(
            123,
            filters,
            database_url=self.database_url,
        )

        self.assertEqual(len(first_page), 20)
        self.assertEqual(first_page[0]["title"], "Title 25")
        self.assertEqual(len(second_page), 5)
        self.assertTrue(
            all(row["content_format"] == "full_length" for row in full_length_only)
        )

    async def test_library_can_be_sorted_by_user_then_tmdb_rating(self) -> None:
        entries = (
            (101, "Мой фаворит", 7.0, 10),
            (102, "Второе место", 9.5, 8),
            (103, "Без моей оценки", 9.9, None),
        )
        for tmdb_id, title, tmdb_rating, user_rating in entries:
            media_id = await self.create_media(
                tmdb_id=tmdb_id,
                content_format="full_length",
                content_type="movie",
                title=title,
                rating=tmdb_rating,
            )
            await self.create_user_media(
                user_id=123,
                media_id=media_id,
                status="completed",
                user_rating=user_rating,
            )

        filters = await get_user_library_filters(123, database_url=self.database_url)
        rows = await list_user_library(
            123,
            filters,
            sort_order="rating",
            database_url=self.database_url,
        )

        self.assertEqual(
            [row["title"] for row in rows],
            ["Мой фаворит", "Второе место", "Без моей оценки"],
        )

        with self.assertRaisesRegex(ValueError, "sort order"):
            await list_user_library(
                123,
                filters,
                sort_order="unknown",
                database_url=self.database_url,
            )

    async def test_library_item_belongs_to_requested_user(self) -> None:
        media_id = await self.create_media(
            tmdb_id=42,
            content_format="full_length",
            content_type="movie",
            title="Private title",
        )
        await self.create_user_media(
            user_id=123,
            media_id=media_id,
            status="completed",
        )

        own_item = await get_user_library_item(
            123,
            media_id,
            database_url=self.database_url,
        )
        other_item = await get_user_library_item(
            456,
            media_id,
            database_url=self.database_url,
        )

        self.assertEqual(own_item["title"], "Private title")
        self.assertIsNone(other_item)
