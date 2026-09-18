# HomePI

Selbst gehostete Infrastruktur auf einem Raspberry Pi 5 (16 GB, NVMe): Home Assistant,
Pi-hole, PostgreSQL und eine eigene Anwendung aus Python-Backend und React-Frontend —
alles in Docker, hinter einem Reverse Proxy mit echten TLS-Zertifikaten, ohne eine
einzige Portfreigabe im Router.

## Aufbau des Repos

```
stacks/        Docker-Compose-Stacks, einer pro Verantwortungsbereich
  core/          Traefik (Reverse Proxy + TLS), Dozzle, Uptime-Kuma
  dns/           Pi-hole
  data/          PostgreSQL, pgAdmin, Redis
  home/          Home Assistant, Mosquitto
  apps/          eigene Anwendung (API + Web)
packages/      wiederverwendbare Bausteine
  homepi-core/   Grundgeruest jedes Microservice + homepi-CLI
modules/       Artefakte, die im Gateway laufen
  geraete/       Geraete im Haus (FastAPI-Router + Fachlogik)
               neue entstehen mit: homepi new <name>
services/      lauffaehige Dienste
  gateway/       Python / FastAPI - laedt die Artefakte
  web/           TypeScript / React - die Huelle mit der Startseite
scripts/       Einrichtung, Backup, Diagnose
docs/          Architektur, Inbetriebnahme, Runbook, Arbeitsweise
```

Die Stacks sind bewusst getrennte Compose-Projekte, verbunden über zwei externe
Docker-Netze. Du kannst `apps` zwanzigmal am Tag neu deployen, ohne Home Assistant oder
Pi-hole anzufassen.

## Dokumentation

| Datei | Inhalt |
|---|---|
| [docs/01-hardware.md](docs/01-hardware.md) | Einkaufsliste, NVMe-Boot, PCIe Gen 3, Fallstricke |
| [docs/02-os-bootstrap.md](docs/02-os-bootstrap.md) | OS-Härtung, Docker, Netze, Reihenfolge der Inbetriebnahme |
| [docs/03-architecture.md](docs/03-architecture.md) | Netztopologie und die Begründung hinter jeder Entscheidung |
| [docs/04-runbook.md](docs/04-runbook.md) | Backup, Restore, Updates, Troubleshooting |
| [docs/05-workflow.md](docs/05-workflow.md) | Branch-Modell, TDD-Schleife, CI/CD |
| [docs/06-artefakte.md](docs/06-artefakte.md) | Wie neue Artefakte dazukommen, ohne dass ein Container dazukommt |
| [docs/07-lokale-entwicklung.md](docs/07-lokale-entwicklung.md) | Die Docker-Umgebung auf dem Windows-Rechner |
| [docs/08-design.md](docs/08-design.md) | Designsystem: Tokens, Bausteine, Verhalten, Zugänglichkeit |
| [docs/09-artefakt-bauen.md](docs/09-artefakt-bauen.md) | Vom leeren Verzeichnis bis zur Kachel auf dem Pi |
| [docs/10-auftrag-artefakt.md](docs/10-auftrag-artefakt.md) | Fertiger Auftrag zum Übergeben an einen Agenten |
| [docs/11-anmeldung.md](docs/11-anmeldung.md) | Ersteinrichtung, Konten, Rechte je Artefakt, wer welches Artefakt sieht |
| [docs/12-testen.md](docs/12-testen.md) | Wie ein Artefakt geprüft wird: fünf Ebenen, Testdatenbank, bekannte Fallen |
| [docs/13-pi-erstinstallation.md](docs/13-pi-erstinstallation.md) | Pi OS auf die NVMe bringen — headless, ohne Kabel, und was dabei alles schiefging |

## Schnellstart auf dem Pi

```bash
git clone https://github.com/AMuetze-Dev/HomePI.git ~/homelab && cd ~/homelab
sudo ./scripts/10-os-bootstrap.sh
./scripts/20-install-docker.sh      # danach ab- und wieder anmelden
cp .env.example .env && nano .env
./scripts/30-create-networks.sh
make up
```

`make help` listet alle Kommandos.

## Port-Belegung auf dem Host

| Port | Dienst | Bind |
|---|---|---|
| 22 | SSH | LAN |
| 53/tcp+udp | Pi-hole DNS | LAN |
| 80 | Traefik → Redirect auf 443 | LAN |
| 443 | Traefik (TLS) — alle Web-Oberflächen | LAN |
| 8080 | Pi-hole Admin direkt (Notausgang) | LAN |
| 8123 | Home Assistant (zwingend Host-Netz) | LAN |
| 5432 | PostgreSQL | nur 127.0.0.1 |

Pi-hole und die eigene Software kollidieren nicht: Pi-hole braucht auf dem Host nur
Port 53, sein Webserver bleibt im Container und wird von Traefik geroutet.

## Hostnamen

Alle Dienste laufen unter `*.$DOMAIN` mit einem Wildcard-Zertifikat von Let's Encrypt,
das per DNS-01-Challenge ausgestellt wird — deshalb muss nichts aus dem Internet
erreichbar sein.

```
ha.$DOMAIN        Home Assistant     pgadmin.$DOMAIN   pgAdmin
app.$DOMAIN       Huelle/Startseite  logs.$DOMAIN      Dozzle
api.$DOMAIN       Gateway            status.$DOMAIN    Uptime-Kuma
pihole.$DOMAIN    Pi-hole            traefik.$DOMAIN   Traefik-Dashboard
```

Die Artefakte bekommen keine eigenen Hostnamen: sie laufen als Module im
Gateway und sind unter `api.$DOMAIN/<artefakt>` erreichbar. Warum das so ist,
steht in [docs/06-artefakte.md](docs/06-artefakte.md).

Für Agenten ist [AGENTS.md](AGENTS.md) der Einstieg.

## Entwicklung

Der Pi wird nicht gebraucht — die komplette Anwendung läuft lokal in Docker:

```bash
make dev           # Frontend 5173, API 18000, Postgres 15432
make test          # alles, was die CI auch prüft
make smoke         # Rauchtests gegen die laufende Umgebung
make tdd-web       # vitest im Watch-Modus
make tdd-api P=modules/geraete
```

Details in [docs/07-lokale-entwicklung.md](docs/07-lokale-entwicklung.md).

Branch-Modell und die genaue TDD-Schleife stehen in
[docs/05-workflow.md](docs/05-workflow.md).
