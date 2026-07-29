import logging
import unittest

from src.logging_config import safe_exception_info


class SafeLoggingTests(unittest.TestCase):
    def test_exception_traceback_redacts_exception_message(self) -> None:
        private_value = "private " + "user input"
        try:
            raise ValueError(private_value)
        except ValueError as exception:
            rendered = logging.Formatter().formatException(
                safe_exception_info(exception)
            )

        self.assertIn("ValueError", rendered)
        self.assertNotIn(private_value, rendered)


if __name__ == "__main__":
    unittest.main()
