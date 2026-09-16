#!/usr/bin/env bash
# Die beiden gemeinsam genutzten Netze anlegen. Sie sind "external", damit die
# Stacks unabhaengig voneinander gestartet und gestoppt werden koennen.
set -euo pipefail

create() {
    local name="$1"; shift
    if docker network inspect "$name" >/dev/null 2>&1; then
        echo "Netz '$name' existiert bereits."
    else
        docker network create "$@" "$name"
        echo "Netz '$name' angelegt."
    fi
}

# Alles, was Traefik erreichen koennen muss
create edge --driver bridge --subnet 172.18.10.0/24

# Datenbank-Schicht. Kein Traefik-Zugriff, keine veroeffentlichten Ports
# ausser dem Loopback-Mapping von Postgres.
create data --driver bridge --subnet 172.18.20.0/24

echo
echo "Wichtig fuer Home Assistant: trusted_proxies auf das edge-Subnetz setzen:"
docker network inspect edge --format '{{range .IPAM.Config}}  - {{.Subnet}}{{end}}'
