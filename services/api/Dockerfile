# syntax=docker/dockerfile:1
# Zielplattform ist arm64 (Raspberry Pi 5). Die Abhaengigkeiten kommen als
# fertige manylinux-aarch64-Wheels, es wird also nichts kompiliert - auch unter
# QEMU in der CI bleibt der Build damit ertraeglich schnell.

FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim AS build

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never

WORKDIR /app

# Erst nur die Abhaengigkeiten - diese Schicht bleibt im Cache, solange sich
# pyproject.toml und uv.lock nicht aendern.
COPY pyproject.toml uv.lock ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-install-project --no-dev

COPY src ./src
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-editable --no-dev

# ---------------------------------------------------------------------------
FROM python:3.14-slim-bookworm

ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

RUN useradd --create-home --uid 10001 appuser

COPY --from=build --chown=appuser:appuser /app/.venv /app/.venv

USER appuser
WORKDIR /app
EXPOSE 8000

# Zwei Worker: der Pi hat vier Kerne und muss daneben Postgres und
# Home Assistant bedienen.
CMD ["uvicorn", "homepi_api.main:app", \
     "--host", "0.0.0.0", "--port", "8000", \
     "--workers", "2", \
     "--proxy-headers", "--forwarded-allow-ips", "*"]
