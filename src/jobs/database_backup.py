"""Daily SQLite backups with restore verification."""

from __future__ import annotations

import argparse
import logging
import os
import sqlite3
import time as clock
from datetime import datetime, time, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo


logger = logging.getLogger(__name__)

DEFAULT_BACKUP_DIRECTORY = "/backups"
DEFAULT_BACKUP_TIME = "03:30"
WEEKDAY_NAMES = ("mon", "tue", "wed", "thu", "fri", "sat", "sun")


def _backup_time(value: str) -> time:
    try:
        return time.fromisoformat(value)
    except ValueError as exc:
        raise ValueError("BACKUP_TIME must use HH:MM format") from exc


def backup_path(backup_directory: Path, now: datetime) -> Path:
    """Return the rotating backup slot for the supplied weekday."""
    return backup_directory / f"bot-{WEEKDAY_NAMES[now.weekday()]}.db"


def _verify_restore(backup_file: Path) -> None:
    with sqlite3.connect(backup_file) as backup, sqlite3.connect(":memory:") as restored:
        backup.backup(restored)
        result = restored.execute("PRAGMA integrity_check").fetchone()

    if result != ("ok",):
        raise RuntimeError(f"Backup restore integrity check failed: {result!r}")


def create_backup(database_file: Path, backup_file: Path) -> None:
    """Create one consistent backup, verify its restoration, then publish it."""
    if not database_file.is_file():
        raise FileNotFoundError(f"SQLite database was not found: {database_file}")

    backup_file.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    temporary_file = backup_file.with_suffix(".tmp")
    temporary_file.unlink(missing_ok=True)

    try:
        with sqlite3.connect(database_file) as source, sqlite3.connect(
            temporary_file
        ) as destination:
            source.backup(destination)

        os.chmod(temporary_file, 0o600)
        _verify_restore(temporary_file)
        os.replace(temporary_file, backup_file)
    finally:
        temporary_file.unlink(missing_ok=True)


def next_backup_run(now: datetime, scheduled_time: time, timezone: ZoneInfo) -> datetime:
    """Return the next daily backup moment in the configured timezone."""
    local_now = now.astimezone(timezone)
    target = datetime.combine(local_now.date(), scheduled_time, tzinfo=timezone)
    if target <= local_now:
        target += timedelta(days=1)
    return target


def run_backup(database_file: Path, backup_directory: Path, now: datetime) -> Path:
    target = backup_path(backup_directory, now)
    create_backup(database_file, target)
    logger.info("SQLite backup and restore check completed: %s", target)
    return target


def run_scheduler(
    database_file: Path,
    backup_directory: Path,
    scheduled_time: time,
    timezone: ZoneInfo,
) -> None:
    while True:
        target = next_backup_run(datetime.now(timezone), scheduled_time, timezone)
        delay = max(0.0, (target - datetime.now(timezone)).total_seconds())
        logger.info(
            "Next SQLite backup scheduled: at=%s sleep_seconds=%s",
            target.isoformat(),
            round(delay),
        )
        clock.sleep(delay)
        run_backup(database_file, backup_directory, datetime.now(timezone))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "command", choices=("backup", "run"), nargs="?", default="run"
    )
    arguments = parser.parse_args()

    database_file = Path(os.environ.get("BACKUP_DATABASE_PATH", "/data/bot.db"))
    backup_directory = Path(
        os.environ.get("BACKUP_DIRECTORY", DEFAULT_BACKUP_DIRECTORY)
    )
    timezone = ZoneInfo(os.environ.get("BACKUP_TIMEZONE", os.environ.get("TZ", "UTC")))
    scheduled_time = _backup_time(os.environ.get("BACKUP_TIME", DEFAULT_BACKUP_TIME))

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    if arguments.command == "backup":
        run_backup(database_file, backup_directory, datetime.now(timezone))
        return
    run_scheduler(database_file, backup_directory, scheduled_time, timezone)


if __name__ == "__main__":
    main()
