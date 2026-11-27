#!/usr/bin/env bash
# Auf dem Pi: den Anwendungs-Stack auf den Stand von develop bringen.
#
# Wird von scripts/ausrollen.ps1 per ssh aufgerufen, NACH einem
# "git pull --ff-only" - so laeuft immer die neueste Fassung dieses Skripts.
# Von Hand geht es genauso:
#
#   cd ~/homelab && git pull --ff-only && bash scripts/pi-ausrollen.sh
#
# Was es tut: sichern, Images ziehen und Container ersetzen, auf ein gesundes
# Gateway warten, fehlende Tabellen anlegen, den Zustand zeigen.
#
# Was es NICHT tut: Migrationen aus scripts/migrationen/ einspielen. Die
# brauchen manchmal eine Entscheidung (etwa welches Konto etwas bekommt) und
# sind nicht zurueckzunehmen. Neue Dateien dort werden genannt, samt Befehl.
#
# Argumente: die Namen neuer Migrationsdateien, die ausrollen.ps1 gefunden hat.

set -euo pipefail
cd "$(dirname "$0")/.."

schritt() { printf '\n==> %s\n' "$*"; }

schritt "Sichern"
make backup

schritt "Images ziehen und Container ersetzen"
make deploy-apps

schritt "Warten, bis das Gateway gesund ist"
for _ in $(seq 1 40); do
    zustand=$(docker inspect -f '{{.State.Health.Status}}' gateway 2>/dev/null || echo fehlt)
    [ "$zustand" = "healthy" ] && break
    sleep 3
done
echo "    gateway: $zustand"

# Erst nach dem Start: Das Gateway legt in Produktion keine Tabellen an
# (DB_SCHEMA_ANLEGEN=false). Ohne diesen Schritt steht ein neues Artefakt
# als "fehler" da, und /health meldet schema=false.
schritt "Fehlende Tabellen anlegen"
docker exec gateway homepi schema anlegen

schritt "Zustand"
docker exec gateway python -c \
    "import urllib.request;print(urllib.request.urlopen('http://127.0.0.1:8000/health').read().decode())"
docker ps --filter name=gateway --filter name=web --format '    {{.Names}}  {{.Status}}'

if [ "$#" -gt 0 ]; then
    schritt "Von Hand einspielen - neue Migrationen"
    for datei in "$@"; do
        echo "    $datei"
        echo "      Kopf lesen, dann:"
        echo "      docker exec -i postgres psql -U app -d app -v ON_ERROR_STOP=1 -f - < $datei"
    done
fi

echo
echo "Fertig."
