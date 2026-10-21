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
# Der Regelordner gehoert dem Dienst, und zwar schon **im Abbild**: ein
# benanntes Band uebernimmt beim ersten Einhaengen Inhalt und Besitzer des
# Pfades, der im Abbild darunter liegt. Fehlt er dort, legt Docker ihn als
# root an -- und der Dienst kann die dreissig Vorlagen der Spielordnung nicht
# hinterlegen. Der Prueflauf scheitert dann mit "Permission denied", und das
# ist die richtige Antwort: ohne diese Regeln saehe ein Bericht geprueft aus,
# ohne geprueft zu sein. Besser, es kommt gar nicht erst dazu.
RUN useradd --uid 1000 --create-home dienst \
    && chown -R dienst:dienst /ms-playwright \
    && mkdir -p /data/regeln \
    && chown -R dienst:dienst /data
USER dienst

WORKDIR /app/services/pruefdienst
COPY --from=build /app/services/pruefdienst/src ./src

# Kein Healthcheck: der Dienst haelt keinen Port offen. Ob er lebt, steht am
# Auftrag im Artefakt - und das ist die Auskunft, auf die es ankommt.
CMD ["python", "-m", "homepi_pruefdienst"]
