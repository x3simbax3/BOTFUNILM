import multiprocessing
import queue
import sqlite3
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path


def _run_updates(database_file: str, start, errors) -> None:
    def update() -> None:
        start.wait()
        try:
            with sqlite3.connect(database_file, timeout=15) as connection:
                connection.execute("PRAGMA busy_timeout = 15000")
                connection.execute("UPDATE counter SET value = value + 1")
        except Exception as exc:
            errors.put(repr(exc))

    with ThreadPoolExecutor(max_workers=16) as executor:
        list(executor.map(lambda _: update(), range(16)))


class SQLiteConcurrencyLoadTests(unittest.TestCase):
    def test_two_processes_complete_32_concurrent_updates(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            database_file = Path(directory) / "load.db"
            with sqlite3.connect(database_file) as connection:
                connection.execute("PRAGMA journal_mode = WAL")
                connection.execute("CREATE TABLE counter (value INTEGER NOT NULL)")
                connection.execute("INSERT INTO counter VALUES (0)")

            context = multiprocessing.get_context("spawn")
            start = context.Event()
            errors = context.Queue()
            processes = [
                context.Process(
                    target=_run_updates,
                    args=(str(database_file), start, errors),
                )
                for _ in range(2)
            ]
            for process in processes:
                process.start()
            start.set()
            for process in processes:
                process.join(timeout=30)
                self.assertEqual(process.exitcode, 0)

            failures = []
            while True:
                try:
                    failures.append(errors.get_nowait())
                except queue.Empty:
                    break
            self.assertEqual(failures, [])
            with sqlite3.connect(database_file) as connection:
                self.assertEqual(
                    connection.execute("SELECT value FROM counter").fetchone(), (32,)
                )
                self.assertEqual(
                    connection.execute("PRAGMA integrity_check").fetchone(), ("ok",)
                )
