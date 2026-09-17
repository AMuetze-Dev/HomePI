# HomePI — Orientierung für Agenten

Selbst gehostete Dienste auf einem Raspberry Pi 5. Ein Gateway, viele
Artefakte, eine Oberfläche.

**Arbeitest du an einem einzelnen Artefakt?** Dann ist `modules/<name>/AGENTS.md`
dein Auftrag, nicht diese Datei. Hier steht nur, wie das Ganze zusammenhängt.

---

## Aufbau

```
packages/homepi-core/   Grundgerüst jedes Artefakts + homepi-CLI
modules/<name>/         Artefakte, die im Gateway laufen  ← der Normalfall
services/gateway/       lädt die Artefakte, sonst keine Fachlichkeit
services/web/           die Hülle: Startseite, Routing, Designsystem
stacks/                 Docker-Compose für den Pi
scripts/                Einrichtung, Backup, Diagnose
docs/                   Begründungen. Lies sie, bevor du etwas umbaust.
```

## Der Kern in vier Sätzen

1. Ein **Artefakt** ist ein Python-Paket mit einem `APIRouter`, das sich über
   einen Entry Point `homepi.module` anmeldet.
2. Das **Gateway** findet es beim Start, hängt es unter `/<name>` ein und nennt
   es in `GET /module`.
3. Die **Startseite** baut ihre Kacheln aus genau dieser Liste — ein neues
   Artefakt erscheint dort ohne Frontend-Änderung.
4. Ohne eigene Oberfläche bekommt es die **generische Ansicht**, die seine
   Endpunkte aus dem OpenAPI-Schema liest.

Warum Modul und nicht Container: zehn FastAPI-Container wären 2 GB auf einem
16-GB-Pi, zehn Module in einem Prozess sind rund 250 MB.
Ausführlich: [docs/06-artefakte.md](docs/06-artefakte.md).

---

## Neues Artefakt

```bash
homepi new <name> --titel "Anzeigename"
```

Erzeugt Backend, Oberfläche, Tests und eine `AGENTS.md` mit dem Auftrag —
und trägt das Artefakt im Gateway und im Frontend-Register ein.

```bash
cd services/gateway && uv sync    # Modul in die Umgebung holen
make dev                          # Kachel erscheint
```

Rezept mit allen Schritten: [docs/09-artefakt-bauen.md](docs/09-artefakt-bauen.md).

**Einen Agenten damit beauftragen:** [docs/10-auftrag-artefakt.md](docs/10-auftrag-artefakt.md)
ist als alleinige Arbeitsanweisung gedacht — vollständig, ohne weiteren Kontext.

---

## Regeln, die nicht verhandelbar sind

**Schichten.** `dienst.py` entscheidet und ist rein — keine DB, kein `await`.
`speicher.py` macht I/O und entscheidet nichts. `router.py` übersetzt. Der
Grund ist messbar: Unit-Tests laufen dadurch in Millisekunden, und nur deshalb
wird die rot-grün-Schleife wirklich benutzt.

**Tests zuerst.** Test schreiben, **scheitern sehen**, dann Code. Ein Test, den
du nie hast scheitern sehen, prüft möglicherweise nichts.

**Keine festen Werte im Frontend.** Jede Farbe, jeder Abstand kommt aus
`src/styles/tokens.css`. Zugriff in Tests über Rollen und sichtbaren Text, nie
über CSS-Klassen.

**Keine eigene Infrastruktur.** FastAPI-App, CORS, Middleware, Health,
Logging, Fehlerformat, DB-Engine kommen aus `homepi-core`. Wer das nachbaut,
hat die falsche Datei geöffnet.

**Zeilenenden LF.** Entwickelt wird unter Windows, ausgeführt unter Linux.
`.gitattributes` erzwingt es; neue `.sh`-Dateien brauchen zusätzlich
`git update-index --chmod=+x`.

---

## Befehle

```bash
make dev             # Umgebung: Frontend 5173, API 18000, Postgres 15432
make test            # alles, was die CI auch prüft
make smoke           # gegen die laufende Umgebung
make fmt
```

An **einem** Artefakt arbeiten — alles andere bleibt aus dem Weg:

```bash
make modul N=<name>        # wo liegen Backend und Oberfläche?
make dev N=<name>          # Gateway lädt nur dieses Artefakt
make tdd-api P=modules/<name>
make tdd-web N=<name>      # vitest nur für dessen Oberfläche
make test-modul N=<name>   # beide Hälften vollständig prüfen
```

Integrationstests laufen gegen die Datenbank `test`, nicht `app` — sie legen
Tabellen an und löschen sie wieder.

---

## Branches

`feature/*` → `develop` → `main`. Auf `main` baut die Pipeline arm64-Images,
`homepi deploy -s <name>` rollt aus. Nie direkt auf `main` committen.

---

## Bevor du etwas für fertig hältst

```bash
make test && make smoke
```

Dazu, was kein Werkzeug prüft: Ladezustände ohne Layoutsprung, ein
Erstzustand, der erklärt was zu tun ist, Backend-Meldungen wörtlich beim
Benutzer, ein fehlgeschlagenes Formular behält seine Eingabe, und bei 375 px
ist alles ohne horizontales Scrollen erreichbar.

---

## Wo was begründet ist

| Frage | Datei |
|---|---|
| Warum diese Netz- und Container-Topologie? | [docs/03-architecture.md](docs/03-architecture.md) |
| Branches, TDD-Schleife, CI/CD | [docs/05-workflow.md](docs/05-workflow.md) |
| Modul oder eigener Container? | [docs/06-artefakte.md](docs/06-artefakte.md) |
| Lokale Umgebung, Fallstricke unter Windows | [docs/07-lokale-entwicklung.md](docs/07-lokale-entwicklung.md) |
| Designsystem, Tokens, Zugänglichkeit | [docs/08-design.md](docs/08-design.md) |
| Artefakt bauen, Schritt für Schritt | [docs/09-artefakt-bauen.md](docs/09-artefakt-bauen.md) |
| Auftrag zum Übergeben an einen Agenten | [docs/10-auftrag-artefakt.md](docs/10-auftrag-artefakt.md) |
