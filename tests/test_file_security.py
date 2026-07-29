import os
import tempfile
import unittest
from pathlib import Path

from src.file_security import verify_private_files


class PrivateFilePermissionTests(unittest.TestCase):
    def test_accepts_owner_only_permissions(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "secret"
            path.touch(mode=0o600)

            verify_private_files((path,))

    def test_rejects_group_or_other_permissions(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "secret"
            path.touch(mode=0o600)
            os.chmod(path, 0o664)

            with self.assertRaisesRegex(PermissionError, "chmod 600"):
                verify_private_files((path,))

    def test_ignores_files_that_do_not_exist_yet(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            verify_private_files((Path(directory) / "future.db",))


if __name__ == "__main__":
    unittest.main()
