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

# Alle Regeln unten nennen ${LAN_CIDR} und gelten damit nur fuer IPv4.
# Das ist Absicht und nur deshalb vertretbar, weil weiter unten die globalen
# IPv6-Adressen abgeschaltet werden. Wer das wieder einschaltet, muss hier
# IPv6-Regeln ergaenzen - sonst ist der Pi ueber seinen Namen unerreichbar,
# waehrend er ueber die IP tadellos antwortet.
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
# Home Assistant laeuft im Host-Netz. Traefik erreicht es ueber die Docker-
# Bruecke, also aus dem edge-Netz (30-create-networks.sh) und NICHT aus dem
# LAN - ohne diese Regel endet https://ha.<DOMAIN> in einer Zeitueberschreitung.
ufw allow from 172.18.10.0/24 to any port 8123 proto tcp comment 'Traefik -> Home Assistant'
ufw --force enable
# Hinweis: UFW und Dockers eigene iptables-Regeln greifen unabhaengig voneinander.
# Published Ports umgehen UFW. Deshalb sind hier alle Ports ausser 53/80/443
# entweder auf 127.0.0.1 gebunden oder bewusst LAN-offen.

echo "==> Swap aus (16 GB RAM, spart SSD-Schreibzyklen)"
systemctl disable --now dphys-swapfile 2>/dev/null || true

echo "==> journald: dauerhaft und begrenzt"
install -d -m 755 /etc/systemd/journald.conf.d

# Raspberry Pi OS liefert /usr/lib/systemd/journald.conf.d/40-rpi-volatile-storage.conf
# mit Storage=volatile aus - das Protokoll liegt dann nur im Arbeitsspeicher
# und ist nach jedem Neustart weg.
#
# Der Dateiname MUSS derselbe sein. Drop-ins werden alphabetisch gelesen und
# die ZULETZT gelesene gewinnt; eine Datei "00-dauerhaft.conf" verliert also
# gegen "40-rpi-...". Nur bei gleichem Namen hat /etc Vorrang vor /usr/lib.
#
# Das ist kein theoretischer Punkt: Genau dieser Fehler hat dazu gefuehrt,
# dass nach einem Ausfall der vorherige Startvorgang nicht mehr nachlesbar
# war - und damit die Ursache unauffindbar.
cat > /etc/systemd/journald.conf.d/40-rpi-volatile-storage.conf <<'EOF'
[Journal]
Storage=persistent
EOF

cat > /etc/systemd/journald.conf.d/99-size.conf <<'EOF'
[Journal]
SystemMaxUse=200M
SystemMaxFileSize=50M
EOF
install -d -m 2755 -g systemd-journal /var/log/journal
systemctl restart systemd-journald
journalctl --flush >/dev/null 2>&1 || true

echo "==> sysctl"
cat > /etc/sysctl.d/99-homelab.conf <<'EOF'
vm.swappiness=10
vm.overcommit_memory=1
net.core.somaxconn=1024
fs.inotify.max_user_watches=524288
EOF
sysctl --system >/dev/null

echo "==> keine globalen IPv6-Adressen"
# Die UFW-Regeln oben gelten ausschliesslich fuer ${LAN_CIDR}, also fuer IPv4.
# ip6tables steht dabei auf policy DROP. Hat der Pi globale IPv6-Adressen,
# verwirft er jede IPv6-Verbindung stillschweigend - und weil die Fritz!Box
# AAAA-Eintraege fuer den Rechnernamen veroeffentlicht und Browser IPv6
# bevorzugen, ist er ueber seinen NAMEN nicht erreichbar, ueber die IP aber
# sofort. Ein Fehlerbild, das man lange fuer einen Dienstausfall haelt.
#
# Zwei Wege fuehren zu globalen Adressen, und beide muessen zu:
#   * Router Advertisements -> accept_ra/autoconf (hier)
#   * DHCPv6 ueber NetworkManager -> ipv6.method (weiter unten)
#
# "all" und "default" gelten nur fuer NEU angelegte Schnittstellen; die
# vorhandenen muessen ausdruecklich genannt werden.
#
# Link-local (fe80::) und ::1 bleiben erhalten.
cat > /etc/sysctl.d/99-kein-globales-ipv6.conf <<'EOF'
net.ipv6.conf.all.accept_ra = 0
net.ipv6.conf.default.accept_ra = 0
net.ipv6.conf.all.autoconf = 0
net.ipv6.conf.default.autoconf = 0
EOF

# Die echten Netzschnittstellen - Kabel und Funk, ohne lo, docker0 und die
# veth-Paare der Container. Globs statt "ls | grep": ls ist fuer Menschen
# gemacht, nicht zum Weiterverarbeiten. "wl*" deckt wlan* mit ab.
netz_schnittstellen() {
    local pfad
    for pfad in /sys/class/net/eth* /sys/class/net/en* /sys/class/net/wl*; do
        [ -e "$pfad" ] && printf '%s\n' "${pfad##*/}"
    done
}

for iface in $(netz_schnittstellen); do
    printf 'net.ipv6.conf.%s.accept_ra = 0\nnet.ipv6.conf.%s.autoconf = 0\n' \
        "$iface" "$iface" >> /etc/sysctl.d/99-kein-globales-ipv6.conf
done
sysctl -q --load=/etc/sysctl.d/99-kein-globales-ipv6.conf

# DHCPv6 laeuft an accept_ra vorbei - deshalb zusaetzlich am Profil.
#
# Zeilenweise lesen, nicht "for conn in $(...)": Verbindungsnamen enthalten
# Leerzeichen ("netplan-wlan0-Wi-Fight Club"). Die for-Schleife zerlegte den
# Namen in zwei Woerter, beide Aufrufe scheiterten still am "|| true" - und
# ausgerechnet das WLAN-Profil blieb, wie es war.
#
# Gefiltert wird nach Schnittstelle, nicht nach Typ: NetworkManager fuehrt auch
# jedes veth-Paar von Docker als Profil vom Typ 802-3-ethernet.
while IFS= read -r conn; do
    [ -n "$conn" ] || continue
    case "$(nmcli -g connection.interface-name connection show "$conn" 2>/dev/null)" in
        eth*|en*|wl*)
            nmcli connection modify "$conn" ipv6.method link-local 2>/dev/null || true
            ;;
    esac
done < <(nmcli -g NAME connection show 2>/dev/null)
for iface in $(netz_schnittstellen); do
    nmcli device reapply "$iface" >/dev/null 2>&1 || true
    ip -6 addr flush dev "$iface" scope global 2>/dev/null || true
done

echo "==> NVMe: kein Tiefschlaf (APST aus)"
# Die SSD (Intenso, MAXIO MAP1202, ohne DRAM) bietet Schlafzustaende mit bis
# zu 45 ms Aufwachzeit an, der Kernel erlaubt per Voreinstellung 100 ms - sie
# darf also hinein. Aus einem davon kam sie offenbar nicht zurueck: Am
# 6. Oktober endete das Journal mitten in einem Strom von Meldungen im
# Sekundentakt, ohne eine einzige Fehlerzeile. Laufende Container lebten
# weiter, alles Neue - SSH-Anmeldung, Zigbee2MQTT - blieb haengen. So sieht
# eine Platte aus, die nicht mehr antwortet; die Fehlermeldung darueber kann
# sie naturgemaess nicht mehr schreiben. SMART zeigte danach keinen Fehler.
#
# Kostet rund 3 W Leerlauf gegen 0,05 W - fuer einen Server, der laufen soll,
# kein Abwaegen. Wirksam erst nach einem Neustart.
CMDLINE=/boot/firmware/cmdline.txt
if [[ -f "$CMDLINE" ]] && ! grep -q "nvme_core.default_ps_max_latency_us=" "$CMDLINE"; then
    cp "$CMDLINE" "${CMDLINE}.vor-apst"
    # cmdline.txt ist EINE Zeile - anhaengen, nie eine zweite beginnen.
    sed -i '1 s/$/ nvme_core.default_ps_max_latency_us=0/' "$CMDLINE"
    echo "    eingetragen - wirkt nach dem naechsten Neustart."
fi

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
