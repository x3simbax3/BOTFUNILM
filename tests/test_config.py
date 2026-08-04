import unittest

from config.config import parse_admin_user_ids, validate_tmdb_url


class AdminUserIdsValidationTests(unittest.TestCase):
    def test_parses_multiple_unique_user_ids(self) -> None:
        self.assertEqual(
            parse_admin_user_ids("18738382, 188299, 18738382"),
            frozenset({18738382, 188299}),
        )

    def test_accepts_empty_value(self) -> None:
        self.assertEqual(parse_admin_user_ids(""), frozenset())

    def test_rejects_non_numeric_user_id(self) -> None:
        with self.assertRaisesRegex(ValueError, "integers"):
            parse_admin_user_ids("18738382, 18829к9")

    def test_rejects_zero(self) -> None:
        with self.assertRaisesRegex(ValueError, "positive"):
            parse_admin_user_ids("0")


class TmdbUrlValidationTests(unittest.TestCase):
    allowed_hosts = frozenset({"api.themoviedb.org", "proxy.example"})

    def test_accepts_https_url_on_allowed_host(self) -> None:
        self.assertEqual(
            validate_tmdb_url(
                "https://proxy.example/tmdb/",
                self.allowed_hosts,
            ),
            "https://proxy.example/tmdb",
        )

    def test_rejects_plain_http(self) -> None:
        with self.assertRaisesRegex(ValueError, "must use HTTPS"):
            validate_tmdb_url(
                "http://api.themoviedb.org/3",
                self.allowed_hosts,
            )

    def test_rejects_host_outside_allowlist(self) -> None:
        with self.assertRaisesRegex(ValueError, "TMDB_ALLOWED_HOSTS"):
            validate_tmdb_url(
                "https://attacker.example/3",
                self.allowed_hosts,
            )

    def test_rejects_credentials_in_url(self) -> None:
        with self.assertRaisesRegex(ValueError, "must not contain credentials"):
            validate_tmdb_url(
                "https://user:password@api.themoviedb.org/3",
                self.allowed_hosts,
            )

    def test_rejects_query_and_fragment(self) -> None:
        for suffix in ("?target=attacker.example", "#attacker.example"):
            with self.subTest(suffix=suffix):
                with self.assertRaisesRegex(ValueError, "query or fragment"):
                    validate_tmdb_url(
                        f"https://api.themoviedb.org/3{suffix}",
                        self.allowed_hosts,
                    )


if __name__ == "__main__":
    unittest.main()
