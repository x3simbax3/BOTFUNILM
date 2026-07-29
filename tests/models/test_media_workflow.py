import unittest

from src.models import MediaWorkflowData, current_media_id


class MediaWorkflowDataTests(unittest.TestCase):
    def test_current_media_id_accepts_only_canonical_positive_ids(self) -> None:
        for value, expected in (
            (7, 7),
            ("7", 7),
            (0, None),
            (-1, None),
            (True, None),
            ("07", None),
            ("٧", None),
            (7.0, None),
        ):
            with self.subTest(value=value):
                self.assertEqual(current_media_id({"media_id": value}), expected)

    def test_candidate_round_trip_keeps_typed_workflow_fields(self) -> None:
        workflow = MediaWorkflowData.from_tmdb_candidate(
            {
                "media_id": "7",
                "tmdb_id": 42,
                "title": "Матрица",
                "overview": "Описание",
                "poster_path": "/poster.jpg",
                "rating": 8.7,
                "original_title": "The Matrix",
                "release_date": "1999-03-31",
            },
            content_format="full_length",
            content_type="movie",
        )

        restored = MediaWorkflowData.from_fsm(workflow.to_fsm_dict())

        self.assertEqual(restored, workflow)
        self.assertEqual(restored.media_id, 7)
        self.assertEqual(restored.tmdb_id, 42)

    def test_library_item_maps_series_release_date(self) -> None:
        workflow = MediaWorkflowData.from_library_item(
            {
                "id": 7,
                "tmdb_id": 42,
                "title": "Сериал",
                "description": None,
                "poster_path": None,
                "original_title": None,
                "release_date": None,
                "first_air_date": "2026-01-01",
                "rating": None,
                "content_format": "series",
                "content_type": "anime",
            }
        )

        self.assertEqual(workflow.tmdb_release_date, "2026-01-01")
        self.assertEqual(workflow.content_format, "series")


if __name__ == "__main__":
    unittest.main()
