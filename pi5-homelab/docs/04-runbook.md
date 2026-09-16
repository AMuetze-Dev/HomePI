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

| Meldung | Ursache |
|---|---|
| `invalid credentials` / `403` | Cloudflare-Token falsch oder ohne `Zone:DNS:Edit` auf diese Zone |
| `timeout waiting for DNS record` | Propagation dauert; bei Cloudflare normalerweise unter 60 s. Länger heißt: falsche Zone. |
| `too many certificates already issued` | Let's Encrypt Rate Limit (5 pro Domain pro Woche). Zum Testen `--certificatesresolvers.cloudflare.acme.caserver=https://acme-staging-v02.api.letsencrypt.org/directory` setzen. |

Die Datei `${DATA_ROOT}/traefik/letsencrypt/acme.json` muss `chmod 600` sein, sonst
verweigert Traefik den Start.

### `400: Bad Request` bei Home Assistant

`trusted_proxies` in `configuration.yaml` fehlt oder hat das falsche Subnetz:

```bash
docker network inspect edge --format '{{range .IPAM.Config}}{{.Subnet}}{{end}}'
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
vorübergehend auf `9.9.9.9` zurückstellen — deshalb steht DHCP bewusst *nicht* im Pi-hole.

### NVMe: `I/O timeout`, Boot hängt, sporadische Abstürze

Erst Netzteil prüfen (`vcgencmd get_throttled`, Bit 0 = Unterspannung). Dann APST
deaktivieren — in `/boot/firmware/cmdline.txt` an dieselbe Zeile anhängen:

```
nvme_core.default_ps_max_latency_us=0
```

Hilft das nicht, PCIe auf Gen 2 zurück (`dtparam=pciex1_gen=2` in `config.txt`). Bleibt es
instabil, ist es die SSD — manche Modelle vertragen sich schlicht nicht mit dem Pi 5.

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
