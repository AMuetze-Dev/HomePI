# 06 — Artefakte: ein Container, der mitwächst

## Die Frage

Wenn jedes neue Artefakt einen eigenen Backend- und einen eigenen
Frontend-Container bekommt, wie teuer wird das auf einem Pi?

## Was tatsächlich was kostet

Gemessen an typischen Ruhewerten im Betrieb, nicht an Peak:

| | RAM | Bemerkung |
|---|---|---|
| FastAPI-Container, 1 uvicorn-Worker | 150–250 MB | **der teure Teil** |
| jeder zusätzliche uvicorn-Worker | ~120 MB | bringt bei I/O-Last nichts |
| nginx:alpine mit statischen Dateien | 10–15 MB | vernachlässigbar |
| das JS-Bundle im Browser | 0 MB auf dem Pi | läuft beim Betrachter |

Daraus folgt etwas, das der ersten Intuition widerspricht: **das Frontend ist
nicht das Problem.** Zehn nginx-Container wären 150 MB. Zehn FastAPI-Container
wären 2 GB — und dazu zehnmal derselbe Python-Interpreter, zehnmal SQLAlchemy,
zehn Verbindungspools gegen dieselbe Postgres-Instanz, die insgesamt nur
100 Verbindungen vergibt.

Der eigentliche Kostentreiber ist also der **Prozess pro Artefakt**, nicht das
Frontend pro Artefakt.

## Die Antwort: Modul statt Service

Ein Artefakt ist ein **Modul** in einem gemeinsamen Gateway, kein eigener
Container. Es meldet sich über einen Entry Point an:

```toml
# pyproject.toml des Artefakts
[project.entry-points."homepi.module"]
geraete = "homepi_geraete:modul"
```

```python
# homepi_geraete/__init__.py
from fastapi import APIRouter
from homepi_core import Modul

router = APIRouter()

@router.get("/", summary="Alle Geräte")
async def liste() -> list[str]:
    return ["lampe", "heizung"]

modul = Modul(id="geraete", titel="Geräte", router=router, version="1.0.0")
```

Das Gateway findet es beim Start, hängt den Router unter `/geraete` ein und
nennt es in `GET /module`. Zehn Artefakte: **ein Prozess, rund 250 MB.**

### Was das kostet

Ehrlich aufgeschrieben, damit die Entscheidung überprüfbar bleibt:

| | Modul | eigener Service |
|---|---|---|
| Speicher bei 10 Artefakten | ~250 MB | ~2 GB |
| Absturz | reißt alles mit | betrifft nur sich |
| unverträgliche Abhängigkeiten | blockieren alle | egal |
| Deploy | Gateway neu starten | unabhängig |
| CPU-lastige Arbeit | blockiert andere | isoliert |

`homepi new <name>` legt deshalb standardmäßig ein Modul an. Ein Artefakt, das
rechenintensiv ist, eine exotische Abhängigkeit hat oder wirklich unabhängig
laufen muss, bekommt weiterhin einen eigenen Container — dieselbe `homepi-core`,
nur mit eigenem `create_service` statt einem Eintrag im Register.

Damit ein einzelnes kaputtes Artefakt nicht alles blockiert, überlebt
`entdecke_module` einen Ladefehler: das Modul wird übersprungen und erscheint
mit `status: "fehler"` im Manifest. Eine Kachel, die „Fehler" anzeigt, ist
leichter zu bemerken als ein Artefakt, das nach einem Deploy kommentarlos
verschwunden ist.

## Ein Prozess, aber getrennte Websites

Ein Artefakt soll sich anfühlen wie eine eigenständige Website. Ein
Staffelleiter, der StaffelPilot benutzt, hat mit den Geräten im Haus nichts zu
tun — er soll nicht einmal erfahren, dass es sie gibt.

Dass alles in einem Prozess läuft, steht dem nicht entgegen, solange zwei
Dinge gelten:

1. **`GET /module` ist je Aufrufer gefiltert.** Wer kein Recht für ein Artefakt
   hat, bekommt es nicht genannt — auch nicht als graue, gesperrte Kachel.
2. **Die Zugriffsprüfung hängt am ganzen Router**, nicht an einzelnen
   Endpunkten. Ein Artefakt bekommt im Lauf der Zeit Endpunkte dazu; hängt die
   Prüfung an jedem einzelnen, ist der vergessene der, der das Loch reißt.

Jedes Modul erklärt dafür seinen `Zugang` — `OEFFENTLICH`, `GESCHUETZT` oder
`SELBST`. Die Voreinstellung ist `GESCHUETZT`: wer beim Bauen nicht über
Zugriff nachdenkt, bekommt ein verschlossenes Artefakt und kein offenes.
Mountet ein Service ein nicht-öffentliches Modul ohne Anmeldung, startet er
gar nicht erst — lieber das als ein Artefakt, das offen steht, weil die
Prüfung stillschweigend ausfiel.

Ausführlich, samt Rollenmodell und CLI: [11-anmeldung.md](11-anmeldung.md).

Was diese Ebene **nicht** leistet: ein Angemeldeter ohne Recht bekommt auf
`/geraete/` ein 403 und weiß damit, dass es dieses Artefakt gibt. Die
vollständige Trennung einer öffentlichen Website von den internen Artefakten
leistet erst der Reverse Proxy.

## Das Frontend: eine Hülle, viele Kacheln

Die Startseite liest `GET /module` und baut daraus ihre Kacheln. **Ein neues
Artefakt erscheint dort, ohne dass am Frontend eine Zeile geändert wird** —
es genügt, dass das Gateway es geladen hat, und dass der Betrachter es sehen
darf.

Hinter der Kachel gibt es zwei Stufen:

1. **Ohne eigene Oberfläche** bekommt das Artefakt die generische Ansicht. Sie
   liest die Endpunkte aus dem OpenAPI-Schema, das FastAPI ohnehin erzeugt.
   Ein frisch deploytes Artefakt ist damit sofort benutzbar, und die Anzeige
   kann nicht veralten.
2. **Mit eigener Oberfläche** trägt sich ein React-Modul in
   `services/web/src/module/register.ts` ein und ersetzt die generische Ansicht.

Stufe 1 braucht keinen Frontend-Build. Stufe 2 schon.

### Warum nicht Module Federation

Module Federation würde auch Stufe 2 ohne Shell-Build erlauben: jedes Artefakt
baut ein eigenes Remote-Bundle, die Hülle lädt es zur Laufzeit. Das klingt nach
genau dem, was hier gewünscht ist — die Rechnung geht trotzdem nicht auf:

- React muss zwischen Hülle und allen Remotes exakt zusammenpassen. Ein Remote
  mit einer anderen Minor-Version bringt Hooks-Fehler, die zur Bauzeit niemand
  sieht.
- Ein nicht erreichbares Remote ist ein Laufzeitfehler in der Hülle, kein
  Build-Fehler.
- Typen laufen nicht über die Grenze; man pflegt sie doppelt oder generiert sie.
- Debuggen heißt, zwei Build-Konfigurationen gleichzeitig im Kopf zu haben.

Der Gegenwert wäre: kein Shell-Build, wenn eine Oberfläche dazukommt. Der
Shell-Build dauert in der CI unter zwei Minuten und passiert ohnehin beim
Deploy. Für einen Entwickler und einen Pi ist das kein Tausch, der sich lohnt.

Der Punkt, an dem sich das dreht: mehrere Leute, die unabhängig voneinander
ausrollen wollen. Dann ist Module Federation richtig — und zu dem Zeitpunkt ist
`register.ts` die einzige Datei, die sich ändern muss.

## Der Weg eines neuen Artefakts

```bash
homepi new geraete           # Modul, Tests, Compose-Fragment
cd services/geraete
uv run ptw . --now           # rot, grün, aufräumen
git commit && git push       # CI prüft
homepi deploy -s geraete     # Pipeline baut, Pi zieht
```

Danach steht die Kachel auf der Startseite. Ohne Frontend-Änderung.

## Tests: dieselben, überall

Was sich zwischen Entwicklungsrechner, CI und Pi unterscheidet, ist genau eine
Angabe — die Basis-URL. Sie steht in `homepi.toml`:

```toml
[ziele.standard]
basis_url = "http://127.0.0.1:8000"

[ziele.pi]
basis_url = "https://api.home.example.com"
timeout = 10
```

```bash
pytest -m smoke                       # gegen [ziele.standard]
HOMEPI_ZIEL=pi pytest -m smoke        # gegen den Pi
HOMEPI_BASIS_URL=… pytest -m smoke    # direkt
```

Jedes Projekt übernimmt die Rauchtests mit einer Zeile:

```python
from homepi_core.testing.smoke import *
```

Geprüft wird genau das, was ein Unit-Test grundsätzlich nicht sehen kann:

- `/health` antwortet und keine Abhängigkeit ist gestört
- `/info` nennt eine Version — sonst ist nach einem Deploy nicht erkennbar,
  was tatsächlich läuft
- jedes Modul aus dem Manifest ist auch wirklich eingehängt. Ein Modul, das im
  Manifest steht, dessen Router aber fehlt, wäre sonst erst beim Klick auf die
  Kachel aufgefallen
- kein Modul steht auf `status: "fehler"`
- jedes als `geschuetzt` deklarierte Artefakt weist einen Aufruf **ohne**
  Cookie ab. Die Liste kommt aus der angemeldeten Sitzung, der Aufruf von einem
  frischen Client — wäre eines versehentlich offen, fiele es genau hier auf
- die Anmeldung ist erreichbar; fehlt sie nach einem Deploy, käme niemand mehr
  an seine Artefakte
- die Anfrage-Kennung kommt zurück; ohne sie lässt sich ein Fehlerbericht des
  Benutzers nicht im Log wiederfinden

Die Tests, die das Manifest auswerten, brauchen ein Konto — ohne Anmeldung ist
es berechtigterweise leer:

```bash
HOMEPI_SMOKE_BENUTZER=rauchtest HOMEPI_SMOKE_PASSWORT=… pytest -m smoke
```

Ohne diese Variablen überspringen sie sich ausdrücklich, statt auf einer leeren
Liste stillschweigend grün zu werden.

Rauchtests sind wie Integrationstests standardmäßig abgewählt und laufen nur
mit `-m smoke`. Im Deploy-Workflow gehören sie hinter den Neustart: erst
ausrollen, dann fragen, ob es auch läuft.

## Grenzen dieser Entscheidung

Drei Dinge, bei denen sie neu zu bewerten ist:

1. **Ein Artefakt braucht dauerhaft CPU.** Ein Modul, das eine Sekunde lang
   rechnet, blockiert im selben Prozess alle anderen. Dann: eigener Container.
2. **Zwei Artefakte brauchen unverträgliche Versionen derselben Bibliothek.**
   Im gemeinsamen Prozess ist das nicht auflösbar.
3. **Das Gateway startet zu langsam.** Bei vielen Modulen summiert sich die
   Importzeit; ab spürbaren Startzeiten lohnt es sich, selten genutzte
   Artefakte herauszulösen.
