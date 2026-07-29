from src.database.ratings import get_user_rating_details
from src.database.user_media import (
    delete_user_media,
    get_user_media,
    update_user_media_rating,
)
from tests.support.database import DatabaseTestCase


class RatingTests(DatabaseTestCase):
    async def test_detailed_ratings_are_saved_and_replaced(self) -> None:
        media_id = await self.create_media(
            tmdb_id=143,
            content_format="full_length",
            content_type="movie",
            title="Rated movie",
        )
        initial_ratings = {
            "acting": 8,
            "story": 7,
            "visuals": 9,
            "sound": 8,
            "overall": 9,
        }
        await self.create_user_media(
            user_id=123,
            media_id=media_id,
            status="completed",
            user_rating=8,
            rating_details=initial_ratings,
        )

        self.assertEqual(
            await get_user_rating_details(
                123, media_id, database_url=self.database_url
            ),
            initial_ratings,
        )

        replacement = {
            "animation": 10,
            "story": 8,
            "characters": 9,
            "sound": 7,
            "overall": 9,
        }
        self.assertTrue(
            await update_user_media_rating(
                123,
                media_id,
                9,
                rating_details=replacement,
                database_url=self.database_url,
            )
        )
        self.assertEqual(
            await get_user_rating_details(
                123, media_id, database_url=self.database_url
            ),
            replacement,
        )

    async def test_invalid_detailed_rating_rolls_back_average_and_details(self) -> None:
        media_id = await self.create_media(
            tmdb_id=144,
            content_format="full_length",
            content_type="movie",
            title="Rated movie",
        )
        await self.create_user_media(
            user_id=123,
            media_id=media_id,
            status="completed",
            user_rating=7,
            rating_details={"overall": 7},
        )

        with self.assertRaises(ValueError):
            await update_user_media_rating(
                123,
                media_id,
                10,
                rating_details={"unknown": 10},
                database_url=self.database_url,
            )

        media = await get_user_media(123, media_id, database_url=self.database_url)
        self.assertEqual(media["user_rating"], 7)
        self.assertEqual(
            await get_user_rating_details(
                123, media_id, database_url=self.database_url
            ),
            {"overall": 7},
        )

    async def test_deleting_user_media_cascades_to_detailed_ratings(self) -> None:
        media_id = await self.create_media(
            tmdb_id=145,
            content_format="full_length",
            content_type="movie",
            title="Rated movie",
        )
        await self.create_user_media(
            user_id=123,
            media_id=media_id,
            status="completed",
            user_rating=8,
            rating_details={"overall": 8},
        )
        await delete_user_media(123, media_id, database_url=self.database_url)

        self.assertEqual(
            await get_user_rating_details(
                123, media_id, database_url=self.database_url
            ),
            {},
        )
