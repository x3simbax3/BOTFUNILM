FROM arigaio/atlas@sha256:ff5291f4995d545479a8301aa364eb256d9f94747d82ae9d6d691ba877fbe8d3 AS atlas

FROM python:3.10-slim-trixie@sha256:c1e4e6c01eb489c422288b2de34b0761ca316f7a2d98e2c33f47659a73ed108a AS base

COPY --from=ghcr.io/astral-sh/uv:0.11.32@sha256:df4cae8f3a96d175e2e5f992e597550000edbe78fdc2594d5cd8de1a217f504c /uv /uvx /bin/
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
