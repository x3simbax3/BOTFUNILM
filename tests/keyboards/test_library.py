from src import keyboards
from tests.support.keyboards import KeyboardTestCase


class LibraryKeyboardTests(KeyboardTestCase):
    def test_library_keyboard_has_filters_and_pagination(self) -> None:
        filters = {
            "series": True,
            "full_length": False,
            "anime": True,
            "movie": True,
            "cartoon": True,
            "completed": True,
            "planned": False,
            "unfinished": False,
            "ongoing": False,
        }

        keyboard = keyboards.library_keyboard(filters, page=1, has_more=True)

        self.assert_callback_rows(
            keyboard,
            [
                ["library:filter:all"],
                [
                    "library:filters:format",
                    "library:filters:format",
                ],
                ["library:filters:category", "library:filters:category"],
                ["library:filters:status", "library:filters:status"],
                ["library:filters:sort", "library:filters:sort"],
                ["library:page:0", "library:page:2"],
                ["back:main"],
            ],
        )
        self.assertEqual(
            keyboard.inline_keyboard[1][0].text,
            "▤\u00a0Формат",
        )
        self.assertEqual(
            keyboard.inline_keyboard[1][1].text,
            "Сериал",
        )
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
        self.assertEqual(keyboard.inline_keyboard[1][0].text, "▤\u00a0Формат")
        self.assertEqual(
            keyboard.inline_keyboard[2][0].text,
            "◇\u00a0Категория",
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
        self.assertEqual(
            keyboard.inline_keyboard[1][0].text,
            "▤\u00a0Формат",
        )
        self.assertEqual(
            keyboard.inline_keyboard[1][1].text,
            "Сериал",
        )
        self.assertEqual(
            keyboard.inline_keyboard[2][1].text,
            "Аниме",
        )

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

        self.assertEqual(
            keyboard.inline_keyboard[4][1].text,
            "Моя оценка",
        )

    def test_category_filter_is_wrapped_in_submenu(self) -> None:
        filters = {
            "movie": False,
            "anime": True,
            "cartoon": False,
        }

        keyboard = keyboards.library_keyboard(
            filters,
            page=0,
            has_more=False,
            filter_group="category",
        )

        self.assert_callback_rows(
            keyboard,
            [
                ["library:filter:category_all"],
                ["library:filter:movie"],
                ["library:filter:anime"],
                ["library:filter:cartoon"],
                ["library:filters:back"],
            ],
        )
        self.assertEqual(keyboard.inline_keyboard[2][0].text, "✓\u00a0Аниме")

    def test_all_category_marks_only_the_all_button(self) -> None:
        keyboard = keyboards.library_keyboard(
            {"movie": True, "anime": True, "cartoon": True},
            page=0,
            has_more=False,
            filter_group="category",
        )

        labels = [button.text for row in keyboard.inline_keyboard for button in row]
        self.assertEqual(
            [label for label in labels if label.startswith("✓")],
            ["✓\u00a0Все"],
        )

    def test_planned_library_item_has_management_actions(self) -> None:
        self.assert_callback_rows(
            keyboards.library_item_keyboard(planned=True),
            [
                ["library:item:watched"],
                ["library:item:edit", "library:item:delete"],
                ["library:back"],
            ],
        )

    def test_series_edit_menu_can_change_rating_and_progress(self) -> None:
        self.assert_callback_rows(
            keyboards.library_edit_keyboard(series=True),
            [
                ["library:item:edit:rating"],
                ["library:item:edit:progress"],
                ["library:item:edit:back"],
            ],
        )
