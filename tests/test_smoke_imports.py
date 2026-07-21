import importlib
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

    def test_router_contains_start_router(self) -> None:
        from src.routers import router
        from src.handlers import start_router

        sub_names = {r.name for r in router.sub_routers}
        self.assertIn(start_router.name, sub_names)


if __name__ == "__main__":
    unittest.main()
