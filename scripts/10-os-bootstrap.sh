#!/usr/bin/env bash
# Grundkonfiguration des Raspberry Pi OS Lite 64-bit fuer den Docker-Betrieb.
# Aufruf:  sudo ./scripts/10-os-bootstrap.sh
set -euo pipefail

if [[ $EUID -ne 0 ]]; then echo "Bitte mit sudo ausfuehren."; exit 1; fi

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
[[ -f "$ROOT_DIR/.env" ]] || { echo "FEHLER: .env fehlt. cp .env.example .env"; exit 1; }
set -a; source "$ROOT_DIR/.env"; set +a

REAL_USER="${SUDO_USER:-pi}"

echo "==> Pakete aktualisieren"
apt-get update
DEBIAN_FRONTEND=noninteractive apt-get -y full-upgrade

echo "==> Werkzeuge installieren"
DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
    ca-certificates curl git make jq gettext-base \
    ufw fail2ban unattended-upgrades \
    nvme-cli smartmontools fio hdparm \
    rsync htop ncdu tmux dnsutils apache2-utils

echo "==> Zeitzone ${TZ}"
timedatectl set-timezone "${TZ}"

echo "==> SSH haerten (nur Public-Key)"
install -d -m 755 /etc/ssh/sshd_config.d
cat > /etc/ssh/sshd_config.d/99-homelab.conf <<'EOF'
PasswordAuthentication no
PermitRootLogin no
KbdInteractiveAuthentication no
MaxAuthTries 3
EOF
# Sicherheitsnetz: nur aktivieren, wenn wirklich ein Key hinterlegt ist
if [[ -s "/home/${REAL_USER}/.ssh/authorized_keys" ]]; then
    systemctl restart ssh
    echo "    SSH: Passwort-Login deaktiviert."
else
    rm -f /etc/ssh/sshd_config.d/99-homelab.conf
    echo "    WARNUNG: kein authorized_keys fuer ${REAL_USER} gefunden."
    echo "    Passwort-Login bleibt AN. Key hinterlegen, dann Skript erneut laufen lassen."
fi

echo "==> Firewall (UFW) - alles nur aus ${LAN_CIDR}"
ufw --force reset >/dev/null
ufw default deny incoming
ufw default allow outgoing
ufw allow from "${LAN_CIDR}" to any port 22    proto tcp comment 'SSH'
ufw allow from "${LAN_CIDR}" to any port 53               comment 'Pi-hole DNS'
ufw allow from "${LAN_CIDR}" to any port 80    proto tcp comment 'Traefik HTTP'
ufw allow from "${LAN_CIDR}" to any port 443   proto tcp comment 'Traefik HTTPS'
ufw allow from "${LAN_CIDR}" to any port 8080  proto tcp comment 'Pi-hole Notausgang'
ufw allow from "${LAN_CIDR}" to any port 8123  proto tcp comment 'Home Assistant'
ufw allow from "${LAN_CIDR}" to any port 1883  proto tcp comment 'MQTT'
ufw allow from "${LAN_CIDR}" to any port 8099  proto tcp comment 'Zigbee2MQTT'
ufw --force enable
# Hinweis: UFW und Dockers eigene iptables-Regeln greifen unabhaengig voneinander.
# Published Ports umgehen UFW. Deshalb sind hier alle Ports ausser 53/80/443
# entweder auf 127.0.0.1 gebunden oder bewusst LAN-offen.

echo "==> Swap aus (16 GB RAM, spart SSD-Schreibzyklen)"
systemctl disable --now dphys-swapfile 2>/dev/null || true

echo "==> journald begrenzen"
install -d -m 755 /etc/systemd/journald.conf.d
cat > /etc/systemd/journald.conf.d/99-size.conf <<'EOF'
[Journal]
SystemMaxUse=200M
SystemMaxFileSize=50M
EOF
systemctl restart systemd-journald

echo "==> sysctl"
cat > /etc/sysctl.d/99-homelab.conf <<'EOF'
vm.swappiness=10
vm.overcommit_memory=1
net.core.somaxconn=1024
fs.inotify.max_user_watches=524288
EOF
sysctl --system >/dev/null

echo "==> fstrim wöchentlich"
systemctl enable --now fstrim.timer

echo "==> unattended-upgrades (nur Security)"
dpkg-reconfigure -f noninteractive unattended-upgrades

echo "==> Datenverzeichnisse unter ${DATA_ROOT}"
install -d -m 755 "${DATA_ROOT}"
for d in traefik/letsencrypt pihole/etc-pihole homeassistant \
         mosquitto/data mosquitto/log postgres/data pgadmin redis \
         uptime-kuma backups; do
    install -d -m 755 "${DATA_ROOT}/${d}"
done
chmod 700 "${DATA_ROOT}/traefik/letsencrypt"
# pgAdmin laeuft im Container als uid 5050
chown -R 5050:5050 "${DATA_ROOT}/pgadmin"
chown -R "${REAL_USER}:${REAL_USER}" "${DATA_ROOT}/homeassistant" "${DATA_ROOT}/backups"

echo
echo "Fertig. Naechster Schritt: ./scripts/20-install-docker.sh"
