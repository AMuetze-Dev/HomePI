# Artefakt „haushaltsbuch" — Auftrag für den Agenten

Dieses Artefakt ist **gefüllt und läuft**. Was es kann und warum es so
entschieden ist, steht in [README.md](README.md); dieser Text beschreibt, wie
hier gearbeitet wird und was noch aussteht.

Lies zuerst [`../../docs/06-artefakte.md`](../../docs/06-artefakte.md) — dort
steht, warum ein Artefakt ein Modul im Gateway ist und kein eigener Container.

## Stand (02.11.2026)

Gebaut: Personen, Konten, Kategorien und Posten mit vollem CRUD; der
Monatsplan mit Aufteilung nach Gewichten, Rücklagen und Sparquote je Person;
das Flussbild als Sankey; vier Flächen in der Oberfläche. 64 Artefakt-Tests
(95 % Zeilen), 68 Tests der Oberfläche.

Offen, in der Reihenfolge, in der es sich lohnt:

| | |
|---|---|
| **Migrationen** | `homepi schema` legt nur an. Eine neue Spalte in einer bestehenden Tabelle hält das Gateway in Produktion auf `unhealthy` an — gilt für jedes Artefakt, hier aber ab der ersten Änderung am Modell |
| **Ist gegen Soll** | Das Artefakt kennt keine Kontostände. Ob die Rücklage tatsächlich so hoch ist wie gerechnet, muss man im Online-Banking nachsehen. Ein Feld „Stand am" je Rücklagenkonto wäre der kleinste nützliche Schritt — eine Buchhaltung ausdrücklich nicht |
| **Jahresansicht** | Welcher Monat welche Abbuchungen trägt, steht heute nur je Monat. Eine Zeile über zwölf Monate würde zeigen, wo sich Jahresbeträge häufen |
| **Beispielhaushalt** | `POST /kategorien/grundgeruest` legt die Kategorien an. Ein vollständiger Beispielhaushalt zum Durchklicken fehlt |

**Eine Zusage ist nicht verhandelbar:** ein Betrag, der aufgeteilt wird, muss
in Summe wieder genau der Betrag sein. `dienst.aufteilen` leistet das, und
`tests/unit/test_dienst.py` prüft es. Wer dort rundet, nimmt jemandem jeden
Monat Cent weg, die ein Jahr später niemand mehr zuordnen kann.

---

## 1. Was bereits funktioniert

Nicht neu bauen, nicht umbauen:

| | |
|---|---|
| Anmeldung | Entry Point `homepi.module` in `pyproject.toml` → Gateway findet das Modul beim Start |
| Routing | Router hängt unter `/haushaltsbuch`; Traefik leitet `api.<domain>/haushaltsbuch` dorthin. **`GET /haushaltsbuch/` muss antworten** - daran erkennt der Rauchtest, dass das Modul wirklich eingehängt ist |
| Kachel | Startseite liest `GET /module` und zeigt „Haushaltsbuch" — ohne Frontend-Änderung |
| Zugriff | `zugang=Zugang.GESCHUETZT` in `__init__.py`: nur mit Recht `haushaltsbuch`. Die Prüfung hängt am ganzen Router |
| Health | `/health` und `/info` kommen aus `homepi-core` |
| Fehlerformat | Jeder Fehler wird RFC 9457 `problem+json`. Eigene Fehler erben von `ServiceError` |
| Logging | JSON in Produktion, Text lokal, `X-Request-ID` in jeder Zeile |
| DB-Sitzung | `DbSitzung` aus `homepi_core.deps` — eine Transaktion je Anfrage. Committet **vor** der Antwort; nie selbst committen |
| Testen | fünf Ebenen, Testdatenbank, bekannte Fallen: `docs/12-testen.md` |
| Tabellen | erben von `homepi_core.Base`; das Gateway legt sie beim Start an |

**Du schreibst nie selbst:** FastAPI-App, CORS, Middleware, Health-Endpunkt,
Datenbank-Engine, Logging-Konfiguration, Dockerfile, Compose-Fragment.

---

## 2. Dateien und ihre Rolle

```
modules/haushaltsbuch/
  src/homepi_haushaltsbuch/
    __init__.py    Anmeldung: modul = Modul(id=..., titel=..., router=...)
    schemas.py     Pydantic: was rein- und rausgeht
    modelle.py     SQLAlchemy: Tabellen (löschen, wenn kein DB-Bedarf)
    dienst.py      REINE Fachlogik - keine DB, kein await, keine Fixtures
    speicher.py    DB-Zugriff - kein einziges if
    router.py      HTTP: übersetzt Anfrage ↔ Fachlichkeit, sonst nichts
  tests/
    unit/          läuft immer, ohne DB, Millisekunden
    integration/   Marker `integration`, braucht Postgres

services/web/src/module/haushaltsbuch/
  api.ts                 typisierter Zugriff auf das Backend
  HaushaltsbuchSeite.tsx    die Oberfläche
  HaushaltsbuchSeite.module.css
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
make dev N=haushaltsbuch              # Gateway lädt nur dieses Artefakt
cd modules/haushaltsbuch && uv run ptw . --now
```

Für die Oberfläche in einem zweiten Fenster:

```bash
make tdd-web N=haushaltsbuch
```

### 3.3 Persistenz

Tabellen in `modelle.py` (erben von `Base`), Zugriff in `speicher.py`.
Integrationstests gegen die Datenbank `test`:

```bash
make dev                       # Umgebung läuft
cd modules/haushaltsbuch
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
cd modules/haushaltsbuch
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
make test-modul N=haushaltsbuch
```

| Kriterium | Schwelle |
|---|---|
| Coverage Backend | ≥ 85 % |
| Coverage Frontend | ≥ 85 % Zeilen, ≥ 80 % Zweige |
| `mypy --strict` | keine Fehler |
| `GET /module` | `haushaltsbuch` mit `status: "bereit"` (angemeldet) |
| `GET /haushaltsbuch/` ohne Cookie | 401 — nicht 200 |
| Rauchtests | grün |

Zusätzlich, was kein Werkzeug prüft:

- [ ] Jeder Ladezustand hat einen Platzhalter, keinen Layoutsprung
- [ ] Der Erstzustand erklärt, was als Nächstes zu tun ist
- [ ] Fehlermeldungen des Backends erreichen den Benutzer wörtlich, nicht als
      „Fehler 409"
- [ ] Ein fehlgeschlagenes Formular behält seine Eingabe
- [ ] Bei 375 px Breite ist alles erreichbar, ohne horizontal zu scrollen
- [ ] Der `zugang` ist bewusst gesetzt. `GESCHUETZT` ist die Voreinstellung und
      meistens richtig; `OEFFENTLICH` macht das Artefakt für **jeden** sichtbar

---

## 5. Ausrollen

```bash
git commit && git push          # CI prüft
homepi deploy -s haushaltsbuch    # Pipeline baut arm64, Pi zieht
```

Die Kachel erscheint danach von selbst — bei allen, die ein Recht dafür haben:

```bash
homepi benutzer recht <name> haushaltsbuch nutzer
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
