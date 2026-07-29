from collections.abc import Iterator
from contextlib import contextmanager
from unittest.mock import AsyncMock, patch

from src import tmdb


class AsyncContextStub:
    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, traceback) -> None:
        pass


class ResponseStub(AsyncContextStub):
    def __init__(
        self,
        status: int,
        data: dict | None = None,
        headers: dict[str, str] | None = None,
    ) -> None:
        self.status = status
        self.data = data or {}
        self.headers = headers or {}

    async def json(self, **kwargs) -> dict:
        return self.data


class SessionStub(AsyncContextStub):
    def __init__(self, response: ResponseStub | None = None, error=None) -> None:
        self.response = response
        self.error = error
        self.call_count = 0

    def get(self, *args, **kwargs):
        self.call_count += 1
        if self.error:
            raise self.error
        return self.response


@contextmanager
def mock_tmdb_api(
    data: dict | None = None,
    *,
    fetch: AsyncMock | None = None,
) -> Iterator[AsyncMock]:
    fetch_mock = fetch or AsyncMock(return_value=data)
    with (
        patch.object(tmdb, "TMDB_API", "token"),
        patch.object(
            tmdb,
            "get_http_session",
            AsyncMock(return_value=SessionStub()),
        ),
        patch.object(tmdb, "_fetch_json", fetch_mock),
    ):
        yield fetch_mock
