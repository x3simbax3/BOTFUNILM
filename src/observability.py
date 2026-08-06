"""Minimal Prometheus-compatible metrics and dependency health endpoint."""

from __future__ import annotations

import asyncio
import json
import time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

from redis.asyncio import Redis
from redis.exceptions import RedisError

from config.config import DATABASE_URL, REDIS_URL
from src.admin_runtime import ADMIN_JOB_QUEUE, MEDIA_WORKER_HEARTBEAT
from src.database.connection import connect_database, database_path

_api_errors: Counter[tuple[str, str]] = Counter()


def record_api_error(provider: str, error: BaseException) -> None:
    """Record a failed call without retaining request data or exception text."""
    _api_errors[(provider, type(error).__name__)] += 1


class ObservabilityServer:
    """Serve metrics and readiness from the application process."""

    def __init__(self, service: str, *, port: int = 8000) -> None:
        self.service = service
        self.port = port
        self.started_at = time.time()
        self._server: asyncio.AbstractServer | None = None

    async def start(self) -> None:
        self._server = await asyncio.start_server(
            self._handle_connection,
            host="0.0.0.0",
            port=self.port,
        )

    async def close(self) -> None:
        if self._server is not None:
            self._server.close()
            await self._server.wait_closed()
            self._server = None

    async def _handle_connection(
        self,
        reader: asyncio.StreamReader,
        writer: asyncio.StreamWriter,
    ) -> None:
        try:
            request = await asyncio.wait_for(reader.readline(), timeout=3)
            path = request.decode("ascii", errors="ignore").split(" ", 2)[1]
            if path == "/healthz":
                status = await _dependency_status()
                body = b"ok\n" if status.healthy else b"unhealthy\n"
                await _write_response(writer, 200 if status.healthy else 503, body)
            elif path == "/metrics":
                metrics = await _render_metrics(self.service, self.started_at)
                await _write_response(
                    writer,
                    200,
                    metrics.encode(),
                    content_type="text/plain; version=0.0.4",
                )
            else:
                await _write_response(writer, 404, b"not found\n")
        except (asyncio.TimeoutError, IndexError):
            await _write_response(writer, 400, b"bad request\n")
        finally:
            writer.close()
            await writer.wait_closed()


class _DependencyStatus:
    def __init__(
        self,
        *,
        database_up: bool,
        redis_up: bool,
        database_size: int,
        queued_jobs: int,
        heartbeat_age: float | None,
    ) -> None:
        self.database_up = database_up
        self.redis_up = redis_up
        self.database_size = database_size
        self.queued_jobs = queued_jobs
        self.heartbeat_age = heartbeat_age

    @property
    def healthy(self) -> bool:
        return self.database_up and (not REDIS_URL or self.redis_up)


async def _dependency_status() -> _DependencyStatus:
    database_up = False
    database_size = 0
    try:
        path = Path(database_path(DATABASE_URL))
        database_size = path.stat().st_size
        connection = await connect_database(DATABASE_URL)
        try:
            await connection.execute("SELECT 1")
        finally:
            await connection.close()
        database_up = True
    except Exception:
        pass

    if not REDIS_URL:
        return _DependencyStatus(
            database_up=database_up,
            redis_up=True,
            database_size=database_size,
            queued_jobs=0,
            heartbeat_age=None,
        )

    redis_up = False
    queued_jobs = 0
    heartbeat_age: float | None = None
    redis = Redis.from_url(REDIS_URL, decode_responses=True)
    try:
        if await redis.ping():
            redis_up = True
            queued_jobs = int(await redis.llen(ADMIN_JOB_QUEUE))
            heartbeat_age = _heartbeat_age(await redis.get(MEDIA_WORKER_HEARTBEAT))
    except (RedisError, OSError):
        pass
    finally:
        await redis.aclose()

    return _DependencyStatus(
        database_up=database_up,
        redis_up=redis_up,
        database_size=database_size,
        queued_jobs=queued_jobs,
        heartbeat_age=heartbeat_age,
    )


def _heartbeat_age(value: str | None) -> float | None:
    try:
        updated_at = json.loads(value or "{}").get("updated_at")
        if not isinstance(updated_at, str):
            return None
        timestamp = datetime.fromisoformat(updated_at).astimezone(timezone.utc)
    except (TypeError, ValueError, json.JSONDecodeError):
        return None
    return max(0.0, time.time() - timestamp.timestamp())


async def _render_metrics(service: str, started_at: float) -> str:
    status = await _dependency_status()
    labels = f'service="{service}"'
    lines = [
        "# HELP botfunilm_process_up Application process is serving metrics.",
        "# TYPE botfunilm_process_up gauge",
        f"botfunilm_process_up{{{labels}}} 1",
        "# HELP botfunilm_process_start_time_seconds Unix start time of the process.",
        "# TYPE botfunilm_process_start_time_seconds gauge",
        f"botfunilm_process_start_time_seconds{{{labels}}} {started_at}",
        "# HELP botfunilm_database_up SQLite readiness status.",
        "# TYPE botfunilm_database_up gauge",
        f"botfunilm_database_up{{{labels}}} {int(status.database_up)}",
        "# HELP botfunilm_sqlite_database_size_bytes SQLite database file size.",
        "# TYPE botfunilm_sqlite_database_size_bytes gauge",
        f"botfunilm_sqlite_database_size_bytes{{{labels}}} {status.database_size}",
        "# HELP botfunilm_redis_up Redis readiness status.",
        "# TYPE botfunilm_redis_up gauge",
        f"botfunilm_redis_up{{{labels}}} {int(status.redis_up)}",
        "# HELP botfunilm_admin_job_queue_length Pending admin jobs in Redis.",
        "# TYPE botfunilm_admin_job_queue_length gauge",
        f"botfunilm_admin_job_queue_length{{{labels}}} {status.queued_jobs}",
        "# HELP botfunilm_media_worker_heartbeat_age_seconds Age of worker heartbeat.",
        "# TYPE botfunilm_media_worker_heartbeat_age_seconds gauge",
        f"botfunilm_media_worker_heartbeat_age_seconds{{{labels}}} "
        f"{status.heartbeat_age if status.heartbeat_age is not None else '+Inf'}",
        "# HELP botfunilm_api_errors_total Failed external API calls.",
        "# TYPE botfunilm_api_errors_total counter",
    ]
    for (provider, error), value in sorted(_api_errors.items()):
        lines.append(
            "botfunilm_api_errors_total{"
            f'service="{service}",provider="{provider}",error="{error}"}} {value}'
        )
    return "\n".join(lines) + "\n"


async def _write_response(
    writer: asyncio.StreamWriter,
    status: int,
    body: bytes,
    *,
    content_type: str = "text/plain; charset=utf-8",
) -> None:
    reason = {
        200: "OK",
        400: "Bad Request",
        404: "Not Found",
        503: "Service Unavailable",
    }[status]
    writer.write(
        (
            f"HTTP/1.1 {status} {reason}\r\n"
            f"Content-Type: {content_type}\r\n"
            f"Content-Length: {len(body)}\r\n"
            "Connection: close\r\n\r\n"
        ).encode()
        + body
    )
    await writer.drain()


__all__ = ("ObservabilityServer", "record_api_error")
