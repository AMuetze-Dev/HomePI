# syntax=docker/dockerfile:1
# Der Pruefdienst faehrt einen echten Browser. Das Image ist deshalb deutlich
# groesser als das Gateway - und genau darum laeuft er in einem eigenen
# Container und nicht als Artefakt im Gateway.
#
# Build-Kontext ist die REPO-WURZEL:
#   docker build -f services/pruefdienst/Dockerfile .

FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim AS build

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never \
    UV_PROJECT_ENVIRONMENT=/app/.venv

WORKDIR /app/services/pruefdienst
COPY services/pruefdienst/pyproject.toml services/pruefdienst/uv.lock ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-install-project --no-dev

COPY services/pruefdienst/src ./src
RUN --mount=type=cache,target=/root/.cache/uv uv sync --frozen --no-dev


FROM python:3.12-slim-bookworm

# Chromium und seine Bibliotheken. `playwright install --with-deps` holt beides
# in der Fassung, die zur installierten Playwright-Version passt - eine von
# Hand gepflegte Paketliste laeuft davon weg.
ENV PLAYWRIGHT_BROWSERS_PATH=/ms-playwright \
    PATH="/app/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1

COPY --from=build /app/.venv /app/.venv
RUN playwright install --with-deps chromium \
    && rm -rf /var/lib/apt/lists/*

# Nicht als root. Der Browser laedt fremde Seiten; er soll nicht mehr duerfen
# als noetig.
RUN useradd --uid 1000 --create-home dienst \
    && chown -R dienst:dienst /ms-playwright
USER dienst

WORKDIR /app/services/pruefdienst
COPY --from=build /app/services/pruefdienst/src ./src

# Kein Healthcheck: der Dienst haelt keinen Port offen. Ob er lebt, steht am
# Auftrag im Artefakt - und das ist die Auskunft, auf die es ankommt.
CMD ["python", "-m", "homepi_pruefdienst"]
