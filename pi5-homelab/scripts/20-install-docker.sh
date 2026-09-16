#!/usr/bin/env bash
# Docker Engine + Compose-Plugin aus dem offiziellen Repo.
# NICHT das apt-Paket "docker.io" nehmen - das ist alt und ohne Compose v2.
set -euo pipefail

if command -v docker >/dev/null 2>&1; then
    echo "Docker ist bereits installiert: $(docker --version)"
else
    echo "==> Docker installieren"
    curl -fsSL https://get.docker.com -o /tmp/get-docker.sh
    sudo sh /tmp/get-docker.sh
    rm -f /tmp/get-docker.sh
fi

echo "==> Log-Rotation fuer Container"
# Der wichtigste Punkt des ganzen Setups: ohne das wachsen Container-Logs
# unbegrenzt und fuellen irgendwann die SSD.
sudo install -d -m 755 /etc/docker
sudo tee /etc/docker/daemon.json >/dev/null <<'EOF'
{
  "log-driver": "json-file",
  "log-opts": { "max-size": "10m", "max-file": "3" },
  "live-restore": true,
  "default-address-pools": [
    { "base": "172.18.0.0/16", "size": 24 }
  ]
}
EOF
sudo systemctl restart docker

echo "==> Benutzer ${USER} zur docker-Gruppe"
sudo usermod -aG docker "${USER}"

echo
docker --version || true
docker compose version 2>/dev/null || sudo docker compose version
echo
echo "Jetzt einmal ab- und wieder anmelden, damit die docker-Gruppe greift:"
echo "  exit"
