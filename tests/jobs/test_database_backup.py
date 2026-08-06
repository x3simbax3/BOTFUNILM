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
                values = restored.execute(
                    "SELECT value FROM entries ORDER BY value"
                ).fetchall()
            self.assertEqual(values, [("first",), ("second",)])

    def test_backup_restores_to_a_new_working_database(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source_file = root / "source.db"
            backup_file = root / "backup.db"
            restored_file = root / "restored.db"
            with sqlite3.connect(source_file) as source:
                source.execute("PRAGMA foreign_keys = ON")
                source.execute("CREATE TABLE parent (id INTEGER PRIMARY KEY)")
                source.execute(
                    "CREATE TABLE child (parent_id INTEGER REFERENCES parent(id))"
                )
                source.execute("INSERT INTO parent VALUES (1)")
                source.execute("INSERT INTO child VALUES (1)")

            create_backup(source_file, backup_file)
            with (
                sqlite3.connect(backup_file) as backup,
                sqlite3.connect(restored_file) as restored,
            ):
                backup.backup(restored)

            with sqlite3.connect(restored_file) as restored:
                restored.execute("PRAGMA foreign_keys = ON")
                self.assertEqual(
                    restored.execute("PRAGMA integrity_check").fetchone(), ("ok",)
                )
                self.assertEqual(
                    restored.execute("SELECT parent_id FROM child").fetchall(), [(1,)]
                )
                with self.assertRaises(sqlite3.IntegrityError):
                    restored.execute("INSERT INTO child VALUES (999)")

    def test_next_backup_run_moves_to_tomorrow_after_scheduled_time(self) -> None:
        timezone = ZoneInfo("Europe/Moscow")
        target = next_backup_run(
            datetime(2026, 8, 3, 4, tzinfo=timezone), time(3, 30), timezone
        )

        self.assertEqual(target, datetime(2026, 8, 4, 3, 30, tzinfo=timezone))
