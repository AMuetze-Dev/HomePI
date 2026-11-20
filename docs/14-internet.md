# 14 — Aus dem Internet erreichbar

Bis hierher stand nichts im Internet: Das Zertifikat kam per DNS-01, der Name
zeigte auf die private Adresse des Pi. Dieses Kapitel öffnet **die Website samt
API** nach außen — damit Spieler das Tischtennisturnier auf dem eigenen Handy
sehen und die Website von überall bedienbar ist.

Der Weg dafür ist **Tailscale Funnel**. Kosten: keine. Die Adresse lautet

```
https://homelab.<tailnet>.ts.net
```

— `<tailnet>` vergibt Tailscale (etwa `tail1a2b3c`), sie steht nach dem
Einrichten in `tailscale funnel status`. Hübsch ist sie nicht; für Spieler in
der Halle und für den eigenen Zugriff von unterwegs genügt sie.

## Warum Funnel und keine Portfreigabe

Der erste Anlauf war DuckDNS mit einer Portfreigabe in der Fritz!Box. Er ist
an drei Dingen gescheitert, und alle drei fallen mit Funnel weg:

- **DynDNS.** Die Fritz!Box muss jede neue Adresse des Anschlusses melden. Als
  das einmal ausblieb, zeigte der Name auf eine fremde Adresse, und nichts war
  erreichbar. Manche Arbeitgeber sperren DynDNS-Namen außerdem ganz. Funnel
  baut die Verbindung vom Pi aus auf; welche Adresse der Anschluss gerade hat,
  ist egal.
- **IPv6.** DuckDNS trug die IPv6-Adresse der Fritz!Box ein. Wer IPv6 hatte,
  landete beim Router und sah eine Zertifikatswarnung.
- **Die Freigabe selbst.** Port 443 außen gehört der Fritz!Box, und eine
  Freigabe auf den falschen Port am Pi stellte den LAN-Eingang samt Home
  Assistant ins Internet. Ohne Freigabe kann das nicht passieren.

## Was danach öffentlich ist — und was nicht

|                                                  | aus dem Internet | im LAN |
| ------------------------------------------------ | :--------------: | :----: |
| Website, API unter `/api` — unter dem ts.net-Namen |      ja        |   ja   |
| `app.<domain>`, `api.<domain>`                   |       nein       |   ja   |
| Traefik-Dashboard, Logs, Status                  |       nein       |   ja   |
| Pi-hole, pgAdmin, Home Assistant                 |       nein       |   ja   |

Das „nein" hängt an einem **eigenen Eingang**: Tailscale reicht die Anfragen
auf dem Pi an `127.0.0.1:8081` weiter, Traefiks Eingang `funnel`. Dort hängen
nur die Router, die ihn ausdrücklich nennen — `funnel-web`, `funnel-api` und
`funnel-anmelden`. Ein neuer Dienst ist damit erst einmal **nicht**
öffentlich. Weil der Eingang nur an `127.0.0.1` horcht, erreicht ihn aus dem
Netz niemand an Tailscale vorbei.

Dashboard, Logs, Status, Pi-hole, pgAdmin, Zigbee2MQTT und Home Assistant
tragen zusätzlich `lan-only@file` (LAN und Tailscale-Bereich). Das ist die
zweite Linie, falls doch jemand eine Portfreigabe auf den Pi anlegt.

### Eine Adresse für Seite und API

Die Website ruft ihre API unter **`/api`** auf, unter derselben Adresse wie sich
selbst; Traefik schneidet das Präfix ab und reicht an das Gateway weiter
(Middleware `api-praefix@file`). So funktioniert dasselbe Bundle unter
`app.<domain>` im LAN und unter dem ts.net-Namen von außen. CORS ist nicht
nötig: Seite und API haben einen Ursprung.

## Was die Anmeldung schützt

Seit die Anmeldung öffentlich ist, kann jeder es versuchen, so oft er will.
Drei Schichten, von außen nach innen:

1. **Traefik bremst je Adresse.** Zehn Versuche je Minute und Absender auf
   `/api/auth/anmelden`, danach 429. Am Eingang `funnel` kommt jede Verbindung
   vom Docker-Proxy, also von **einer** Adresse; die echte steht in
   `X-Forwarded-For`, gesetzt von Tailscale. Deshalb gibt es eigene Bremsen
   (`anmelde-bremse-funnel`, `rate-limit-funnel`), die diesen Kopf lesen —
   sonst teilten sich alle Besucher ein Limit, und zwanzig Spieler vor der
   Anzeigetafel brauchten es gemeinsam auf. Geglaubt wird der Kopf nur, wenn
   die Verbindung von `127.0.0.1` oder aus `172.16.0.0/12` kommt.
2. **Das Gateway sperrt je Name.** Fünf Fehlversuche in einer Viertelstunde,
   danach wird für diesen Benutzernamen auch das richtige Passwort abgewiesen,
   bis der älteste Fehlversuch aus dem Fenster fällt
   (`homepi_core.auth.dienst.wartezeit`). Das trifft auch Namen, die es nicht
   gibt — sonst verriete die Sperre, welche es gibt. Der Preis: Wer einen Namen
   kennt, kann ihn eine Viertelstunde lang aussperren. Das ist ärgerlich und
   kein Einbruch.
3. **Das Passwort selbst.** Argon2id, also teuer zu prüfen. Gegen ein Passwort
   aus vier Wörtern sind 480 Versuche am Tag nichts — gegen „Sommer2026" schon.
   Vor dem Freischalten jedes Konto prüfen, besonders die mit Recht auf
   `verwaltung`.

Dazu kommt, was schon vorher galt: Sitzungs-Cookie `HttpOnly`, `Secure` und
`SameSite=Lax`, HSTS über `secure-headers@file`, OpenAPI in Produktion aus.

## Einschalten

Auf dem Pi, im Repo:

```bash
git pull
make up-core      # Traefik mit dem Eingang "funnel" auf 127.0.0.1:8081
make up-apps      # Website und API auch an diesem Eingang
make funnel       # Tailscale installieren, anmelden, Funnel einschalten
```

`make funnel` (`scripts/50-tailscale-funnel.sh`) fragt zweimal nach dem
Browser:

1. **Anmelden.** Ein Link `https://login.tailscale.com/a/…` — öffnen, mit dem
   eigenen Konto anmelden, den Pi aufnehmen. Ein Tailscale-Konto ist kostenlos.
2. **Funnel erlauben.** Ein Link `https://login.tailscale.com/f/funnel?…` —
   dort HTTPS-Zertifikate und Funnel für das Tailnet einschalten.

Danach zeigt `tailscale funnel status` die Adresse. Die Einstellung übersteht
Neustarts; `make funnel` muss nur einmal laufen.

**Die Adresse in die `.env`** — als `OEFFENTLICHE_URL='https://homelab.<tailnet>.ts.net'`,
danach `make up-apps`. Die Startseite zeigt sie dann als QR-Code (Knopf
„QR-Code zeigen“ unten), und zwar auch, wenn sie selbst im LAN unter
`app.<domain>` läuft: Diesen Namen löst nur das Pi-hole auf, ein Handy im
Mobilfunk käme dort nie an. Ohne Eintrag nimmt der Code die Adresse, unter der
die Seite gerade geöffnet ist.

**Von außen prüfen** — WLAN am Handy aus, mobile Daten an:

- `https://homelab.<tailnet>.ts.net` zeigt die Startseite mit gültigem Schloss.
- `https://homelab.<tailnet>.ts.net/modul/tischtennis` zeigt die Anzeigetafel
  **ohne** Anmeldung, und sie füllt sich — das ist die API unter `/api`.

Der erste Aufruf nach dem Einschalten kann ein, zwei Minuten dauern, bis der
Name überall bekannt ist.

## Die Fritz!Box

Für den Funnel braucht es dort **nichts**. Eine Portfreigabe auf den Pi aus
früheren Anläufen gehört gelöscht (_Internet → Freigaben → Portfreigaben_).

## Im LAN

Im eigenen Netz bleibt alles unter `<dienst>.<domain>`, mit dem Zertifikat aus
DNS-01. Dafür muss jedes Gerät **Pi-hole** fragen: Pi-hole beantwortet die
Domain samt allen Unternamen selbst mit der privaten Adresse des Pi
(`FTLCONF_misc_dnsmasq_lines` in `stacks/dns/docker-compose.yml`), und die
Frage nach IPv6 (AAAA) bleibt leer (`local=/<domain>/`). Was der öffentliche
DNS-Eintrag sagt, spielt dann keine Rolle — er muss nicht einmal aktuell sein.

Fragen die Geräte stattdessen die Fritz!Box, bekommen sie den öffentlichen
Eintrag und finden den Pi nicht. Deshalb in der Fritz!Box Pi-hole als
DNS-Server eintragen (_Internet → Zugangsdaten → DNS-Server_) und die Domain
beim DNS-Rebind-Schutz als Ausnahme (_Heimnetz → Netzwerk →
Netzwerkeinstellungen_).

## Ausschalten

```bash
sudo tailscale funnel reset
```

Danach ist nichts mehr öffentlich. Der Eingang in Traefik darf bleiben — ohne
Funnel kommt dort nichts an.
