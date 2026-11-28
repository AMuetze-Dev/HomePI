# Artefakt „quiz" — Auftrag für den Agenten

Dieses Verzeichnis ist ein **lauffähiges, leeres Artefakt**. Verdrahtung,
Tests und Deploy stehen bereits. Du füllst die Fachlichkeit ein.

Lies zuerst [`../../docs/06-artefakte.md`](../../docs/06-artefakte.md) — dort
steht, warum ein Artefakt ein Modul im Gateway ist und kein eigener Container.

---

## 1. Was bereits funktioniert

Nicht neu bauen, nicht umbauen:

| | |
|---|---|
| Anmeldung | Entry Point `homepi.module` in `pyproject.toml` → Gateway findet das Modul beim Start |
| Routing | Router hängt unter `/quiz`; Traefik leitet `api.<domain>/quiz` dorthin. **`GET /quiz/` muss antworten** - daran erkennt der Rauchtest, dass das Modul wirklich eingehängt ist |
| Kachel | Startseite liest `GET /module` und zeigt „Quiz" — ohne Frontend-Änderung |
| Zugriff | `zugang=Zugang.OEFFENTLICH` in `__init__.py`: Mitspieler brauchen kein Konto. Die Prüfung hängt **nicht** am Router - jeder Endpunkt der Leitung trägt `erfordert(...)`, und `tests/unit/test_anmeldung.py` kennt die offenen Endpunkte namentlich |
| Health | `/health` und `/info` kommen aus `homepi-core` |
| Fehlerformat | Jeder Fehler wird RFC 9457 `problem+json`. Eigene Fehler erben von `ServiceError` |
| Logging | JSON in Produktion, Text lokal, `X-Request-ID` in jeder Zeile |
| DB-Sitzung | `DbSitzung` aus `homepi_core.deps` — eine Transaktion je Anfrage. Committet **vor** der Antwort; nie selbst committen |
| Testen | fünf Ebenen, Testdatenbank, bekannte Fallen: `docs/12-testen.md` |
| Tabellen | erben von `homepi_core.Base`; das Gateway legt sie beim Start an |

**Du schreibst nie selbst:** FastAPI-App, CORS, Middleware, Health-Endpunkt,
Datenbank-Engine, Logging-Konfiguration, Dockerfile, Compose-Fragment.

---

## Vor jeder Änderung: was dieses Artefakt besonders macht

Es ist **öffentlich**. Drei Regeln, die daraus folgen:

1. **Ein neuer Endpunkt der Leitung bekommt `dependencies=[LESEN|LEITEN|VERWALTEN]`.**
   Sonst macht `test_ohne_konto_geht_genau_die_liste` die CI rot - und das
   ist gewollt. Ein neuer öffentlicher Endpunkt gehört dort mit Begründung in
   `OHNE_KONTO`.
2. **Spieler-Endpunkte hängen an `hole_spieler`** (Token im Cookie). Nur der
   Beitritt geht ohne.
3. **`Rundenstand` ist öffentlich.** Was dort hinzukommt, sieht jeder mit dem
   Code. Lösungen nur über `dienst.oeffentliche_frage` und erst bei
   `aufgeloest`; von Mitspielern nur Name und Punkte.

Dazu zwei Regeln aus dem Ausbau:

4. **Eine neue Spalte an einer bestehenden `quiz_*`-Tabelle braucht eine Datei
   in `scripts/migrationen/`** - die Tabellen laufen auf dem Pi. Neue Tabellen
   legt `homepi schema anlegen` selbst an; deshalb stehen Teams und Medien in
   eigenen Tabellen und nicht als Spalten.
5. **`austausch.py` holt nichts aus dem Netz.** Ein importiertes Quiz kann
   beliebige Adressen enthalten; ein Abruf daraus waere ein Zugriff des Pi auf
   Zuruf einer hochgeladenen Datei.

Was das Artefakt kann und warum, steht in [README.md](README.md).

---

## 2. Dateien und ihre Rolle

```
modules/quiz/
  src/homepi_quiz/
    __init__.py    Anmeldung: modul = Modul(id=..., titel=..., router=...)
    schemas.py     Pydantic: was rein- und rausgeht
    modelle.py     SQLAlchemy: Tabellen (löschen, wenn kein DB-Bedarf)
    dienst.py      REINE Fachlogik - keine DB, kein await, keine Fixtures
    austausch.py   REIN: Battle.Net- und eigene ZIPs lesen und schreiben
    speicher.py    DB-Zugriff - kein einziges if
    router.py      HTTP: übersetzt Anfrage ↔ Fachlichkeit, sonst nichts
  tests/
    unit/          läuft immer, ohne DB, Millisekunden
    integration/   Marker `integration`, braucht Postgres

services/web/src/module/quiz/
  api.ts                 typisierter Zugriff auf das Backend
  QuizSeite.tsx    die Oberfläche
  QuizSeite.module.css
```

### Die Trennung ist nicht verhandelbar

`dienst.py` enthält die Entscheidungen und ist rein. `speicher.py` macht I/O
und entscheidet nichts. `router.py` übersetzt.

Der Grund ist messbar: Unit-Tests laufen dadurch in Millisekunden, und nur
deshalb benutzt man die rot-grün-Schleife wirklich. Sobald eine
Fallunterscheidung in `speicher.py` oder `router.py` rutscht, braucht ihr Test
eine Datenbank — und ab da wird nicht mehr getestet, sondern geklickt.

---

## 3. Ablauf

### 3.1 Vertrag zuerst

Schreibe `schemas.py`. Was geht rein, was kommt raus, welche Werte sind
zulässig. Pydantic-Validierung wird automatisch zu `422` mit Feldnamen.

### 3.2 Fachlogik testgetrieben

1. Test in `tests/unit/test_dienst.py` schreiben und **scheitern sehen**
2. einfachste Änderung in `dienst.py`, die ihn grün macht
3. aufräumen, Tests bleiben unverändert

```bash
make dev N=quiz              # Gateway lädt nur dieses Artefakt
cd modules/quiz && uv run ptw . --now
```

Für die Oberfläche in einem zweiten Fenster:

```bash
make tdd-web N=quiz
```

### 3.3 Persistenz

Tabellen in `modelle.py` (erben von `Base`), Zugriff in `speicher.py`.
Integrationstests gegen die Datenbank `test`:

```bash
make dev                       # Umgebung läuft
cd modules/quiz
DATABASE_URL='postgresql+asyncpg://app:app@127.0.0.1:15432/test' uv run pytest -m ''
```

### 3.4 Endpunkte

`router.py`. Regeln:

- `summary=` bei jedem Endpunkt — die generische Ansicht im Frontend zeigt ihn
- feste Pfade **vor** parametrisierte, sonst liest FastAPI `/zusammenfassung`
  als UUID und antwortet `422`
- Fehler über eigene `ServiceError`-Klassen, nie `HTTPException`
- Rückgabetypen annotieren, sonst fehlt das OpenAPI-Schema

### 3.5 Oberfläche

`api.ts` erweitern, dann die Seite. Zugriff über Rollen und sichtbaren Text,
nie über CSS-Klassen. Nur Tokens aus `src/styles/tokens.css` — kein fester
Farbwert, keine feste Pixelzahl. Bausteine aus `src/ui`:
`Knopf`, `Karte`, `Feld`, `Etikett`, `Hinweis`, `Leerzustand`, `Platzhalter`.

Details: [`../../docs/08-design.md`](../../docs/08-design.md).

---

## 4. Abnahmekriterien

Fertig ist das Artefakt, wenn **alles** davon zutrifft:

```bash
# Backend
cd modules/quiz
uv run ruff format --check . && uv run ruff check . && uv run mypy
DATABASE_URL='postgresql+asyncpg://app:app@127.0.0.1:15432/test' uv run pytest -m ''

# Frontend
cd services/web
npx prettier --check src && npx eslint . && npm run typecheck && npm run test:coverage

# Zusammenspiel
make dev && make smoke
```

Kürzer, solange du nur an diesem Artefakt arbeitest:

```bash
make test-modul N=quiz
```

| Kriterium | Schwelle |
|---|---|
| Coverage Backend | ≥ 85 % |
| Coverage Frontend | ≥ 85 % Zeilen, ≥ 80 % Zweige |
| `mypy --strict` | keine Fehler |
| `GET /module` | `quiz` mit `status: "bereit"` (angemeldet) |
| `GET /quiz/` ohne Cookie | 200 mit `laufende_runden` (öffentlich); `GET /quiz/kataloge` ohne Cookie 401 |
| Rauchtests | grün |

Zusätzlich, was kein Werkzeug prüft:

- [ ] Jeder Ladezustand hat einen Platzhalter, keinen Layoutsprung
- [ ] Der Erstzustand erklärt, was als Nächstes zu tun ist
- [ ] Fehlermeldungen des Backends erreichen den Benutzer wörtlich, nicht als
      „Fehler 409"
- [ ] Ein fehlgeschlagenes Formular behält seine Eingabe
- [ ] Bei 375 px Breite ist alles erreichbar, ohne horizontal zu scrollen
- [ ] Der `zugang` ist bewusst `OEFFENTLICH` - bestätigt am 2026-11-28, der
      Gateway-Test `test_ohne_anmeldung_ist_nur_das_oeffentliche_zu_sehen`
      nennt `quiz` namentlich

---

## 5. Ausrollen

```bash
git commit && git push          # CI prüft
homepi deploy -s quiz    # Pipeline baut arm64, Pi zieht
```

Die Kachel erscheint danach von selbst — bei allen, die ein Recht dafür haben:

```bash
homepi benutzer recht <name> quiz nutzer
```

---

## 6. Häufige Fehler

| Symptom | Ursache |
|---|---|
| Kachel fehlt | Entry Point in `pyproject.toml` falsch, oder Modul nicht als Abhängigkeit im Gateway |
| `status: "fehler"` im Manifest | Import wirft. Grund steht in der Kachel und im Log |
| `422` statt Treffer | parametrisierte Route steht vor der festen |
| `RuntimeError: keine DATABASE_URL` | Unit-Test benutzt `DbSitzung`; das gehört in `tests/integration/` |
| Leere Tabelle nach Neustart | `DB_SCHEMA_ANLEGEN=false`. Lokal `true`, in Produktion braucht es eine Migration |
| Endpunkt fehlt in generischer Ansicht | `summary=` oder Rückgabetyp fehlt |
