# Pi 5 Homelab — Architektur & Runbook

Zielplattform: Raspberry Pi 5 / 16 GB, NVMe-SSD via PCIe-HAT, Raspberry Pi OS Lite 64-bit,
Docker + Compose. Alles läuft nur im LAN, TLS mit echten Zertifikaten via DNS-01.

## Stand der Prüfung

Alle fünf Compose-Dateien sind mit `docker compose config` validiert, die
Template-Ersetzung ist einmal durchlaufen, alle Shell-Skripte sind syntaxgeprüft.
Nicht geprüft, weil dafür die Hardware fehlt: der `Makefile` selbst, die tatsächlichen
Image-Tags und die Pi-hole-v6-Variablennamen (kurz gegen die aktuelle Doku abgleichen,
v6 hat das Schema gegenüber v5 umgestellt).

## Reihenfolge am Tag X

1. `docs/01-hardware.md`  — HAT montieren, EEPROM/Bootorder, NVMe klonen, PCIe Gen 3
2. `docs/02-os-bootstrap.md` — OS-Grundhärtung, Docker, Netzwerke  (`scripts/*.sh`)
3. `.env.example` → `.env` ausfüllen
4. `make up-core up-dns` → prüfen → `make up-data up-home up-apps`
5. `docs/04-runbook.md` — Backup, Updates, Troubleshooting

## Stacks

| Verzeichnis | Inhalt | Netz |
|---|---|---|
| `core/` | Traefik v3 (Reverse Proxy + TLS), Dozzle, Uptime-Kuma | `edge` |
| `dns/`  | Pi-hole v6 | `edge` + Host-Port 53 |
| `home/` | Home Assistant, Mosquitto | Host-Netz (HA), `edge` |
| `data/` | PostgreSQL 17, pgAdmin, Redis | `data` (+ 127.0.0.1:5432) |
| `apps/` | Python-Backend (FastAPI), React-Frontend | `edge` + `data` |

Getrennte Compose-Projekte, verbunden über zwei **externe** Docker-Netze.
Vorteil: du kannst `apps` 20× am Tag neu deployen, ohne HA oder Pi-hole anzufassen.

## Port-Belegung auf dem Host

| Port | Dienst | Bind |
|---|---|---|
| 22 | SSH | LAN |
| 53/tcp+udp | Pi-hole DNS | LAN |
| 80 | Traefik → Redirect auf 443 | LAN |
| 443 | Traefik (TLS) — **deine Software + alle UIs** | LAN |
| 8080 | Pi-hole Admin direkt (Break-Glass, falls Traefik tot) | LAN |
| 8123 | Home Assistant (zwingend Host-Netz) | LAN, per Firewall auf LAN begrenzt |
| 5432 | PostgreSQL | **nur 127.0.0.1** |

**Der Konflikt 80/443 existiert nicht.** Pi-hole v6 bringt zwar einen eigenen Webserver mit,
aber der wird im Container gelassen und nicht auf 80/443 des Hosts gemappt. Traefik besitzt
80 und 443 exklusiv; Pi-hole ist unter `https://pihole.$DOMAIN` erreichbar und zusätzlich
unter `http://$PI_IP:8080` als Notausgang. Pi-hole braucht auf dem Host nur Port 53.

## Hostnamen (alle → $PI_IP)

```
ha.home.example.com        Home Assistant
pihole.home.example.com    Pi-hole Admin
pgadmin.home.example.com   pgAdmin
app.home.example.com       React-Frontend
api.home.example.com       Python-Backend
traefik.home.example.com   Traefik-Dashboard
logs.home.example.com      Dozzle
status.home.example.com    Uptime-Kuma
```

## RAM-Budget (16 GB, realistisch im Betrieb)

```
Traefik            ~60 MB
Pi-hole           ~120 MB
Home Assistant  ~0,8-1,2 GB
PostgreSQL        ~1,5 GB  (shared_buffers 1 GB)
pgAdmin           ~350 MB
Redis              ~50 MB
Python-Backend  ~250-500 MB
Frontend (nginx)   ~15 MB
Mosquitto          ~15 MB
Dozzle/Kuma       ~120 MB
-------------------------
Summe            ~3,5-4,5 GB
```

Du hast ~11 GB Luft. Das ist der Grund, warum die 16-GB-Variante hier eher Reserve für
später ist (Immich, Frigate, Jellyfin, ein LLM-Runner) als Notwendigkeit für diesen Stack.
