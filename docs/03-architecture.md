# 03 — Architekturentscheidungen

## Netz-Topologie

```
                    Internet
                       |
                   [ Router ]  DHCP-Option DNS = 192.168.1.50
                       |
                  LAN 192.168.1.0/24
                       |
        +--------------+-----------------------------+
        |            Raspberry Pi 5                   |
        |                                             |
        |  :53   Pi-hole ────────────┐                |
        |  :8080 Pi-hole Admin       │                |
        |                            │                |
        |  :80 ──redirect──▶ :443  Traefik v3         |
        |                        │   │                |
        |        docker net "edge"   │                |
        |     ┌──────────────────────┼─────────────┐  |
        |     │  pihole   web   api  │  pgadmin    │  |
        |     │             dozzle   │  kuma       │  |
        |     └──────┬───────────────┘             │  |
        |            │                             │  |
        |     docker net "data"                   │  |
        |     ┌──────┴──────────────────────────┐  │  |
        |     │   postgres        redis         │  │  |
        |     └─────────────────────────────────┘  │  |
        |                                          │  |
        |  :8123 Home Assistant (network_mode host)│  |
        |         └─ 127.0.0.1:5432 ──▶ postgres   │  |
        +------------------------------------------+--+
```

Zwei Netze, bewusst getrennt:

- **`edge`** (172.18.10.0/24) — alles, was Traefik erreichen können muss.
- **`data`** (172.18.20.0/24) — Postgres und Redis. Kein Traefik-Label, keine
  veröffentlichten Ports außer `127.0.0.1:5432` für Postgres. Das Backend und pgAdmin
  hängen in beiden Netzen und sind die einzigen Brücken.

Anmerkung zu `internal: true`: Damit würde `data` zusätzlich jede ausgehende Verbindung
der DB-Container unterbinden — sicherheitstechnisch schöner. Es kollidiert aber mit dem
Loopback-Mapping von Postgres (`127.0.0.1:5432`), das Home Assistant im Host-Netz und
dein SSH-Tunnel brauchen. Wenn du auf beides verzichten kannst (Zugriff nur noch per
`make psql` im Container), setz in `scripts/30-create-networks.sh` `--internal` für `data`
und entferne den `ports:`-Block bei Postgres.

## Warum Home Assistant im Host-Netz läuft

HA braucht Broadcast/mDNS für Auto-Discovery (Sonos, HomeKit, ESPHome, Chromecast,
DHCP-Scan). Im Bridge-Netz findet es schlicht nichts. Offiziell unterstützt ist deshalb
nur `network_mode: host`. Konsequenzen, die du einplanen musst:

1. HA belegt Port **8123 auf dem Host**. Kein Mapping, kein Ausweichen.
2. Traefik kann HA nicht per Container-DNS finden. Lösung im Repo: Traefik bekommt
   `extra_hosts: host.docker.internal:host-gateway` und einen **File-Provider**-Eintrag
   (`core/dynamic/homeassistant.yml`), der auf `http://host.docker.internal:8123` zeigt.
3. HA muss den Proxy kennen, sonst lehnt es die Anfragen mit `400: Bad Request` ab.
   In `configuration.yaml`:

```yaml
http:
  use_x_forwarded_for: true
  trusted_proxies:
    - 172.18.0.0/16     # das edge-Subnetz: docker network inspect edge
    - 127.0.0.1
```

Das ist der Fehler, an dem praktisch jeder einmal hängt.

## Pi-hole: der 80/443-Konflikt

Existiert hier nicht, weil Pi-hole **nichts auf 80/443 des Hosts mappt**. Pi-hole v6 hat
seinen Webserver in FTL integriert; im Container lauscht er auf 80, nach außen gemappt
wird nur `8080:80`. Traefik spricht Pi-hole containerintern auf Port 80 an.

Damit hast du:

- `https://pihole.$DOMAIN` — normaler Weg, mit gültigem Zertifikat
- `http://$PI_IP:8080` — Notausgang, wenn Traefik streikt und du DNS reparieren musst

**Wichtig:** Traefik nutzt für den ACME-DNS-01-Challenge feste externe Resolver
(1.1.1.1 / 9.9.9.9), nicht Pi-hole. Sonst entsteht eine Henne-Ei-Situation: Pi-hole ist
down → DNS kaputt → Traefik kann kein Zertifikat erneuern → du kommst nicht an Pi-hole.

Pi-hole macht **kein DHCP**. Das bleibt im Router. Ein Container, der DHCP für dein
ganzes Haus macht, ist ein Single Point of Failure, den du beim Basteln ständig neu
startest. Im Router trägst du nur den DNS-Server ein.

## TLS: echte Zertifikate für LAN-Adressen

Das Problem: Let's Encrypt stellt keine Zertifikate für `.local`, `.home.arpa` oder
IP-Adressen aus, und HTTP-01 geht nicht ohne Portfreigabe.

**Empfohlener Weg — DNS-01-Challenge mit eigener Domain:**

1. Beliebige günstige Domain, DNS bei **Cloudflare** (oder Hetzner/deSEC/Netcup — Traefik
   unterstützt rund 100 Provider).
2. Wildcard-A-Record: `*.home.example.com → 192.168.1.50`. Eine private IP im öffentlichen
   DNS ist zulässig und üblich.
3. API-Token mit Recht `Zone:DNS:Edit` für genau diese Zone → `CF_DNS_API_TOKEN`.
4. Traefik holt ein Wildcard-Zertifikat für `*.home.example.com`.

Ergebnis: grünes Schloss auf jedem Gerät, **keine einzige Portfreigabe im Router**, kein
Zertifikat manuell verteilen. Die Domain kostet rund 10 Euro im Jahr und spart viel Ärger.

Die Alternative — eigene CA mit `mkcert` — bedeutet, dass du das Root-CA auf jedem Handy,
Tablet, Laptop und in einigen Apps einzeln installierst. Bei aktuellem Android und iOS ist
das unangenehm geworden. Mach das nur, wenn du wirklich keine Domain willst.

**Fernzugriff:** kein Port-Forwarding. Installiere **Tailscale** auf dem Pi (als
Subnet-Router für 192.168.1.0/24) und auf deinen Geräten. Dann funktionieren dieselben
Hostnamen mit denselben Zertifikaten von unterwegs, ohne dass etwas im Internet steht.

## Eureka: brauchst du hier nicht

Ehrlich: nein. Eureka löst die Frage "welche Instanzen von Service X gibt es gerade und
unter welcher Adresse" — ein Problem dynamischer Multi-Host-Cluster mit Autoscaling.

Auf **einem** Host mit Docker Compose gilt:

- Docker hat einen eingebauten DNS-Server. `http://api:8000` funktioniert einfach.
- Container-Namen sind stabil, IPs sind egal.
- Es gibt genau eine Instanz pro Service.

Eureka würde kosten: eine JVM (rund 400 MB RAM), einen zweiten Discovery-Mechanismus neben
Docker-DNS, einen zusätzlichen Startup-Abhängigkeitsbaum — und bei einem **Python**-Backend
obendrein `py-eureka-client` als Fremdkörper, weil Eureka ein Spring-Cloud-Konzept ist.

Was du stattdessen nimmst:

- **Service Discovery:** Docker-DNS (Container-Name).
- **Routing / L7-Gateway:** Traefik, per Docker-Labels. Das *ist* die Discovery-Ebene —
  Traefik beobachtet den Docker-Socket und konfiguriert sich selbst, wenn Container kommen
  und gehen. Genau die Funktion, die du von Eureka plus Spring Cloud Gateway erwartest.
- **Konfiguration:** `.env` plus Compose. Kein Config-Server nötig.

Eureka lohnt sich ab mehreren Hosts, Autoscaling oder echten Spring-Cloud-Services. Dann
ist allerdings k3s mit Kubernetes-Services die naheliegendere Antwort. Ein auskommentierter
Eureka-Block liegt trotzdem in `apps/docker-compose.yml`: Wenn du Spring Cloud *lernen*
willst, ist das ein völlig legitimer Grund, und dann ist es ein Einzeiler zum Aktivieren.

## Postgres oder MongoDB: nimm Postgres

Eine Datenbank, nicht zwei. Gründe:

- pgAdmin wolltest du ohnehin — das gehört zu Postgres.
- `JSONB` deckt den Dokumenten-Anwendungsfall ab, inklusive GIN-Index. Für alles unterhalb
  von "wirklich schemalose Daten im TB-Bereich" reicht das.
- Home Assistant kann seinen Recorder auf Postgres legen. Das ist ein echter Gewinn:
  SQLite unter Dauer-Writes ist der Hauptgrund, warum HA-Installationen mit der Zeit
  langsam werden. Eigene DB `homeassistant`, eigener User — in `data/initdb/` vorbereitet.
- MongoDB auf ARM64 läuft (offizielle arm64-Images seit 4.4), aber Lizenz (SSPL) und
  zusätzlicher RAM-Bedarf lohnen sich nur, wenn du Mongo-spezifisch etwas brauchst.

Wenn dein Backend später wirklich Dokumente braucht: erst Postgres mit `JSONB` versuchen,
Mongo erst, wenn das nachweislich nicht reicht.

## pgAdmin

Braucht rund 350 MB und ist eine Web-App mit eigenem Login, also zusätzliche
Angriffsfläche. Sie ist im Repo enthalten und hängt hinter Traefik mit einer
IP-Allowlist-Middleware auf dein LAN.

Überlege trotzdem die schlankere Variante: Postgres ist auf `127.0.0.1:5432` gebunden, also
machst du vom Desktop aus

```bash
ssh -L 5432:127.0.0.1:5432 pi@192.168.1.50
```

und verbindest DBeaver, DataGrip oder pgAdmin-Desktop auf `localhost:5432`. Kein Container,
keine Angriffsfläche, besseres Tooling. `make pg-tunnel` macht genau das.

## Images bauen: nicht auf dem Pi

Der Pi 5 kann `docker build` für Backend und Frontend, aber ein React-Build mit `npm ci`
dauert dort mehrere Minuten und schreibt viel auf die SSD. Besser:

**GitHub Actions → GHCR → `docker compose pull` auf dem Pi.**
GitHub bietet kostenlose ARM64-Runner für öffentliche Repos, sonst
`docker/build-push-action` mit `platforms: linux/arm64` plus QEMU. Eine fertige
Workflow-Datei liegt in `apps/github-workflow-example.yml`.

Auf dem Pi bleibt dann nur:

```bash
make deploy-apps     # pull + up -d
```

Für die Entwicklung selbst laufen Backend und Frontend lokal auf deinem Windows-Rechner
gegen den Postgres auf dem Pi (per SSH-Tunnel). Der Pi ist Laufzeitumgebung, keine
Entwicklungsmaschine.

## Was bewusst nicht drin ist

| Weggelassen | Warum |
|---|---|
| Portainer | Compose-Dateien im Git sind die Quelle der Wahrheit. Eine GUI, die daran vorbei ändert, macht den Zustand undurchschaubar. Für reines Anschauen reicht Dozzle. |
| Watchtower (Auto-Update) | Bei Postgres und Home Assistant sind automatische Major-Updates ein Weg, ein funktionierendes System nachts kaputtzumachen. Updates laufen manuell nach Backup, siehe Runbook. |
| Nginx Proxy Manager | Klickbar, aber die Konfiguration liegt dann in einer SQLite-Datei statt im Git. Traefik-Labels stehen neben dem Service, den sie routen. |
| k3s | Ein Node, ein Admin. Der Mehraufwand zahlt sich erst bei mehreren Hosts aus. |
| Unbound als rekursiver Resolver | Kannst du später ergänzen; Quad9 als Upstream ist für den Anfang ausreichend und weniger fehleranfällig. |
