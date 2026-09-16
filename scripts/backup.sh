#!/usr/bin/env bash
# Taegliches Backup. Per cron:
#   0 3 * * *  /home/pi/homelab/scripts/backup.sh >> /var/log/homelab-backup.log 2>&1
#
# Strategie:
#   - Postgres: pg_dumpall im laufenden Betrieb (konsistent, kein Stop noetig)
#   - Rest:     Dateikopie. HA und Pi-hole vertragen das im Betrieb,
#               weil ihre kritischen Daten in Postgres bzw. SQLite-WAL liegen.
#   - Ziel:     lokal + optional extern (USB/NAS/Restic)
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
set -a; source "$ROOT_DIR/.env"; set +a

STAMP="$(date +%Y-%m-%d)"
DEST="${DATA_ROOT}/backups/${STAMP}"
KEEP_DAYS=14

mkdir -p "$DEST"

echo "[$(date -Is)] Backup nach $DEST"

# --- 1. Postgres -----------------------------------------------------------
echo "  -> Postgres"
docker exec -e PGPASSWORD="${POSTGRES_PASSWORD}" postgres \
    pg_dumpall -U "${POSTGRES_USER}" --clean --if-exists \
    | gzip -6 > "${DEST}/postgres-all.sql.gz"

# --- 2. Konfigurationen und Volumes ---------------------------------------
echo "  -> Konfigurationen"
tar -czf "${DEST}/configs.tar.gz" \
    -C "${DATA_ROOT}" \
        homeassistant \
        pihole \
        mosquitto \
        uptime-kuma \
        traefik \
    --exclude='homeassistant/home-assistant_v2.db*' \
    --exclude='homeassistant/*.log*' \
    --exclude='homeassistant/.storage/*.corrupt.*'

# --- 3. Das Repo selbst (inkl. .env - deshalb Rechte einschraenken) --------
echo "  -> Repo + .env"
tar -czf "${DEST}/homelab-repo.tar.gz" -C "$(dirname "$ROOT_DIR")" \
    --exclude='.git' "$(basename "$ROOT_DIR")"
chmod 600 "${DEST}"/*.gz

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
