# 02 — OS, Docker, Netzwerke

OS-Empfehlung: **Raspberry Pi OS Lite 64-bit**. Nicht Desktop (spart RAM und Angriffsfläche),
nicht Ubuntu (Pi OS hat den besseren Support für Pi-5-Eigenheiten wie PCIe, EEPROM, RTC).

Bei `rpi-imager` gleich im Vorab-Dialog setzen: Hostname `pi5`, Benutzer, **SSH-Public-Key
statt Passwort**, WLAN nur falls nötig (LAN-Kabel ist für einen Server die bessere Wahl),
Locale/Timezone.

## Ablauf

```bash
git clone <dein-repo> ~/homelab && cd ~/homelab
sudo ./scripts/10-os-bootstrap.sh      # Pakete, Härtung, Journald, Swap, fstrim
./scripts/20-install-docker.sh         # Docker Engine + Compose Plugin
# ab-/anmelden, damit die docker-Gruppe greift
exit
```

Nach erneutem Login:

```bash
cd ~/homelab
cp .env.example .env && nano .env      # ausfüllen!
./scripts/30-create-networks.sh        # externe Netze edge + data
make up-core
```

## Was `10-os-bootstrap.sh` macht und warum

| Schritt | Grund |
|---|---|
| `apt full-upgrade` | Ausgangszustand. |
| Pakete: `ufw fail2ban git make curl jq nvme-cli smartmontools fio rsync unattended-upgrades` | Werkzeugkasten plus NVMe-Diagnose. |
| UFW: deny incoming, allow 22/53/80/443/8080/8123 **nur aus `$LAN_CIDR`** | HA auf 8123 wäre sonst offen für alles, was ins LAN kommt. |
| `fail2ban` für SSH | Auch im LAN sinnvoll, falls doch mal etwas erreichbar wird. |
| `dphys-swapfile` aus | 16 GB RAM. Swap auf SSD kostet nur Schreibzyklen. |
| `journald` auf 200 MB begrenzt | Sonst wachsen Logs unbemerkt. |
| `/etc/docker/daemon.json` mit `log-opts max-size=10m,max-file=3` | **Der wichtigste Punkt.** Ohne das wachsen Container-Logs unbegrenzt; HA und Traefik produzieren viel. Klassische Ursache für volle Platten nach ein paar Monaten. |
| `fstrim.timer` aktiv | SSD-Gesundheit. |
| `vm.swappiness=10`, `vm.overcommit_memory=1` | Letzteres verhindert Redis-Warnungen. |
| Verzeichnis `/srv/homelab` mit Unterordnern pro Stack | Alle Volumes sind **Bind-Mounts** dorthin. Backup ist dann ein `tar` über einen Pfad, nicht eine Jagd durch `/var/lib/docker/volumes`. |

## Port 53: mögliche Kollision prüfen

Bevor Pi-hole startet:

```bash
sudo ss -tulpn | grep ':53 '
```

Auf Raspberry Pi OS Lite ist üblicherweise nichts da. Falls doch `systemd-resolved`
lauscht (typisch bei Ubuntu):

```bash
sudo mkdir -p /etc/systemd/resolved.conf.d
printf '[Resolve]\nDNSStubListener=no\n' | sudo tee /etc/systemd/resolved.conf.d/no-stub.conf
sudo ln -sf /run/systemd/resolve/resolv.conf /etc/resolv.conf
sudo systemctl restart systemd-resolved
```

## Der Pi darf nicht sich selbst als DNS benutzen

Sonst kann er bei einem Pi-hole-Neustart kurzzeitig gar nichts auflösen — inklusive
`docker pull` und `apt`. Trage im Router als DNS für **den Pi selbst** einen externen
Resolver ein, oder fixiere es lokal:

```bash
# Raspberry Pi OS Bookworm/Trixie nutzt NetworkManager
sudo nmcli con mod "Wired connection 1" ipv4.ignore-auto-dns yes
sudo nmcli con mod "Wired connection 1" ipv4.dns "9.9.9.9 1.1.1.1"
sudo nmcli con up "Wired connection 1"
```

## Reihenfolge der Inbetriebnahme

Nicht alles auf einmal. Jede Stufe verifizieren:

1. **`make up-core`** — Traefik. Prüfen: `docker compose -f core/... logs -f traefik`.
   Das Wildcard-Zertifikat muss erscheinen (dauert bis zu 2 Minuten wegen DNS-Propagation).
   Test: `https://traefik.$DOMAIN` zeigt das Dashboard mit gültigem Zertifikat.
2. **`make up-dns`** — Pi-hole. Test auf `http://$PI_IP:8080`, dann
   `dig @$PI_IP google.com`. Erst wenn das sauber antwortet, im **Router** den DNS ändern.
3. **`make up-data`** — Postgres. Test: `make psql`.
4. **`make up-home`** — Home Assistant. Erst per `http://$PI_IP:8123` einrichten, dann
   `trusted_proxies` in `configuration.yaml` setzen, HA neu starten, dann über
   `https://ha.$DOMAIN` prüfen.
5. **`make up-apps`** — deine eigene Software.

## Deine externen SSDs / USB-Platten

Falls du später eine USB-Platte für Backups anschließt: **immer per UUID in `/etc/fstab`**
mounten, mit `nofail`. Sonst bootet der Pi nicht, wenn die Platte einmal nicht da ist.

```
UUID=xxxx-xxxx  /mnt/backup  ext4  defaults,nofail,noatime  0  2
```
