"""Permission checks for files containing credentials or private user data."""

import stat
from collections.abc import Iterable
from pathlib import Path


def verify_private_files(paths: Iterable[Path]) -> None:
    """Reject existing files readable or writable by group/other users."""
    for path in paths:
        try:
            file_stat = path.stat()
        except FileNotFoundError:
            continue

        if not stat.S_ISREG(file_stat.st_mode):
            raise PermissionError(f"Sensitive path is not a regular file: {path}")

        mode = stat.S_IMODE(file_stat.st_mode)
        if mode & 0o077:
            raise PermissionError(
                f"Unsafe permissions {mode:03o} on {path}; run: chmod 600 {path}"
            )
