# 11 — Anmeldung und Sichtbarkeit

## Die Frage

Ein Artefakt soll eine eigenständige Website sein. Ein Staffelleiter, der
StaffelPilot benutzt, hat mit den Geräten im Haus nichts zu tun — er soll nicht
einmal erfahren, dass es sie gibt. Wie geht das, wenn alle Artefakte in einem
Prozess hinter einer Adresse laufen?

## Rechte gelten je Artefakt

Das ist die Regel, aus der alles Weitere folgt:

```
benutzer  ──┬── recht(artefakt="staffelpilot", rolle="verwalter")
            └── recht(artefakt="geraete",      rolle="leser")
```

**Es gibt keinen globalen Administrator.** Wer StaffelPilot verwaltet, hat
damit keinerlei Zugriff auf die Geräte im Haus. Ein Konto ohne Eintrag für ein
Artefakt sieht dieses Artefakt nicht — nicht als gesperrte Kachel, sondern gar
nicht.

Drei Rollen, aufsteigend. Absichtlich nicht mehr: jede weitere Stufe macht die
Frage „darf der das?" schwerer zu beantworten, nicht leichter.

| Rolle | gedacht für |
|---|---|
| `leser` | ansehen |
| `nutzer` | die alltägliche Arbeit |
| `verwalter` | einrichten, löschen, Grundeinstellungen |

Eine höhere Rolle deckt die niedrigeren ab.

## Zugang: was das Artefakt selbst festlegt

Jedes Modul erklärt, wer es überhaupt sehen darf:

```python
from homepi_core import Modul, Zugang

modul = Modul(
    id="staffelpilot",
    titel="StaffelPilot",
    router=router,
    zugang=Zugang.GESCHUETZT,      # Voreinstellung
    mindestrolle=Rolle.LESER,      # nur bei GESCHUETZT
)
```

| `Zugang` | Router | im Manifest sichtbar für |
|---|---|---|
| `OEFFENTLICH` | frei erreichbar | jeden |
| `GESCHUETZT` *(Voreinstellung)* | Prüfung am ganzen Router | wer ein Recht hat |
| `SELBST` | keine pauschale Prüfung | wer ein Recht hat |

**Die Voreinstellung ist die strengste.** Wer beim Bauen eines Artefakts nicht
über Zugriff nachdenkt, bekommt ein verschlossenes Artefakt und kein offenes.

`SELBST` ist für den Fall, dass ein Teil öffentlich sein soll und ein anderer
nicht — etwa eine öffentliche Tabellenansicht neben einer geschützten
Verwaltung. Das Artefakt prüft dann Endpunkt für Endpunkt mit `erfordert(...)`.
Im Manifest erscheint es trotzdem nur bei Rechteinhabern; sonst wäre es über
die Kachelliste wieder für alle sichtbar.

### Warum die Prüfung am Router hängt und nicht am Endpunkt

Ein Artefakt bekommt im Lauf der Zeit Endpunkte dazu. Hängt die Prüfung an
jedem einzelnen, ist der vergessene der, der das Loch reißt. Bei
`Zugang.GESCHUETZT` hängt sie deshalb am gesamten Router — sie gilt damit auch
für Endpunkte, die es heute noch gar nicht gibt.

Zusätzliche, strengere Prüfungen bleiben möglich:

```python
@router.delete("/{id}", dependencies=[erfordert("staffelpilot", Rolle.VERWALTER)])
async def entfernen(...) -> None: ...
```

### Ein Dienst startet nicht, wenn die Prüfung wirkungslos wäre

Mountet ein Service ein nicht-öffentliches Modul, ohne `anmeldung=True` zu
setzen, wirft `create_service` beim Start. Lieber gar nicht starten als offen
stehen — ohne Anmeldung gäbe es niemanden, der die Rechte prüfen könnte, und
die Prüfung fiele stillschweigend aus.

## Konten anlegen

**Es gibt keinen Registrierungs-Endpunkt.** Das erste Konto muss von jemandem
kommen, der ohnehin Zugriff auf die Maschine hat; ein offenes Anmeldeformular
wäre auf einem selbst gehosteten Dienst die erste Tür, die jemand eintritt.

```bash
export DATABASE_URL='postgresql+asyncpg://app:app@127.0.0.1:15432/app'

homepi benutzer anlegen aaron --artefakt staffelpilot --rolle verwalter
homepi benutzer recht aaron geraete leser
homepi benutzer entziehen aaron geraete
homepi benutzer passwort aaron
homepi benutzer liste
```

Das Passwort wird abgefragt, **nie als Argument übergeben** — als Argument
stünde es in der Shell-Historie und in der Prozessliste. Für Skripte und die
CI gibt es `--passwort-stdin`:

```bash
printf '%s' "$PW" | homepi benutzer anlegen rauchtest --passwort-stdin
```

Auf dem Pi läuft dasselbe im Gateway-Container:

```bash
docker compose exec -w /app/services/gateway gateway \
  uv run homepi benutzer anlegen aaron --artefakt staffelpilot --rolle verwalter
```

## Wie es technisch funktioniert

| | |
|---|---|
| Passwörter | Argon2id, 64 MB, t=2, p=1 — rund 100 ms auf einem Pi 5 |
| Sitzungstoken | 256 Bit aus `secrets` |
| in der Datenbank | **nur** der SHA-256 des Tokens |
| Cookie | `httponly`, `SameSite=Lax`, `secure` in Produktion |
| Dauer | 14 Tage, Verlängerung erst im letzten Tag |

Ein Datenbankabzug enthält damit keine lebenden Sitzungen. Ein XSS-Fund im
Frontend liefert kein Token (`httponly`). Kein bcrypt: dessen 72-Byte-Grenze
schneidet lange Passphrasen still ab.

Warum SHA-256 für das Token und Argon2 für das Passwort: ein Passwort ist
ratbar und muss teuer sein. Ein Token aus 256 Zufallsbits ist es nicht — und es
wird bei **jeder** Anfrage geprüft. Argon2 an dieser Stelle hieße 100 ms pro
Seitenaufruf.

Die Passwortregel ist **Länge, nicht Zeichenklassen**: mindestens zwölf
Zeichen. Eine erzwungene Sonderzeichenregel erzeugt `Passwort1!` und macht
nichts besser.

Ein unbekannter Benutzername und ein falsches Passwort sind von außen nicht zu
unterscheiden — auch nicht an der Antwortzeit. Bei fehlendem Konto wird
trotzdem einmal gehasht.

Ein Passwortwechsel meldet **alle** Geräte ab. Wer sein Passwort ändert, tut
das oft genau deshalb.

## Was das Gateway nach außen preisgibt

| Endpunkt | ohne Anmeldung |
|---|---|
| `GET /health` | Zustand, keine Namen |
| `GET /info` | Version, Umgebung, **Anzahl** der Module — keine Namen |
| `GET /module` | nur die öffentlichen Artefakte, nie ein 401 |
| `GET /openapi.json` | in Produktion abgeschaltet |
| `GET /<artefakt>/…` | 401 ohne Anmeldung, 403 ohne Recht |

`/module` antwortet bewusst auch anonym mit 200. Ein Besucher der öffentlichen
Seite soll die Seite sehen, für die er gekommen ist, und keinen 401.

Das OpenAPI-Schema listet jeden Pfad jedes Artefakts, auch die, die der
Aufrufer nicht sehen darf. Auf einem Dienst mit Anmeldung ist das ein
Verzeichnis der internen Artefakte — in Produktion deshalb zu. In der
Entwicklung bleibt es offen, sonst fehlte die generische Ansicht.

### Was hier noch offen ist

Ein Aufruf von `/geraete/` beantwortet sich für einen Angemeldeten ohne Recht
mit **403**, nicht mit 404. Damit weiß er, dass es ein Artefakt `geraete` gibt.
Das ist die ehrliche HTTP-Semantik und macht Fehlersuche möglich; die
vollständige Trennung einer öffentlichen Website von den internen Artefakten
leistet erst der Reverse Proxy, der öffentlich nur `/api/<artefakt>` durchlässt
(Stufe 4, siehe [03-architecture](03-architecture.md)).

## Im Frontend

```tsx
import { useAnmeldung } from "../anmeldung/kontext";

const { zustand, benutzer, darf, abmelden } = useAnmeldung();

if (darf("staffelpilot", "verwalter")) {
  // Knopf anzeigen
}
```

`zustand` ist `"laedt" | "angemeldet" | "abgemeldet"`. Das `laedt` ist ein
eigener Zustand und kein `null`: sonst blitzt bei jedem Seitenaufruf kurz das
Anmeldeformular auf, obwohl der Benutzer angemeldet ist.

`darf(...)` blendet **Bedienelemente** aus. Es ist keine Sicherheitsmaßnahme —
geprüft wird im Backend, und zwar nochmal.

Jede Anfrage braucht `credentials: "include"`, sonst schickt der Browser das
Cookie nicht mit.

## Tests

Lokal und in der CI:

```bash
# Unit: reine Entscheidungen, Millisekunden
uv run pytest tests/unit/test_auth_dienst.py tests/unit/test_modules.py

# Verdrahtung: hängt die Prüfung wirklich am Router?
uv run pytest tests/unit/test_modul_zugriff.py

# Gegen echtes Postgres: der ganze Weg mit Cookie
uv run pytest -m integration
```

Die Rauchtests gegen eine laufende Instanz brauchen ein Konto — sonst ist das
Manifest berechtigterweise leer und sie prüfen nichts mehr:

```bash
HOMEPI_SMOKE_BENUTZER=rauchtest HOMEPI_SMOKE_PASSWORT=… pytest -m smoke
```

Ohne diese Variablen überspringen sich die betroffenen Tests ausdrücklich,
statt auf einer leeren Liste stillschweigend grün zu werden.

Der schärfste dieser Tests holt die Artefaktliste aus der angemeldeten Sitzung
und ruft jeden Pfad daraus mit einem **frischen Client ohne Cookie** auf. Wäre
ein als `geschuetzt` deklariertes Artefakt versehentlich offen, fiele es genau
dort auf — und sonst nirgends.
