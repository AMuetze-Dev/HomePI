#!/usr/bin/env bash
# Backend-Tests wie in der CI: inklusive Integrationstests und Coverage-Schwelle.
# Startet dafuer einen Wegwerf-Postgres auf Port 55432, damit weder der
# data-Stack noch eine lokale Installation im Weg stehen.
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
API_DIR="$ROOT_DIR/services/api"
CONTAINER="homepi-testdb"
PORT="${TESTDB_PORT:-55432}"
MIN_COVERAGE="${MIN_COVERAGE:-85}"

aufraeumen() {
    docker rm -f "$CONTAINER" >/dev/null 2>&1 || true
}
# Auch bei Strg-C und bei fehlgeschlagenen Tests wieder aufraeumen
trap aufraeumen EXIT INT TERM

aufraeumen
echo "==> Wegwerf-Postgres auf Port ${PORT}"
docker run -d --rm --name "$CONTAINER" \
    -e POSTGRES_USER=app -e POSTGRES_PASSWORD=app -e POSTGRES_DB=app \
    -p "${PORT}:5432" postgres:17-bookworm >/dev/null

echo -n "    warte auf die Datenbank"
for _ in $(seq 1 60); do
    if docker exec "$CONTAINER" pg_isready -U app -q 2>/dev/null; then
        echo " - bereit"
        break
    fi
    echo -n "."
    sleep 1
done

echo "==> Format, Lint, Typen"
cd "$API_DIR"
uv run ruff format --check .
uv run ruff check .
uv run mypy

echo "==> Tests (Unit + Integration), Schwelle ${MIN_COVERAGE}%"
DATABASE_URL="postgresql+asyncpg://app:app@127.0.0.1:${PORT}/app" \
    uv run pytest -m '' \
        --cov=homepi_api \
        --cov-report=term-missing \
        --cov-fail-under="${MIN_COVERAGE}"
