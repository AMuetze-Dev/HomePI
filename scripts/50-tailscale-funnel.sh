#!/usr/bin/env bash
# Website und API aus dem Internet - ueber Tailscale Funnel.
#
#   make funnel
#
# Tailscale nimmt die Anfragen unter https://<pi>.<tailnet>.ts.net an (mit
# eigenem Zertifikat) und reicht sie auf dem Pi an Traefiks Eingang "funnel"
# weiter, der nur an 127.0.0.1:8081 horcht. Keine Portfreigabe, kein DynDNS,
# keine Kosten. Hintergrund: docs/14-internet.md.
#
# Darf mehrfach laufen: Was schon da ist, wird uebersprungen.
set -euo pipefail

ZIEL="http://127.0.0.1:8081"

if [[ $EUID -ne 0 ]]; then
    exec sudo "$0" "$@"
fi

# --- 1. Installieren, aus der Paketquelle von Tailscale --------------------
# Nicht das install.sh aus dem Netz: Die Paketquelle ist signiert, und apt
# haelt Tailscale danach mit dem Rest des Systems aktuell.
if ! command -v tailscale >/dev/null; then
    # shellcheck source=/dev/null
    . /etc/os-release
    echo "  -> Tailscale installieren (Debian ${VERSION_CODENAME})"
    curl -fsSL "https://pkgs.tailscale.com/stable/debian/${VERSION_CODENAME}.noarmor.gpg" \
        -o /usr/share/keyrings/tailscale-archive-keyring.gpg
    curl -fsSL "https://pkgs.tailscale.com/stable/debian/${VERSION_CODENAME}.tailscale-keyring.list" \
        -o /etc/apt/sources.list.d/tailscale.list
    apt-get update -qq
    apt-get install -y -qq tailscale
fi
systemctl enable --now tailscaled >/dev/null

# --- 2. Anmelden ------------------------------------------------------------
# Beim ersten Mal steht hier ein Link. Den im Browser oeffnen und den Pi in
# das eigene Tailnet aufnehmen - das Skript wartet so lange.
if ! tailscale status >/dev/null 2>&1; then
    echo "  -> Pi im Tailnet anmelden"
    tailscale up --hostname=homelab
fi

# --- 3. Funnel --------------------------------------------------------------
# Beim ersten Mal fragt Tailscale, ob HTTPS und Funnel im Tailnet erlaubt
# werden sollen, und nennt dafuer einen Link. --bg: Die Einstellung bleibt
# ueber Neustarts erhalten; dieses Skript muss danach nie wieder laufen.
echo "  -> Funnel auf ${ZIEL}"
tailscale funnel --bg "$ZIEL"

echo
tailscale funnel status
