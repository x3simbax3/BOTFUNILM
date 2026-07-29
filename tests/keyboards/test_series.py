from src import keyboards
from tests.support.keyboards import KeyboardTestCase, callback_rows


class SeriesKeyboardTests(KeyboardTestCase):
    def test_season_list_can_mark_every_season_watched(self) -> None:
        keyboard = keyboards.season_list_keyboard(
            [{"season_number": 1, "name": "Сезон 1", "episode_count": 8}],
            {},
        )

        self.assert_callback_rows(
            keyboard,
            [["season:all"], ["season:1"], ["season:done"]],
        )

    def test_future_season_is_not_selectable(self) -> None:
        keyboard = keyboards.season_list_keyboard(
            [
                {
                    "season_number": 2,
                    "name": "Сезон 2",
                    "episode_count": 0,
                    "announced_episode_count": 12,
                }
            ],
            {},
        )

        self.assert_callback_rows(
            keyboard,
            [["season:all"], ["ep:noop"], ["season:done"]],
        )

    def test_episode_keyboard_has_back_button(self) -> None:
        self.assert_callback_rows(
            keyboards.episodes_keyboard(3, 2),
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

    def test_episode_keyboard_paginates_by_fifty(self) -> None:
        first_page = keyboards.episodes_keyboard(120, 2)
        second_page = keyboards.episodes_keyboard(120, 2, page=1)
        last_page = keyboards.episodes_keyboard(120, 2, page=2)

        self.assertEqual(callback_rows(first_page)[1][0], "ep:2:1")
        self.assertEqual(callback_rows(first_page)[10][-1], "ep:2:50")
        self.assertEqual(
            callback_rows(first_page)[11],
            ["ep:noop", "ep:noop", "ep:page:1"],
        )
        self.assertEqual(callback_rows(second_page)[1][0], "ep:2:51")
        self.assertEqual(callback_rows(second_page)[10][-1], "ep:2:100")
        self.assertEqual(
            callback_rows(second_page)[11],
            ["ep:page:0", "ep:noop", "ep:page:2"],
        )
        self.assertEqual(callback_rows(last_page)[1][0], "ep:2:101")
        self.assertEqual(callback_rows(last_page)[4][-1], "ep:2:120")
        self.assertEqual(
            callback_rows(last_page)[5],
            ["ep:page:1", "ep:noop", "ep:noop"],
        )
        self.assertEqual(
            [button.text for button in second_page.inline_keyboard[11]],
            ["‹", "2/3", "›"],
        )
