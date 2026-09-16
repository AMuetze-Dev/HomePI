# Multi-Stage, arm64. Wheels werden einmal gebaut und dann nur kopiert -
# das spart auf dem Pi die Compiler-Toolchain im Laufzeit-Image.
FROM python:3.12-slim-bookworm AS build

ENV PIP_NO_CACHE_DIR=1 PIP_DISABLE_PIP_VERSION_CHECK=1
RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential libpq-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt .
RUN python -m venv /opt/venv \
    && /opt/venv/bin/pip install -r requirements.txt

# ---------------------------------------------------------------------------
FROM python:3.12-slim-bookworm

ENV PATH="/opt/venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

RUN apt-get update && apt-get install -y --no-install-recommends libpq5 \
    && rm -rf /var/lib/apt/lists/* \
    && useradd --create-home --uid 10001 appuser

COPY --from=build /opt/venv /opt/venv
WORKDIR /app
COPY --chown=appuser:appuser ./app ./app

USER appuser
EXPOSE 8000

# Ein Worker pro Kern, aber nicht mehr als 4 - der Pi hat 4 Kerne und muss
# daneben noch Postgres und Home Assistant bedienen.
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "2", "--proxy-headers", "--forwarded-allow-ips", "*"]
