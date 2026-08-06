import os
import subprocess
import sys
import unittest


class SmokeImportTests(unittest.TestCase):
    def assert_imports_in_fresh_process(self, module: str) -> None:
        environment = os.environ.copy()
        environment["BOT_TOKEN"] = ""
        result = subprocess.run(
            [sys.executable, "-c", f"import {module}"],
            check=False,
            capture_output=True,
            text=True,
            env=environment,
        )
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_import_src_bot(self) -> None:
        self.assert_imports_in_fresh_process("src.bot")

    def test_import_src_routers(self) -> None:
        self.assert_imports_in_fresh_process("src.routers")

    def test_import_src_handlers(self) -> None:
        self.assert_imports_in_fresh_process("src.handlers")

    def test_router_contains_domain_routers(self) -> None:
        from src.handlers.admin import router as admin_router
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
                admin_router.name,
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
