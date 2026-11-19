# 14 — Aus dem Internet erreichbar

Bis hierher stand nichts im Internet: Das Zertifikat kam per DNS-01, der Name
zeigte auf die private Adresse des Pi, von unterwegs ging es über Tailscale.
Dieses Kapitel öffnet **App und API** nach außen — damit Spieler das
Tischtennisturnier auf dem eigenen Handy sehen und die Website von überall
bedienbar ist. Kosten: keine. DuckDNS und Let's Encrypt sind frei.

## Was danach öffentlich ist — und was nicht

|                                           | aus dem Internet | im LAN / über Tailscale |
| ----------------------------------------- | :--------------: | :---------------------: |
| `app.<domain>` — die Website              |        ja        |           ja            |
| `api.<domain>` — Gateway mit allen Artefakten |   ja         |           ja            |
| Traefik-Dashboard, Logs, Status           |       nein       |           ja            |
| Pi-hole, pgAdmin, Home Assistant          |       nein       |           ja            |

Das „nein" hängt nicht an einer Regel, die jeder Dienst einhalten muss, sondern
an einem **eigenen Eingang**: Der Router leitet von außen auf Port **8443** des
Pi, und auf diesem Traefik-Eingang (`internet`) hängen nur die Router, die ihn
ausdrücklich nennen — `web`, `gateway` und `gateway-anmelden`. Ein neuer Dienst
ist damit erst einmal **nicht** öffentlich. Dashboard, Logs, Status, Pi-hole,
pgAdmin und Zigbee2MQTT tragen zusätzlich `lan-only@file`; selbst ein Versehen
bei den Eingängen ließe sie also noch nicht durch. **Home Assistant nicht** —
es soll auch über Tailscale erreichbar bleiben, und dort schützt es allein der
getrennte Eingang. Wer an seinem Router etwas ändert, prüft deshalb zuerst,
dass dort weiterhin nur `websecure` steht.

## Was die Anmeldung schützt

Seit die Anmeldung öffentlich ist, kann jeder es versuchen, so oft er will.
Drei Schichten, von außen nach innen:

1. **Traefik bremst je Adresse.** `anmelde-bremse@file`: zehn Versuche je
   Minute und Absender auf `/auth/anmelden`, danach 429. Mit der Portfreigabe
   sieht Traefik die echte Adresse des Besuchers.
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

## Vorher prüfen: Hat der Anschluss eine öffentliche IPv4-Adresse?

Ohne sie geht keine Portfreigabe, und alles Weitere läuft ins Leere.

**Fritz!Box:** _Internet → Online-Monitor_. Steht dort eine IPv4-Adresse, ist
alles gut. Steht dort **„DS-Lite"** oder eine Adresse aus `100.64.0.0/10`, teilt
sich der Anschluss die IPv4 mit anderen Kunden — dann weiter unten bei
[Ohne öffentliche IPv4](#ohne-öffentliche-ipv4).

## Einschalten

Auf dem Pi, im Repo:

```bash
git pull
make up-core      # Traefik mit dem neuen Eingang 8443
make up-dns       # Pi-hole beantwortet die Domain im LAN selbst
make up-apps      # App und API auch auf dem Eingang "internet"
```

**Im LAN prüfen, bevor etwas nach außen geht:**

```bash
dig +short app.<domain> @127.0.0.1    # muss die private Adresse des Pi sein
curl -sI https://app.<domain> | head -1
```

Steht dort die private Adresse, kommt das LAN ab jetzt nicht mehr ans
öffentliche DNS — der nächste Schritt ändert also nichts an der Wohnung.

**Am Router** (Fritz!Box: _Internet → Freigaben → Portfreigaben → Gerät für
Freigaben hinzufügen_ → der Pi):

| Protokoll | Port außen | Port am Pi | Wozu                                        |
| --------- | ---------- | ---------- | ------------------------------------------- |
| TCP       | 443        | **8443**   | der Eingang „internet"                      |
| TCP       | 80         | 80         | optional: leitet `http://` auf `https://` um |

**Nicht** 443 auf 443 — dort hängen auch Dashboard, Logs und Home Assistant.

**Dann den Namen auf die öffentliche Adresse stellen:**

```bash
make up-internet
docker logs duckdns    # alle fünf Minuten eine Zeile mit "OK"
```

**Von außen prüfen** — WLAN am Handy aus, mobile Daten an:

- `https://app.<domain>` zeigt die Startseite mit grünem Schloss.
- `https://app.<domain>/modul/tischtennis` zeigt die Anzeigetafel **ohne**
  Anmeldung.
- `https://traefik.<domain>` und `https://ha.<domain>` antworten mit **404**:
  Der Eingang „internet" kennt diese Namen nicht. Kommt dort eine
  Anmeldemaske, hängt ein Admin-Router am falschen Eingang.

## Ausschalten

```bash
docker compose -f stacks/dns/docker-compose.yml --profile internet stop duckdns
curl "https://www.duckdns.org/update?domains=<name>&token=<token>&ip=<private Adresse des Pi>"
```

Dann die Portfreigabe im Router löschen. Die Eingänge in Traefik dürfen
bleiben — ohne Weiterleitung kommt dort nichts an.

## Ohne öffentliche IPv4

Bei DS-Lite gibt es keine eigene IPv4 und damit keine Portfreigabe dafür. Zwei
kostenlose Wege, beide ohne Freigabe am Router:

- **Tailscale Funnel** — nutzt das schon installierte Tailscale.
  `sudo tailscale funnel --bg 8443` leitet `https://<pi>.<tailnet>.ts.net` auf
  den Eingang „internet". Der Name ist dann allerdings der von Tailscale und
  nicht `app.<domain>`; die Website erwartet ihre API heute unter `api.<domain>`
  und bräuchte dafür einen eigenen Build mit `/api` unter demselben Namen.
- **IPv6** — viele DS-Lite-Anschlüsse haben eine öffentliche IPv6-Adresse. Die
  Fritz!Box kann dafür eine IPv6-Freigabe auf den Pi öffnen, und DuckDNS nimmt
  zusätzlich `&ipv6=`. Besucher ohne IPv6 (manche Mobilfunknetze) kommen dann
  aber nicht durch.

ngrok ginge auch, zeigt im kostenlosen Tarif aber jedem Besucher erst eine
Warnseite — für eine Anzeigetafel in der Halle der falsche erste Eindruck.
