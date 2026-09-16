# syntax=docker/dockerfile:1
# Zielplattform ist arm64 (Raspberry Pi 5). Die Abhaengigkeiten kommen als
# fertige manylinux-aarch64-Wheels, es wird also nichts kompiliert - auch unter
# QEMU in der CI bleibt der Build damit ertraeglich schnell.
#
# WICHTIG: Build-Kontext ist die REPO-WURZEL, sonst waeren packages/ und
# modules/ nicht erreichbar:
#   docker build -f services/gateway/Dockerfile .

FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim AS build

# UV_PROJECT_ENVIRONMENT legt die venv direkt dort an, wo sie spaeter liegt.
# Kopiert man sie an einen anderen Pfad, zeigen die Shebangs ihrer Skripte
# (bin/uvicorn) noch auf den alten - das Image startet dann mit
# "exec: uvicorn: not found".
ENV UV_COMPILE_BYTECODE=1     UV_LINK_MODE=copy     UV_PYTHON_DOWNLOADS=never     UV_PROJECT_ENVIRONMENT=/app/.venv

WORKDIR /app

# Basispaket und Artefakte zuerst, dann die Projektdatei des Gateways: die
# Abhaengigkeitsschicht bleibt im Cache, solange sich nur Quellcode aendert.
COPY packages/homepi-core /app/packages/homepi-core
COPY modules /app/modules
COPY services/gateway/pyproject.toml services/gateway/uv.lock /app/services/gateway/

WORKDIR /app/services/gateway
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-install-project --no-dev

COPY services/gateway/src ./src
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-editable --no-dev

# ---------------------------------------------------------------------------
FROM python:3.12-slim-bookworm

ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

RUN useradd --create-home --uid 10001 appuser

COPY --from=build --chown=appuser:appuser /app/.venv /app/.venv

USER appuser
WORKDIR /app
EXPOSE 8000

# Ein Worker. Ueber WEB_CONCURRENCY in der Compose-Datei erhoehbar.
CMD ["sh", "-c", "exec uvicorn homepi_gateway.main:app --host 0.0.0.0 --port 8000 --workers ${WEB_CONCURRENCY:-1} --proxy-headers --forwarded-allow-ips '*'"]
