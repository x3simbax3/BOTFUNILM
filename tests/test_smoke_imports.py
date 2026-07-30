import os
import sys
import unittest


class SmokeImportTests(unittest.TestCase):
    def setUp(self) -> None:
        self._orig_token = os.environ.get("BOT_TOKEN")
        os.environ["BOT_TOKEN"] = ""

        modules_to_reload = [
            k for k in list(sys.modules) if k.startswith(("src", "config"))
        ]
        for mod in modules_to_reload:
            del sys.modules[mod]

    def tearDown(self) -> None:
        if self._orig_token is not None:
            os.environ["BOT_TOKEN"] = self._orig_token
        else:
            os.environ.pop("BOT_TOKEN", None)

    def test_import_src_bot(self) -> None:
        import src.bot  # noqa: F401

    def test_import_src_routers(self) -> None:
        import src.routers  # noqa: F401

    def test_import_src_handlers(self) -> None:
        import src.handlers  # noqa: F401

    def test_router_contains_domain_routers(self) -> None:
        from src.handlers.errors import router as errors_router
        from src.handlers.library import router as library_router
        from src.handlers.menu import router as menu_router
        from src.handlers.rating import router as rating_router
        from src.handlers.search import router as search_router
        from src.handlers.series import router as series_router
        from src.handlers.tracking import router as tracking_router
        from src.routers import router

        sub_names = {r.name for r in router.sub_routers}
        self.assertEqual(
            sub_names,
            {
                errors_router.name,
                library_router.name,
                menu_router.name,
                rating_router.name,
                search_router.name,
                series_router.name,
                tracking_router.name,
            },
        )


if __name__ == "__main__":
    unittest.main()
