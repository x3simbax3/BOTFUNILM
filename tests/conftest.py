from pathlib import Path

import pytest


def pytest_collection_modifyitems(items: list[pytest.Item]) -> None:
    for item in items:
        path = Path(str(item.path))
        if "integration" in path.parts:
            item.add_marker(pytest.mark.integration)
        if "load" in path.parts:
            item.add_marker(pytest.mark.load)
