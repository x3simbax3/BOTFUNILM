import unittest

from src.callback_data import (
    BackCallback,
    EpisodeCallback,
    EpisodePageCallback,
    FormatCallback,
    TypeCallback,
    parse_back_callback,
    parse_badge_callback,
    parse_episode_callback,
    parse_format_callback,
    parse_library_filter_callback,
    parse_library_filter_group_callback,
    parse_library_page_callback,
    parse_library_sort_callback,
    parse_rating_callback,
    parse_season_callback,
    parse_type_callback,
)


class CallbackDataTests(unittest.TestCase):
    def test_parses_valid_symbolic_callbacks(self) -> None:
        self.assertEqual(
            parse_format_callback("format:add:series"),
            FormatCallback("add", "series"),
        )
        self.assertEqual(
            parse_type_callback("type:add:full_length:movie"),
            TypeCallback("add", "full_length", "movie"),
        )
        self.assertEqual(
            parse_back_callback("back:content_type:add:series"),
            BackCallback("content_type", ("add", "series")),
        )
        self.assertEqual(
            parse_library_filter_callback("library:filter:anime"),
            "anime",
        )
        self.assertEqual(
            parse_library_filter_callback("library:filter:planned"),
            "planned",
        )
        self.assertEqual(
            parse_library_filter_callback("library:filter:dropped"),
            "dropped",
        )
        self.assertEqual(parse_library_sort_callback("library:sort:rating"), "rating")
        self.assertEqual(parse_library_sort_callback("library:sort:recent"), "recent")
        self.assertEqual(
            parse_library_filter_group_callback("library:filters:category"),
            "category",
        )
        self.assertEqual(
            parse_library_sort_callback("library:sort:tmdb_rating"),
            "tmdb_rating",
        )

    def test_rejects_unknown_values_and_extra_segments(self) -> None:
        invalid_callbacks = (
            (parse_format_callback, "format:delete:series"),
            (parse_format_callback, "format:add:series:extra"),
            (parse_type_callback, "type:add:series:documentary"),
            (parse_type_callback, "type:add:series:movie:extra"),
            (parse_back_callback, "back:main:extra"),
            (parse_back_callback, "back:format"),
            (parse_back_callback, "back:content_type:add:unknown"),
            (parse_library_filter_callback, "library:filter:unknown"),
            (parse_library_filter_callback, "library:filter:anime:extra"),
            (parse_library_sort_callback, "library:sort:unknown"),
            (parse_library_sort_callback, "library:sort:rating:extra"),
            (parse_library_filter_group_callback, "library:filters:unknown"),
        )
        for parser, value in invalid_callbacks:
            with self.subTest(value=value):
                self.assertIsNone(parser(value))

    def test_parses_valid_numeric_callbacks(self) -> None:
        self.assertEqual(parse_library_page_callback("library:page:0"), 0)
        self.assertEqual(parse_library_page_callback("library:page:100000"), 100_000)
        self.assertEqual(parse_rating_callback("rate:10"), 10)
        self.assertEqual(parse_badge_callback("rating_badge:top"), "top")
        self.assertEqual(parse_badge_callback("library_badge:none"), "none")
        self.assertEqual(parse_season_callback("season:1"), 1)
        self.assertEqual(parse_season_callback("season:done"), "done")
        self.assertEqual(parse_season_callback("season:all"), "all")
        self.assertEqual(
            parse_episode_callback("ep:12:34"),
            EpisodeCallback(12, 34),
        )
        self.assertEqual(parse_episode_callback("ep:done"), "done")
        self.assertEqual(parse_episode_callback("ep:back"), "back")
        self.assertEqual(parse_episode_callback("ep:noop"), "noop")
        self.assertEqual(
            parse_episode_callback("ep:page:2"),
            EpisodePageCallback(page=2),
        )

    def test_rejects_noncanonical_or_out_of_range_numbers(self) -> None:
        invalid_callbacks = (
            (parse_library_page_callback, "library:page:-1"),
            (parse_library_page_callback, "library:page:+1"),
            (parse_library_page_callback, "library:page:01"),
            (parse_library_page_callback, "library:page:100001"),
            (parse_rating_callback, "rate:0"),
            (parse_rating_callback, "rate:01"),
            (parse_rating_callback, "rate:11"),
            (parse_rating_callback, "rate:1:extra"),
            (parse_badge_callback, "rating_badge:unknown"),
            (parse_badge_callback, "badge:top"),
            (parse_season_callback, "season:-1"),
            (parse_season_callback, "season:0"),
            (parse_season_callback, "season:01"),
            (parse_season_callback, "season:10001"),
            (parse_episode_callback, "ep:-1:2"),
            (parse_episode_callback, "ep:0:2"),
            (parse_episode_callback, "ep:1:-2"),
            (parse_episode_callback, "ep:1:0"),
            (parse_episode_callback, "ep:01:2"),
            (parse_episode_callback, "ep:1:100001"),
            (parse_episode_callback, "ep:done:extra"),
            (parse_episode_callback, "ep:page:01"),
        )
        for parser, value in invalid_callbacks:
            with self.subTest(value=value):
                self.assertIsNone(parser(value))


if __name__ == "__main__":
    unittest.main()
