import unittest

from aiogram.types import InlineKeyboardMarkup

from src import keyboards


def callback_rows(markup: InlineKeyboardMarkup) -> list[list[str]]:
    return [[button.callback_data for button in row] for row in markup.inline_keyboard]


class KeyboardsTests(unittest.TestCase):
    def test_main_menu_buttons_have_expected_callbacks(self) -> None:
        self.assertEqual(
            callback_rows(keyboards.main_menu_keyboard()),
            [["menu:library"], ["menu:add"]],
        )

    def test_library_keyboard_has_filters_and_pagination(self) -> None:
        filters = {
            "series": True,
            "full_length": False,
            "anime": True,
            "movie": True,
            "cartoon": True,
            "completed": True,
            "planned": False,
        }

        keyboard = keyboards.library_keyboard(filters, page=1, has_more=True)

        self.assertEqual(
            callback_rows(keyboard),
            [
                ["library:sort:recent", "library:sort:rating"],
                ["library:filter:series", "library:filter:full_length"],
                [
                    "library:filter:movie",
                    "library:filter:anime",
                    "library:filter:cartoon",
                ],
                ["library:filter:completed", "library:filter:planned"],
                ["library:filter:all"],
                ["library:page:0", "library:page:2"],
                ["back:main"],
            ],
        )
        self.assertEqual(keyboard.inline_keyboard[0][0].text, "✓\u00a0По дате")
        self.assertEqual(keyboard.inline_keyboard[1][0].text, "✓\u00a0Сериалы")
        self.assertEqual(keyboard.inline_keyboard[1][1].text, "Полный метр")
        self.assertEqual(
            [button.text for button in keyboard.inline_keyboard[-2]],
            ["‹\u00a0Пред. страница", "След. страница\u00a0›"],
        )

    def test_all_filter_marks_mandatory_sort_and_completed_status(self) -> None:
        filters = {
            "series": True,
            "full_length": True,
            "anime": True,
            "movie": True,
            "cartoon": True,
            "completed": True,
            "planned": False,
        }

        keyboard = keyboards.library_keyboard(filters, page=0, has_more=False)
        labels = [button.text for row in keyboard.inline_keyboard for button in row]

        self.assertEqual(
            [label for label in labels if label.startswith("✓")],
            ["✓\u00a0По дате", "✓\u00a0Просмотрено"],
        )

    def test_filter_groups_show_only_one_selected_option(self) -> None:
        keyboard = keyboards.library_keyboard(
            {
                "series": True,
                "full_length": False,
                "movie": False,
                "anime": True,
                "cartoon": False,
                "completed": False,
                "planned": True,
            },
            page=0,
            has_more=False,
        )
        labels = [button.text for row in keyboard.inline_keyboard for button in row]

        self.assertIn("✓\u00a0Сериалы", labels)
        self.assertIn("✓\u00a0Аниме", labels)
        self.assertNotIn("✓\u00a0Полный метр", labels)
        self.assertNotIn("✓\u00a0Кино", labels)
        self.assertNotIn("✓\u00a0Мультфильмы", labels)
        self.assertNotIn("✓\u00a0Просмотрено", labels)
        self.assertIn("✓\u00a0Хочу посмотреть", labels)

    def test_rating_sort_has_compact_selected_button(self) -> None:
        filters = {
            "series": True,
            "full_length": False,
            "anime": False,
            "movie": True,
            "cartoon": False,
            "completed": True,
            "planned": True,
        }

        keyboard = keyboards.library_keyboard(
            filters,
            page=0,
            has_more=False,
            sort_order="rating",
        )

        self.assertEqual(keyboard.inline_keyboard[0][1].text, "✓\u00a0По оценке")

    def test_format_buttons_have_expected_callbacks_and_back_to_main(self) -> None:
        self.assertEqual(
            callback_rows(keyboards.format_keyboard("add")),
            [
                ["format:add:full_length", "format:add:series"],
                ["back:main"],
            ],
        )

    def test_content_type_buttons_have_expected_callbacks_and_back_to_format(
        self,
    ) -> None:
        self.assertEqual(
            callback_rows(keyboards.content_type_keyboard("add", "series")),
            [
                ["type:add:series:movie"],
                ["type:add:series:anime"],
                ["type:add:series:cartoon"],
                ["back:format:add"],
            ],
        )

    def test_selected_type_back_returns_to_content_type_step(self) -> None:
        self.assertEqual(
            callback_rows(keyboards.selected_type_keyboard("add", "full_length")),
            [["back:content_type:add:full_length"]],
        )

    def test_tmdb_guess_buttons_have_expected_callbacks(self) -> None:
        self.assertEqual(
            callback_rows(keyboards.tmdb_guess_keyboard()),
            [["tmdb_guess:yes", "tmdb_guess:no"]],
        )

    def test_tmdb_guess_carousel_has_navigation(self) -> None:
        keyboard = keyboards.tmdb_guess_keyboard(position=1, total=5)

        self.assertEqual(
            callback_rows(keyboard),
            [
                [
                    "tmdb_guess:previous",
                    "tmdb_guess:position",
                    "tmdb_guess:next",
                ],
                ["tmdb_guess:yes", "tmdb_guess:no"],
            ],
        )
        self.assertEqual(keyboard.inline_keyboard[0][1].text, "2 / 5")

    def test_watch_status_buttons_have_expected_callbacks(self) -> None:
        self.assertEqual(
            callback_rows(keyboards.watch_status_keyboard()),
            [["watch_status:completed"], ["watch_status:planned"]],
        )

    def test_planned_library_item_has_management_actions(self) -> None:
        self.assertEqual(
            callback_rows(keyboards.library_item_keyboard(planned=True)),
            [
                ["library:item:watched"],
                ["library:item:edit", "library:item:delete"],
                ["library:back"],
            ],
        )

    def test_series_edit_menu_can_change_rating_and_progress(self) -> None:
        self.assertEqual(
            callback_rows(keyboards.library_edit_keyboard(series=True)),
            [
                ["library:item:edit:rating"],
                ["library:item:edit:progress"],
                ["library:item:edit:back"],
            ],
        )

    def test_season_list_can_mark_every_season_watched(self) -> None:
        keyboard = keyboards.season_list_keyboard(
            [{"season_number": 1, "name": "Сезон 1", "episode_count": 8}],
            {},
        )

        self.assertEqual(
            callback_rows(keyboard),
            [["season:all"], ["season:1"], ["season:done"]],
        )

    def test_rating_keyboard_has_back_button(self) -> None:
        self.assertEqual(
            callback_rows(keyboards.rating_keyboard()),
            [
                ["rate:1", "rate:2", "rate:3", "rate:4", "rate:5"],
                ["rate:6", "rate:7", "rate:8", "rate:9", "rate:10"],
                ["rating:back"],
            ],
        )

    def test_tmdb_retry_with_context_returns_to_selected_content_type(self) -> None:
        self.assertEqual(
            callback_rows(keyboards.tmdb_retry_keyboard("add", "full_length")),
            [
                ["title:retry"],
                ["back:content_type:add:full_length"],
            ],
        )

    def test_tmdb_retry_without_context_returns_to_content_type_step(self) -> None:
        self.assertEqual(
            callback_rows(keyboards.tmdb_retry_keyboard()),
            [
                ["title:retry"],
                ["back:content_type"],
            ],
        )

    def test_episode_keyboard_has_back_button(self) -> None:
        self.assertEqual(
            callback_rows(keyboards.episodes_keyboard(3, 2)),
            [
                ["ep:2:3"],
                ["ep:2:1", "ep:2:2", "ep:2:3"],
                ["ep:back", "ep:done"],
            ],
        )
        self.assertEqual(
            keyboards.episodes_keyboard(3, 2).inline_keyboard[0][0].text,
            "✓\u00a0Все серии",
        )


if __name__ == "__main__":
    unittest.main()
