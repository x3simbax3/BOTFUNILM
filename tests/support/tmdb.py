import json
from collections.abc import Iterator
from contextlib import contextmanager
from unittest.mock import AsyncMock, patch

from src import tmdb_search, tmdb_series


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
        raw_body: bytes | None = None,
    ) -> None:
        self.status = status
        self.data = data or {}
        self.headers = headers or {}
        self.content = ContentStub(
            raw_body if raw_body is not None else json.dumps(self.data).encode()
        )
        self.content_length = len(raw_body) if raw_body is not None else None

    async def json(self, **kwargs) -> dict:
        return self.data


class ContentStub:
    def __init__(self, body: bytes) -> None:
        self.body = body

    async def read(self, size: int) -> bytes:
        chunk, self.body = self.body[:size], self.body[size:]
        return chunk


class SessionStub(AsyncContextStub):
    def __init__(self, response: ResponseStub | None = None, error=None) -> None:
        self.response = response
        self.error = error
        self.call_count = 0
        self.last_get_kwargs = None

    def get(self, *args, **kwargs):
        self.call_count += 1
        self.last_get_kwargs = kwargs
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
        patch.object(tmdb_search, "TMDB_API", "token"),
        patch.object(tmdb_series, "TMDB_API", "token"),
        patch.object(
            tmdb_search,
            "get_http_session",
            AsyncMock(return_value=SessionStub()),
        ),
        patch.object(
            tmdb_series,
            "get_http_session",
            AsyncMock(return_value=SessionStub()),
        ),
        patch.object(tmdb_search, "fetch_json", fetch_mock),
        patch.object(tmdb_series, "fetch_json", fetch_mock),
    ):
        yield fetch_mock
