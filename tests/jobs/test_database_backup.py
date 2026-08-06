import sqlite3
import tempfile
import unittest
from datetime import datetime, time
from pathlib import Path
from zoneinfo import ZoneInfo

from src.jobs.database_backup import backup_path, create_backup, next_backup_run


class DatabaseBackupTests(unittest.TestCase):
    def test_backup_replaces_weekday_slot_and_can_be_restored(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            database_file = root / "bot.db"
            backup_file = backup_path(
                root / "backups", datetime(2026, 8, 3, tzinfo=ZoneInfo("UTC"))
            )
            with sqlite3.connect(database_file) as database:
                database.execute("CREATE TABLE entries (value TEXT NOT NULL)")
                database.execute("INSERT INTO entries VALUES ('first')")

            create_backup(database_file, backup_file)

            with sqlite3.connect(database_file) as database:
                database.execute("INSERT INTO entries VALUES ('second')")
            create_backup(database_file, backup_file)

            self.assertEqual(backup_file.name, "bot-mon.db")
            with sqlite3.connect(backup_file) as restored:
                values = restored.execute("SELECT value FROM entries ORDER BY value").fetchall()
            self.assertEqual(values, [("first",), ("second",)])

    def test_next_backup_run_moves_to_tomorrow_after_scheduled_time(self) -> None:
        timezone = ZoneInfo("Europe/Moscow")
        target = next_backup_run(
            datetime(2026, 8, 3, 4, tzinfo=timezone), time(3, 30), timezone
        )

        self.assertEqual(target, datetime(2026, 8, 4, 3, 30, tzinfo=timezone))
