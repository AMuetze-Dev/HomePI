# 14 — Aus dem Internet erreichbar

Bis hierher stand nichts im Internet: Das Zertifikat kam per DNS-01, der Name
zeigte auf die private Adresse des Pi, von unterwegs ging es über Tailscale.
Dieses Kapitel öffnet **die Website samt API** nach außen — damit Spieler das
Tischtennisturnier auf dem eigenen Handy sehen und die Website von überall
bedienbar ist. Kosten: keine. DuckDNS und Let's Encrypt sind frei.

Von außen heißt die Adresse **`https://app.<domain>:8443`**. Port 443 bleibt
außen frei — die Fritz!Box braucht ihn oft selbst für ihren eigenen
Fernzugang.

## Was danach öffentlich ist — und was nicht

|                                              | aus dem Internet | im LAN / über Tailscale |
| -------------------------------------------- | :--------------: | :---------------------: |
| `app.<domain>` — die Website, API unter `/api` |  ja (`:8443`)  |           ja            |
| `api.<domain>` — das Gateway unter eigenem Namen |    nein      |           ja            |
| Traefik-Dashboard, Logs, Status              |       nein       |           ja            |
| Pi-hole, pgAdmin, Home Assistant             |       nein       |           ja            |

Das „nein" hängt nicht an einer Regel, die jeder Dienst einhalten muss, sondern
an einem **eigenen Eingang**: Die Fritz!Box leitet von außen auf Port **8443 des
Pi**, und auf diesem Traefik-Eingang (`internet`) hängen nur die Router, die ihn
ausdrücklich nennen — `web`, `app-api` und `app-anmelden`. Ein neuer Dienst ist
damit erst einmal **nicht** öffentlich. Dashboard, Logs, Status, Pi-hole,
pgAdmin und Zigbee2MQTT tragen zusätzlich `lan-only@file`. **Home Assistant
nicht** — es soll auch über Tailscale erreichbar bleiben, und dort schützt es
allein der getrennte Eingang. Deshalb ist die Freigabe auf Port 443 des Pi
gefährlich (siehe unten): Dort hängt Home Assistant.

### Eine Adresse für Seite und API

Die Website ruft ihre API unter **`/api`** auf, unter derselben Adresse wie sich
selbst; Traefik schneidet das Präfix ab und reicht an das Gateway weiter
(Router `app-api`, Middleware `api-praefix@file`). Früher stand im Bundle fest
`https://api.<domain>` — unter `https://app.<domain>:8443` lud die Seite dann
zwar, aber jeder Aufruf ging an Port 443, und der ist von außen zu. Mit `/api`
funktioniert dieselbe Seite im LAN, über Tailscale und aus dem Internet, egal
unter welchem Port. CORS ist dafür nicht mehr nötig: Seite und API haben einen
Ursprung.

## Was die Anmeldung schützt

Seit die Anmeldung öffentlich ist, kann jeder es versuchen, so oft er will.
Drei Schichten, von außen nach innen:

1. **Traefik bremst je Adresse.** `anmelde-bremse@file`: zehn Versuche je
   Minute und Absender auf `/api/auth/anmelden`, danach 429. Mit der
   Portfreigabe sieht Traefik die echte Adresse des Besuchers.
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

> **Ehrlich gesagt:** Wer die Website nur selbst von unterwegs bedienen will,
> braucht dieses Kapitel nicht — Tailscale kann das schon, ohne dass etwas im
> Internet steht. Gebraucht wird es für Menschen, die kein Tailscale haben:
> die Spieler beim Turnier.

## DuckDNS: hält die Fritz!Box aktuell

Der DuckDNS-Eintrag zeigt auf die **öffentliche** Adresse des Anschlusses; die
Fritz!Box pflegt ihn selbst (_Internet → Freigaben → DynDNS_, Anbieter
„Benutzerdefiniert" mit der Update-Adresse von DuckDNS). Im Homelab läuft dafür
nichts.

Genau das brach vorher den Zugriff im eigenen Netz: Der Name zeigte nach außen,
und jeder Aufruf aus dem Wohnzimmer ging erst zum Router. **Pi-hole beantwortet
die Domain deshalb samt allen Unternamen selbst** mit der privaten Adresse des
Pi (`FTLCONF_misc_dnsmasq_lines` in `stacks/dns/docker-compose.yml`). Im LAN
merkt man nicht, wohin DuckDNS zeigt — und der DNS-Rebind-Schutz der Fritz!Box
aus docs/03 ist nebenbei erledigt, weil die Frage ihn nie erreicht.

Das Zertifikat bleibt unberührt: Traefik holt es per DNS-01 über einen
TXT-Eintrag, die Fritz!Box ändert nur den A-Eintrag. Die beiden kommen sich
nicht in die Quere.

## Einschalten

Auf dem Pi, im Repo:

```bash
git pull
make up-dns       # Pi-hole beantwortet die Domain im LAN selbst
make up-core      # Traefik mit dem Eingang "internet" auf 8443
make up-apps      # Website und API auf beiden Eingängen
```

Die Website braucht ein **neues Image** — die API-Adresse steht zur Build-Zeit
im Bundle, und die alte zeigt auf `api.<domain>`. Nach dem Push auf `develop`
baut die Pipeline es; danach `make pull` und noch einmal `make up-apps`. Die
Repository-Variable `VITE_API_URL` liest der Workflow nicht mehr und darf weg.

**Im LAN prüfen:**

```bash
dig +short app.<domain> @127.0.0.1         # die private Adresse des Pi
curl -s https://app.<domain>/api/health     # {"status":"ok", ...}
```

**An der Fritz!Box** (_Internet → Freigaben → Portfreigaben_ → der Pi):

| Protokoll | Port außen | Port am Pi | Wozu                   |
| --------- | ---------- | ---------- | ---------------------- |
| TCP       | 8443       | **8443**   | der Eingang „internet" |

> **Nicht 8443 auf 443.** Port 443 des Pi ist der Eingang fürs LAN — dort
> hängen Dashboard, Logs und Home Assistant, und Home Assistant hat kein
> `lan-only`. Eine Freigabe dorthin stellt es ins Internet.

**Von außen prüfen** — WLAN am Handy aus, mobile Daten an:

- `https://app.<domain>:8443` zeigt die Startseite mit grünem Schloss.
- `https://app.<domain>:8443/modul/tischtennis` zeigt die Anzeigetafel
  **ohne** Anmeldung, und sie füllt sich — das ist die API unter `/api`.
- `https://ha.<domain>:8443` und `https://traefik.<domain>:8443` antworten mit
  **404**: Der Eingang „internet" kennt diese Namen nicht. Kommt dort eine
  Anmeldemaske, zeigt die Freigabe auf den falschen Port.

Derselbe Link mit `:8443` funktioniert auch im LAN: Pi-hole schickt den Namen
zum Pi, und dort horcht Port 8443 direkt.

## Ausschalten

Die Portfreigabe in der Fritz!Box löschen. Die Eingänge in Traefik dürfen
bleiben — ohne Weiterleitung kommt dort nichts an. DuckDNS darf weiter auf die
öffentliche Adresse zeigen; im LAN antwortet ohnehin Pi-hole.

## Ohne öffentliche IPv4

Bei DS-Lite (Fritz!Box: _Internet → Online-Monitor_ zeigt „DS-Lite" oder eine
Adresse aus `100.64.0.0/10`) gibt es keine eigene IPv4 und damit keine
Portfreigabe dafür. Zwei kostenlose Wege, beide ohne Freigabe am Router:

- **Tailscale Funnel** — nutzt das schon installierte Tailscale.
  `sudo tailscale funnel --bg 8443` leitet `https://<pi>.<tailnet>.ts.net` auf
  den Eingang „internet". Seit die API unter `/api` liegt, braucht die Website
  dafür nichts weiter — nur in Traefik einen Router für diesen Namen.
- **IPv6** — viele DS-Lite-Anschlüsse haben eine öffentliche IPv6-Adresse. Die
  Fritz!Box kann dafür eine IPv6-Freigabe auf den Pi öffnen, und DuckDNS nimmt
  zusätzlich `&ipv6=`. Besucher ohne IPv6 (manche Mobilfunknetze) kommen dann
  aber nicht durch.

ngrok ginge auch, zeigt im kostenlosen Tarif aber jedem Besucher erst eine
Warnseite — für eine Anzeigetafel in der Halle der falsche erste Eindruck.
