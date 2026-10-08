# 04 — Runbook

## Tägliche Kommandos

```bash
make ps            # was läuft
make stats         # RAM/CPU pro Container
make logs C=traefik
make check         # NVMe, PCIe-Speed, Temperatur, Throttling
make cert          # Ablaufdatum des Wildcard-Zertifikats
make backup
```

## Erstinbetriebnahme der Anwendung

Zwei Schritte, die genau einmal nötig sind.

**1. Schema anlegen.** In Produktion steht `DB_SCHEMA_ANLEGEN` auf `false` —
ein Schema ändert man mit einer Migration, nicht beim Start. Beim allerersten
Mal gibt es aber noch nichts zu migrieren:

```bash
APPS="docker compose -f stacks/apps/docker-compose.yml --env-file .env"

$APPS exec gateway homepi schema anlegen --trocken
$APPS exec gateway homepi schema anlegen
```

Erst der Trockenlauf, dann der Ernstfall — so steht vorher auf dem Schirm, was
entsteht. Danach gibt es die Tabellen der Artefakte **und** die der Anmeldung
(`benutzer`, `benutzer_rechte`, `sitzungen`).

`homepi schema` ist ein Startwerkzeug, **kein Migrationssystem**: es legt
Fehlendes an und ändert nichts Vorhandenes. Sobald sich ein Schema zum ersten
Mal ändert, gehört dort Alembic hin.

**Es vergleicht Tabellen und Spalten.** Kommt in einer vorhandenen Tabelle
eine Spalte dazu, kann `create_all` sie nicht nachtragen — der Befehl meldet
das und endet mit Fehler statt mit „alles gut":

```
! benutzer: Spalte(n) passwort_wechseln fehlen
  create_all legt nur fehlende Tabellen an und aendert keine vorhandene.
  Hier gehoert eine Migration hin - von Hand oder mit Alembic.
```

Dieselbe Prüfung hängt als `schema` im `/health`: eine fehlende Spalte setzt
die Instanz auf `degraded`, und die Rauchtests werden nach dem Deploy rot.
Ohne das sieht eine halb migrierte Datenbank aus, als wären die Daten weg —
jede Abfrage auf die betroffene Tabelle scheitert.

Nachsehen, was da ist:

```bash
$APPS exec gateway homepi schema zeigen
```

**2. Das erste Konto.** Zwei Wege, beide gleichwertig.

_Über die Website._ Solange es keinen Verwalter gibt, zeigt sie die
Einrichtungsmaske. Sie verlangt das Einrichtungstoken, das beim Start im Log
steht:

```bash
$APPS logs gateway | grep -A3 "keinen Verwalter"
```

Lesen kann das nur, wer Zugriff auf die Maschine hat — genau das ist die
Absicht. Ohne diese Bedingung würde derjenige die Installation übernehmen, der
als Erster an die frische Adresse kommt.

_Über die Kommandozeile._ Tut dasselbe; danach schließt sich die Maske von
selbst.

```bash
$APPS exec gateway \
  homepi benutzer anlegen aaron --artefakt verwaltung --rolle verwalter
```

Das Passwort wird abgefragt — nie als Argument, sonst stünde es in der
Shell-Historie und in der Prozessliste.

Das Recht `verwaltung` ist das, was sonst „Administrator" heißt: damit lassen
sich weitere Konten anlegen und Rechte vergeben — in der Oberfläche unter
_Verwaltung_. Alles Weitere gibt sich der erste Verwalter dort selbst.

Prüfen:

```bash
$APPS exec gateway homepi benutzer liste
```

Weitere Konten legt der Verwalter in der Oberfläche unter _Verwaltung_ an —
dort genügt ein Name, das Startpasswort erzeugt der Dienst. Der Benutzer
ersetzt es beim ersten Anmelden und kommt bis dahin an kein Artefakt.

Weitere Rechte, Sperren, Löschen: [11-anmeldung.md](11-anmeldung.md).

## Home Assistant auf Postgres umstellen

Erst HA einmal normal einrichten, dann in `configuration.yaml`:

```yaml
recorder:
  db_url: postgresql://ha:DEIN_HA_DB_PASSWORD@127.0.0.1:5432/homeassistant
  purge_keep_days: 30
  commit_interval: 5
```

`127.0.0.1` funktioniert, weil HA im Host-Netz läuft und Postgres dort auf Loopback
gebunden ist. Die bestehende SQLite-Historie wird dabei **nicht** übernommen — entweder
du verzichtest darauf oder du migrierst sie vorher. Für einen frischen Aufbau ist der
Zeitpunkt jetzt der beste.

`commit_interval: 5` reduziert Schreibvorgänge deutlich; der Preis ist, dass die letzten
fünf Sekunden Historie bei einem harten Stromausfall fehlen können.

## Updates

Nicht automatisch. Ablauf:

```bash
make backup
make pull                  # nur Images ziehen, nichts neu starten
make up                    # Container ersetzen
make ps                    # prüfen
```

Vor **Major**-Updates die Release Notes lesen — besonders bei:

- **Postgres** (17 → 18): braucht `pg_upgrade` oder Dump/Restore. Ein einfacher Tag-Wechsel
  startet nicht, weil das Datenverzeichnis versioniert ist. Weg: `pg_dumpall` mit der alten
  Version, Volume leeren, neue Version starten, Dump einspielen.
- **Home Assistant**: Breaking Changes stehen monatlich in den Release Notes. HA hat ein
  eigenes Backup unter Einstellungen → System → Backups — vor jedem Update auslösen.
- **Pi-hole** (v5 → v6): Konfigurationsschema und Env-Variablen haben sich geändert.
  Siehe Kommentarblock in `dns/docker-compose.yml`.

Zurückrollen geht nur, wenn du die Version kennst, die lief. Deshalb: nach jedem
erfolgreichen Update die laufenden Tags festhalten.

```bash
docker ps --format '{{.Names}}\t{{.Image}}' > ~/versions-$(date +%F).txt
```

## Backup und Restore

`make backup` legt unter `${DATA_ROOT}/backups/JJJJ-MM-TT/` ab:

- `postgres-all.sql.gz` — alle Datenbanken inkl. Rollen
- `configs.tar.gz` — HA, Pi-hole, Mosquitto, Kuma, Traefik/ACME
- `homelab-repo.tar.gz` — Compose-Dateien und `.env`

Cron einrichten:

```bash
crontab -e
# 0 3 * * * /home/pi/homelab/scripts/backup.sh >> /home/pi/backup.log 2>&1
```

**Ein Backup auf derselben SSD ist kein Backup.** Aktiviere in `scripts/backup.sh` eine
der `rsync`/`restic`-Zeilen, sobald ein Ziel existiert (USB-Platte, NAS, Cloud).

### Restore auf einen neuen Pi

```bash
# 1. OS + Docker wie in 02-os-bootstrap.md
# 2. Repo und .env zurückspielen
tar -xzf homelab-repo.tar.gz -C ~
# 3. Konfigurationen
sudo tar -xzf configs.tar.gz -C /srv/homelab
# 4. Netze + leerer Postgres
./scripts/30-create-networks.sh && make up-data
# 5. Dump einspielen
gunzip -c postgres-all.sql.gz | docker exec -i postgres psql -U postgres
# 6. Rest
make up
```

Probier das **einmal**, bevor du es brauchst. Ein ungetestetes Backup ist eine Vermutung.

## Troubleshooting

### Traefik bekommt kein Zertifikat

```bash
docker logs traefik 2>&1 | grep -i acme
```

| Meldung                                | Ursache                                                                                                                                                                  |
| -------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| `invalid credentials` / `403`          | Token falsch. Bei Cloudflare fehlt meist `Zone:DNS:Edit` auf genau diese Zone; bei DuckDNS stimmt `DUCKDNS_TOKEN` oder der Name in `DOMAIN` nicht.                       |
| `timeout waiting for DNS record`       | Propagation dauert. Normalerweise unter 60 s. Länger heißt: falsche Zone, oder bei DuckDNS ein Name, der dem Token nicht gehört.                                         |
| `too many certificates already issued` | Let's Encrypt Rate Limit (5 pro Domain pro Woche). Zum Testen `--certificatesresolvers.dns.acme.caserver=https://acme-staging-v02.api.letsencrypt.org/directory` setzen. |
| Ausstellung scheitert bei zwei Namen   | Der Anbieter hält nur einen TXT-Eintrag je Domain (DuckDNS). Nur das Wildcard beantragen, nicht zusätzlich die nackte Domain.                                            |
| Name löst im LAN gar nicht auf         | Fritz!Box-DNS-Rebind-Schutz. Den Namen unter _Heimnetz → Netzwerk → Netzwerkeinstellungen_ als Ausnahme eintragen.                                                       |

Die Datei `${DATA_ROOT}/traefik/letsencrypt/acme.json` muss `chmod 600` sein, sonst
verweigert Traefik den Start.

### `400: Bad Request` bei Home Assistant

HA kennt den Proxy nicht. Im HA-Log steht dann *„A request from a reverse proxy
was received from 172.18.10.x, but your HTTP integration is not set-up for reverse
proxies"*. Seit 2026.x hilft `configuration.yaml` hier nicht mehr — die Werte
gehören nach `${DATA_ROOT}/homeassistant/.storage/http`, Abschnitt `data.stable`:

```bash
docker stop homeassistant
cd /srv/homelab/homeassistant && cp .storage/http .storage/http.sicherung
python3 -c 'import json; p=".storage/http"; d=json.load(open(p)); s=d["data"]["stable"]; s["use_x_forwarded_for"]=True; s["trusted_proxies"]=["172.18.10.0/24"]; json.dump(d, open(p,"w"), indent=2)'
docker start homeassistant
```

Das Subnetz zeigt `docker network inspect edge --format '{{range .IPAM.Config}}{{.Subnet}}{{end}}'`.

### Zeitüberschreitung bei Home Assistant über Traefik

Die Firewall verwirft Traefiks Anfragen — sie kommen aus dem `edge`-Netz, nicht aus
dem LAN. Zu sehen mit `sudo journalctl -k | grep 'UFW BLOCK.*DPT=8123'`. Abhilfe:

```bash
sudo ufw allow from 172.18.10.0/24 to any port 8123 proto tcp comment 'Traefik -> Home Assistant'
```

### Pi-hole startet nicht, Port 53 belegt

```bash
sudo ss -tulpn | grep ':53 '
```

Meist `systemd-resolved`. Lösung in `docs/02-os-bootstrap.md`.

### Pi-hole zeigt alle Anfragen von einer einzigen IP

Dann läuft der Verkehr über Dockers Userland-Proxy statt über iptables-DNAT und die
Absender-IP geht verloren. In `/etc/docker/daemon.json` ergänzen und Docker neu starten:

```json
"userland-proxy": false
```

### Nichts löst mehr auf, nachdem der Router auf Pi-hole zeigt

Notausgang: `http://PI_IP:8080/admin`. Wenn auch das nicht geht, im Router den DNS
vorübergehend auf `9.9.9.9` zurückstellen — deshalb steht DHCP bewusst _nicht_ im Pi-hole.

### NVMe: `I/O timeout`, Boot hängt, sporadische Abstürze

Erst Netzteil prüfen (`vcgencmd get_throttled`, Bit 0 = Unterspannung). Dann APST
deaktivieren — in `/boot/firmware/cmdline.txt` an dieselbe Zeile anhängen:

```
nvme_core.default_ps_max_latency_us=0
```

`scripts/10-os-bootstrap.sh` trägt das inzwischen selbst ein. Ob es wirkt:
`cat /sys/module/nvme_core/parameters/default_ps_max_latency_us` muss `0` zeigen.

Gen 2 ist beim Pi 5 schon die Voreinstellung — `sudo lspci -vv | grep LnkSta` zeigt
dann `5GT/s`. `dtparam=pciex1_gen=2` hilft nur, wenn jemand vorher auf Gen 3 gestellt
hat. Bleibt es instabil, ist es die SSD — manche Modelle vertragen sich schlicht nicht
mit dem Pi 5.

**Woran man es erkennt, wenn die Platte stehen bleibt:** Das Journal des vorigen
Starts (`journalctl --list-boots`) endet Stunden oder Tage vor dem Neustart — mitten
im Satz, ohne Fehlerzeile. Laufende Container antworten weiter, alles, was neu
gestartet oder von der Platte gelesen werden muss, hängt: SSH schließt vor dem Banner
(`kex_exchange_identification`), Zigbee2MQTT und rpi-connect sterben.

### WLAN-Treiber meldet sich jede Sekunde

Im Journal zweimal pro Sekunde `brcmf_cfg80211_scan: Scanning suppressed: status (4)`
und `wlan0: CTRL-EVENT-SCAN-FAILED ret=-11`. Der Treiber `brcmfmac` ist ausgestiegen —
hier genau 24 Stunden nach dem Start — und kommt ohne Neustart nicht zurück.

Hängt der Pi am Kabel, das WLAN ganz abschalten — in `/boot/firmware/config.txt` unter
`[all]`, dann neu starten:

```
dtoverlay=disable-wifi
```

Bewusst nicht in `scripts/10-os-bootstrap.sh`: Ein Pi, der nur per WLAN angebunden ist,
wäre danach nicht mehr erreichbar. Und erst prüfen, dass `eth0` die Standardroute hat
(`ip -4 route show default`) — sonst sägt man den Ast ab, auf dem die SSH-Sitzung sitzt.

### Platte läuft voll

```bash
docker system df
sudo ncdu /var/lib/docker
sudo du -sh /srv/homelab/* | sort -h
```

Typische Kandidaten: alte Images (`docker image prune -af`), HA-Datenbank (`purge_keep_days`
senken), Container-Logs (bei korrekter `daemon.json` maximal 30 MB pro Container).

### Traefik zeigt einen Service nicht

```bash
docker inspect <container> --format '{{json .Config.Labels}}' | jq
```

Die drei üblichen Fehler: `traefik.enable=true` fehlt, der Container hängt nicht im Netz
`edge`, oder `loadbalancer.server.port` zeigt auf den falschen Container-Port (nicht auf
den veröffentlichten Host-Port).

## Sicherheit: was noch offen ist

Der Docker-Socket ist read-only in Traefik gemountet. Read-only heißt trotzdem: wer in
Traefik Code ausführt, kann alle Container und Secrets auslesen. Die saubere Variante ist
ein **Socket-Proxy** (`tecnativa/docker-socket-proxy`), der nur `CONTAINERS=1` und
`NETWORKS=1` durchlässt. Lohnt sich, sobald du irgendetwas aus dem Internet erreichbar
machst — für ein reines LAN-Setup ist es eine sinnvolle Ausbaustufe, kein Tag-1-Thema.

Weitere Ausbaustufen in sinnvoller Reihenfolge:

1. **Tailscale** statt Portfreigabe für den Fernzugriff.
2. **Offsite-Backup** aktivieren.
3. **Prometheus + Grafana + node-exporter + cAdvisor** für Trends (RAM, SSD-Verschleiß,
   Temperatur). Kostet rund 600 MB RAM, die du hast.
4. **Authelia oder Pocket-ID** als Single-Sign-On vor die Admin-Oberflächen, statt
   Basic Auth pro Dienst.
5. **Socket-Proxy** vor Traefik und Dozzle.
