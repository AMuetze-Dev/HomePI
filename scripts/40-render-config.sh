#!/usr/bin/env bash
# Traefiks dynamische Konfiguration kennt keine Umgebungsvariablen.
# Deshalb werden die *.yml.tmpl hier mit envsubst zu *.yml gerendert.
# Nach jeder Aenderung an .env oder an einem Template erneut ausfuehren -
# Traefik laedt die Dateien dank providers.file.watch automatisch nach.
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
[[ -f "$ROOT_DIR/.env" ]] || { echo "FEHLER: .env fehlt."; exit 1; }
set -a; source "$ROOT_DIR/.env"; set +a

shopt -s nullglob
for tmpl in "$ROOT_DIR"/stacks/core/dynamic/*.yml.tmpl; do
    out="${tmpl%.tmpl}"
    # nur die Variablen ersetzen, die wir meinen - sonst frisst envsubst
    # auch Traefik-eigene Platzhalter
    envsubst '${DOMAIN} ${LAN_CIDR} ${PI_IP}' < "$tmpl" > "$out"
    echo "gerendert: ${out#$ROOT_DIR/}"
done
