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

### Wer „Administrator" ist

An genau einer Stelle definiert, und absichtlich nichts Besonderes:
**`verwalter` für das Artefakt `verwaltung`**. Geprüft mit derselben Funktion
wie jedes andere Recht.

Das Artefakt `verwaltung` ist die Oberfläche, in der Konten angelegt, gesperrt,
gelöscht und Rechte vergeben werden. Wer es darf, kann sich selbst jedes andere
Recht geben — das ist kein Loch, sondern die Definition von Administrator. Der
Unterschied zu einem globalen Administrator bleibt trotzdem: die Macht hängt an
einem Artefakt wie jede andere auch, sie steht in derselben Tabelle, und sie
lässt sich einzeln entziehen.

Zwei Regeln binden auch ihn:

| | |
|---|---|
| Niemand nimmt sich **selbst** die Verwaltung | Er könnte es nicht zurücknehmen und säße vor einer Oberfläche, die ihn nicht mehr hineinlässt |
| Der **letzte** Verwalter bleibt | Sonst kann diese Installation niemand mehr verwalten |

Über die Oberfläche greift immer die erste: der letzte Verwalter ist
zwangsläufig der Aufrufer selbst. Die Zählung ist die Sicherung für den Weg
über die Kommandozeile, wo niemand als jemand handelt.

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

## Ersteinrichtung: das erste Konto

Eine frische Installation hat keinen Verwalter. Wer die Adresse aufruft,
bekommt die **Einrichtungsmaske** statt der Anmeldung.

Damit nicht derjenige die Installation übernimmt, der als Erster an die frische
Adresse kommt, verlangt sie ein **Einrichtungstoken**. Das schreibt das Gateway
beim Start ins Log:

```
Diese Installation hat noch keinen Verwalter.
  Einrichtung öffnen:  <adresse>/einrichtung
  Einrichtungstoken:   D2oEXAHV31fDHs8aycq-…
  Das Token gilt bis zum nächsten Start und wird danach ersetzt.
```

```bash
docker compose -f compose.dev.yml logs gateway | grep -A3 "keinen Verwalter"
```

Lesen kann das Log nur, wer Zugriff auf die Maschine hat — damit gilt dieselbe
Bedingung wie für die Kommandozeile, nur bequemer.

### Was das Backend prüft

Bei **jedem** Aufruf, beide Bedingungen:

1. Es gibt noch keinen Verwalter.
2. Das vorgelegte Token stimmt.

| Fall | Antwort |
|---|---|
| noch kein Verwalter, Token stimmt | 200, Konto angelegt und angemeldet |
| noch kein Verwalter, Token falsch | 401 — die Einrichtung bleibt offen |
| Verwalter vorhanden | 409, auch mit gültigem Token |
| letzter Verwalter gesperrt | 409 — eine Sperre öffnet die Tür nicht wieder |

**Dass die Oberfläche die Maske nicht anzeigt, ist keine Sicherung.** Wer
`/einrichtung` von Hand eintippt oder direkt gegen die API spricht, landet
genauso hier — und hier wird geprüft. Ein eigener Testfall hält das fest.

Das Token liegt wie ein Sitzungstoken nur als SHA-256 in der Datenbank; der
Klartext steht einmal im Log und sonst nirgends. Bei jedem Start entsteht ein
neues, damit ein vorgestern mitgelesenes wertlos ist. Ist das Log schon
weggerollt:

```bash
homepi benutzer einrichtungstoken
```

Das verweigert sich, sobald es einen Verwalter gibt — sonst wäre es ein
Zweitschlüssel, der nie ungültig wird.

## Konten anlegen

**Es gibt keinen Registrierungs-Endpunkt.** Wer ein Konto braucht, bekommt es
von einem Verwalter — in der Oberfläche unter *Verwaltung* oder auf der
Kommandozeile.

```bash
export DATABASE_URL='postgresql+asyncpg://app:app@127.0.0.1:15432/app'

homepi benutzer anlegen aaron --artefakt staffelpilot --rolle verwalter
homepi benutzer recht aaron geraete leser
homepi benutzer entziehen aaron geraete
homepi benutzer passwort aaron
homepi benutzer liste

homepi benutzer sperren aaron       # stilllegen, Sitzungen fliegen sofort raus
homepi benutzer entsperren aaron
homepi benutzer loeschen aaron      # fragt nach; --ja fuer Skripte
```

Dasselbe in der Oberfläche: Artefakt **Verwaltung**. Dort lassen sich Konten
anlegen, sperren, löschen, Passwörter setzen und Rollen je Artefakt vergeben.
Sichtbar ist es nur für Verwalter — wie jedes andere Artefakt auch.

`sperren` statt `loeschen` ist der uebliche Fall: jemand ist ausgeschieden,
seine Daten sollen aber zuordenbar bleiben. Beides beendet laufende Sitzungen
sofort — ohne das waere die Sperre bis zu vierzehn Tage wirkungslos.

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
| `GET /auth/einrichtung` | ein Ja oder Nein, sonst nichts |
| `POST /auth/einrichtung` | 409, sobald es einen Verwalter gibt |
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
leistet erst der Reverse Proxy, der auf einem öffentlichen Host nur
`/api/<artefakt>` und `/auth/…` durchlässt. Das ist noch nicht gebaut; die
Netz-Topologie, in die es sich einfügt, steht in
[03-architecture.md](03-architecture.md).

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
