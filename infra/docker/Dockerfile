# --- Stage 1: Builder ---
FROM python:3.13-slim as builder

RUN pip install poetry==1.8.5 poetry-plugin-export

ENV POETRY_NO_INTERACTION=1 \
    POETRY_VIRTUALENVS_IN_PROJECT=1 \
    POETRY_VIRTUALENVS_CREATE=1 \
    POETRY_CACHE_DIR=/tmp/poetry_cache

WORKDIR /app

COPY pyproject.toml poetry.lock ./

RUN poetry install --only main --no-root && rm -rf $POETRY_CACHE_DIR

# --- Stage 2: Production ---
FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app \
    PORT=8000 \
    PATH="/app/.venv/bin:$PATH"

WORKDIR /app

COPY --from=builder /app/.venv ./.venv

COPY src/ ./src/

RUN useradd -m appuser && chown -R appuser:appuser /app
USER appuser

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -f http://127.0.0.1:$PORT/health || exit 1

CMD uvicorn src.main:app --host 0.0.0.0 --port $PORT
