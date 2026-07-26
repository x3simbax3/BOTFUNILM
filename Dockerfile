FROM arigaio/atlas:latest AS atlas

FROM python:3.10-slim-trixie AS base

COPY --from=ghcr.io/astral-sh/uv:0.11.32 /uv /uvx /bin/
COPY --from=atlas /atlas /usr/local/bin/atlas

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    PATH="/app/.venv/bin:$PATH"

WORKDIR /app

COPY pyproject.toml uv.lock README.md LICENSE ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --locked --no-dev --no-install-project

FROM base AS test

COPY config ./config
COPY migrations ./migrations
COPY src ./src
COPY tests ./tests

RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --locked --all-groups --no-editable

CMD ["pytest", "-q", "-n", "1"]

FROM base AS runtime

COPY config ./config
COPY migrations ./migrations
COPY src ./src
COPY docker-entrypoint.sh ./docker-entrypoint.sh

RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --locked --no-dev --no-editable \
    && useradd --system --uid 10001 --create-home botfunilm \
    && mkdir -p /data/media/posters \
    && chown -R botfunilm:botfunilm /data \
    && chmod +x /app/docker-entrypoint.sh

USER botfunilm

VOLUME ["/data"]

ENTRYPOINT ["/app/docker-entrypoint.sh"]
