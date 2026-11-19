#!/usr/bin/env bash
# Backup. Laeuft mit `make backup`, vor jedem Deploy (deploy.yml) oder per cron:
#   0 3 * * *  /home/aaron/homelab/scripts/backup.sh >> /var/log/homelab-backup.log 2>&1
#
# Strategie:
#   - Postgres: pg_dumpall im laufenden Betrieb (konsistent, kein Stop noetig)
#   - Rest:     Dateikopie. HA und Pi-hole vertragen das im Betrieb,
#               weil ihre kritischen Daten in Postgres bzw. SQLite-WAL liegen.
#   - Ziel:     lokal + optional extern (USB/NAS/Restic)
#
# Laeuft als root: Home Assistant, Mosquitto und Traefik legen ihre Dateien
# als root an (HA-Anmeldedaten, acme.json). Als normaler Benutzer fehlten die
# genau dort, wo es weh tut - und das Skript brach ab, bevor Repo und .env
# gesichert waren. Ohne root startet es sich deshalb selbst ueber sudo neu.
set -euo pipefail

if [[ $EUID -ne 0 ]]; then
    if ! sudo -n true 2>/dev/null; then
        echo "backup.sh braucht root: sudo ohne Passwort fehlt." >&2
        exit 1
    fi
    exec sudo -n "$0" "$@"
fi

# Alles, was hier entsteht, enthaelt Passwoerter (.env, Dump, HA-Anmeldung).
# Nur der Eigentuemer darf es lesen - von Anfang an, nicht erst am Ende.
umask 077

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
set -a; source "$ROOT_DIR/.env"; set +a

STAMP="$(date +%Y-%m-%d)"
DEST="${DATA_ROOT}/backups/${STAMP}"
KEEP_DAYS=14

mkdir -p "$DEST"

echo "[$(date -Is)] Backup nach $DEST"

# Jedes Archiv entsteht erst unter .teil und wird dann umbenannt. Was unter
# dem endgueltigen Namen liegt, ist also vollstaendig.
fertig() { mv -f "$1.teil" "$1"; }

# --- 1. Postgres -----------------------------------------------------------
echo "  -> Postgres"
docker exec -e PGPASSWORD="${POSTGRES_PASSWORD}" postgres \
    pg_dumpall -U "${POSTGRES_USER}" --clean --if-exists \
    | gzip -6 > "${DEST}/postgres-all.sql.gz.teil"
fertig "${DEST}/postgres-all.sql.gz"

# --- 2. Konfigurationen und Volumes ---------------------------------------
# Die --exclude-Optionen stehen VOR den Pfaden: GNU tar wendet Optionen nur
# auf das an, was ihnen folgt, und bricht bei nachgestellten mit Fehler ab.
#
# Rueckgabe 1 heisst bei GNU tar "eine Datei hat sich beim Lesen geaendert" -
# im laufenden Betrieb von Home Assistant normal und kein Grund zum Abbruch.
# Erst 2 ist ein echter Fehler.
echo "  -> Konfigurationen"
rc=0
tar -czf "${DEST}/configs.tar.gz.teil" \
    --warning=no-file-changed \
    --exclude='homeassistant/home-assistant_v2.db*' \
    --exclude='homeassistant/*.log*' \
    --exclude='homeassistant/.storage/*.corrupt.*' \
    -C "${DATA_ROOT}" \
        homeassistant \
        pihole \
        mosquitto \
        uptime-kuma \
        traefik \
    || rc=$?
if (( rc > 1 )); then
    echo "  !! tar meldet Fehler $rc - Konfigurationen unvollstaendig" >&2
    exit "$rc"
fi
fertig "${DEST}/configs.tar.gz"

# --- 3. Das Repo selbst (inkl. .env) ---------------------------------------
echo "  -> Repo + .env"
tar -czf "${DEST}/homelab-repo.tar.gz.teil" \
    --exclude='.git' \
    -C "$(dirname "$ROOT_DIR")" "$(basename "$ROOT_DIR")"
fertig "${DEST}/homelab-repo.tar.gz"

# Wer das Backup per sudo angestossen hat, soll es auch lesen und
# weiterkopieren koennen - nur eben niemand sonst.
if [[ -n "${SUDO_USER:-}" ]]; then
    chown -R "$SUDO_USER:" "$DEST"
fi

# --- 4. Alte Backups aufraeumen -------------------------------------------
find "${DATA_ROOT}/backups" -maxdepth 1 -type d -name '20*' -mtime "+${KEEP_DAYS}" \
    -exec rm -rf {} + 2>/dev/null || true

# --- 5. Offsite ------------------------------------------------------------
# Ein Backup auf derselben SSD ist kein Backup. Mindestens eine der Zeilen
# aktivieren, sobald das Ziel existiert:
#
# rsync -a --delete "${DATA_ROOT}/backups/" /mnt/usb-backup/pi5/
# rsync -a --delete "${DATA_ROOT}/backups/" nas:/volume1/backup/pi5/
# restic -r sftp:nas:/backup/restic backup "${DATA_ROOT}/backups/${STAMP}"

du -sh "$DEST"
echo "[$(date -Is)] fertig"
