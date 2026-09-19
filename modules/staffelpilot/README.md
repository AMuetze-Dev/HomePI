# homepi-staffelpilot

Spielberichte pruefen und abhaken - der Kern der Arbeit eines Staffelleiters.

Geprüfte Spielberichte kommen ueber `POST /staffelpilot/import` herein, ihre
Befunde werden entschieden, und **erst wenn zu jedem Befund eine Entscheidung
vorliegt**, laesst sich ein Bericht abhaken. Das ist die eine Zusage dieses
Artefakts: nichts uebersehen.

Die zweite steht daneben und ist genauso wichtig: **hier wird nichts
verschickt.** Aus einem Befund entsteht ein Entwurf aus einer Vorlage - Wort
fuer Wort vorhersagbar, ohne erzeugte Sprache. Abgeschickt wird er von einem
Menschen, in seinem Mailprogramm.

## Endpunkte

### Die taegliche Arbeit

| Endpunkt | |
|---|---|
| `GET /` | Warteschlange, optional `?staffel_id=` und `?nur_faellig=true` |
| `GET /zusammenfassung` | die Zahlen fuer die Kachel |
| `GET /spiele/{id}` | ein Bericht mit seinen Befunden, sortiert |
| `POST/DELETE /spiele/{id}/haken` | abhaken und wieder loesen |
| `POST /befunde/{id}/entscheidung` | `kenntnis` oder `verworfen` (mit Grund) |
| `DELETE /befunde/{id}/entscheidung` | zurücknehmen — der Haken fällt mit |
| `GET /befunde` | alle Befunde flach, `?staffel_id=` und `?nur_offen=` |

### Was aus einem Befund wird

| Endpunkt | |
|---|---|
| `POST /befunde/{id}/vorgang` | Entwurf erzeugen - Mahnung oder Antrag |
| `GET /vorgaenge` | Liste, optional `?zustand=entwurf\|versandt\|erledigt` |
| `GET/PATCH/DELETE /vorgaenge/{id}` | oeffnen, Text aendern, verwerfen |
| `POST /vorgaenge/{id}/zustand` | weiterstellen |

### Stammdaten

| Endpunkt | |
|---|---|
| `GET/POST /staffeln`, `PATCH/DELETE /staffeln/{id}` | Staffeln verwalten |
| `GET/PUT /staffeln/{id}/mannschaften` | Mannschaften und ihr Aufbau |
| `GET/PUT /regeln`, `PATCH /regeln/{id}` | Regelkatalog und die Schalter |
| `GET/PUT /einstellungen` | Staffelleiter, Verband, Zeitraeume, Pause |
| `GET/PUT/DELETE /zugang` | DFBnet-Zugangsdaten (verschluesselt) |
| `POST /import` | geprueftte Berichte einspielen |

### Was der Prüfdienst treibt

| Endpunkt | |
|---|---|
| `GET/POST /auftraege` | Prueflauf oder Initialisierung anfordern |
| `GET /auftraege/offen` | der eine, der laeuft -- oder `null` |
| `GET /auftraege/{id}` | einer mit seinem Protokoll |
| `POST /auftraege/{id}/fortschritt` | vom Pruefdienst |
| `POST /auftraege/{id}/abschluss` | vom Pruefdienst, oder Abbruch |
| `GET/POST /uebertragungen` | was nach DFBnet hinaus soll |
| `POST /uebertragungen/pause` | der eine Schalter |
| `POST /uebertragungen/wiederholen` | Gescheitertes zurueck in die Schlange |
| `POST /uebertragungen/{id}/abschluss` | vom Pruefdienst |
| `POST /zugang/abholen` | Zugangsdaten fuer den Pruefdienst |

## Die Entscheidungen, die hier stecken

**Ein Prueflauf ist die vollstaendige Aussage ueber einen Bericht**, kein
Nachtrag: ein erneutes Einspielen ersetzt die Befunde. Getroffene
Entscheidungen bleiben trotzdem, wiedergefunden an Regel und Person - das ist
es, was den zweiten Prueflauf ertraeglich macht.

**Der Weg eines Befundes kommt von aussen.** Ob aus einem Feldverweis ein
Sportgerichtsfall wird, steht in der Spielordnung, und die kennt dieses
Artefakt nicht. Der Prueflauf sagt es beim Einspielen (`weg`); hier entsteht
daraus der passende Entwurf.

**Der Aufbau der Mannschaften ist geraten, und das steht dran.** Welche
Mannschaft eines Vereins ueber welcher spielt, liefert DFBnet nicht mit - es
wird aus dem Namenszusatz geschlossen. Ein falscher Schluss faellt nicht laut
auf: er aendert still, wessen Einsaetze als Stammspieler zaehlen. Deshalb
traegt jede Zeile "geraten" oder "bestaetigt", eine Spielgemeinschaft gilt als
"pruefen", und eine Handkorrektur ueberlebt jedes weitere Einspielen. Eine
angehaengte Zahl ueber 20 ist eine Jahreszahl und keine Mannschaftsnummer
("Dresdner SC 1898").

**`aktiv` an einer Regel gehoert dem Staffelleiter.** Der Katalog meldet, was
es gibt - nicht, was jemand davon sehen will. Was der Prueflauf nicht mehr
meldet, verschwindet: ein Schalter fuer eine Regel, die niemand mehr prueft,
verspricht etwas, das nicht passiert.

**`faellig` wird berechnet, nicht gespeichert.** Der Pruefzeitraum verschiebt
sich mit jedem Tag; ein geschriebener Wert waere am Morgen darauf falsch.

**Ein Auftrag ist ein Datensatz, kein Prozess.** Der Prueflauf faehrt
minutenlang einen Browser und laeuft im Pruefdienst; hier steht nur, wer ihn
angefordert hat, wie weit er ist und was herauskam. Das Gateway darf neu
starten, ohne dass jemand vor einer Anzeige sitzt, die nie wieder
weiterzaehlt. Es gibt genau **einen** offenen Auftrag, weil es genau eine
DFBnet-Sitzung gibt.

**Eine Entscheidung laesst sich zuruecknehmen -- solange nichts hinaus ist.**
Der Haken faellt dabei mit: abgehakt heisst, zu jedem Befund liegt eine
Entscheidung vor. Ist zu dem Befund schon ein Schreiben **versandt**, geht es
nicht; der Verein hat es, und ein Befund, der hier wieder "offen" heisst,
waere eine Akte, die dem widerspricht.

**Die Uebertragung ist auf einer frischen Installation pausiert.** Eine
Freigabe in DFBnet ist eine Handlung nach aussen; sie soll nicht passieren,
weil jemand die Software zum ersten Mal gestartet hat. Sie ist idempotent
ueber `(aktion, referenz)` -- abhaken, Haken entfernen und wieder abhaken
erzeugt keine zwei Freigaben.

**Das DFBnet-Passwort liegt verschluesselt.** Der Schluessel steht in der
Umgebung (`STAFFELPILOT_SCHLUESSEL`), nicht in der Datenbank -- sonst laege er
neben dem, was er schuetzt. Fehlt er, wird **nichts** abgelegt, und die
Oberflaeche sagt das, bevor jemand tippt. Der Preis: wer den Schluessel
verliert, traegt die Zugangsdaten neu ein. Das ist der richtige Preis.

## Was hier bewusst nicht liegt

Die **DFBnet-Automation**. Sie faehrt minutenlang einen echten Browser und
gehoert nach [docs/06-artefakte.md](../../docs/06-artefakte.md) in einen
eigenen Dienst - im gemeinsamen Gateway-Prozess wuerde sie jedes andere
Artefakt blockieren, und die synchrone Playwright-API laesst sich aus einer
laufenden Event-Loop ohnehin nicht aufrufen.

Die Nahtstellen stehen dafuer bereit. Der Dienst

1. holt sich die Zugangsdaten (`POST /zugang/abholen`),
2. nimmt den offenen Auftrag (`GET /auftraege/offen`),
3. meldet Fortschritt (`POST /auftraege/{id}/fortschritt`),
4. spielt ein (`POST /import`, `PUT /regeln`,
   `PUT /staffeln/{id}/mannschaften`),
5. schliesst ab (`POST /auftraege/{id}/abschluss`),
6. arbeitet die Uebertragungen ab -- **nur wenn sie nicht pausiert ist** --
   und meldet jede einzeln (`POST /uebertragungen/{id}/abschluss`).

Noch offen: die **Mahnung als PDF**. Der Vordruck des Verbandes wird im alten
StaffelPilot ausgefuellt (`src/core/mahnung.py`); hier gibt es den Text, aber
kein Formular.

Ebenfalls nicht uebernommen: der Auftragstyp `sportrichter_mail` der alten
Warteschlange. Schreiben werden vorbereitet und von einem Menschen
abgeschickt; ein Programm, das Post an einen Sportrichter verschickt, ist
etwas anderes als eines, das einen Entwurf hinlegt.

Die bestehende Anwendung, aus der die Fachlichkeit stammt, liegt unter
`D:/DevLibrary/StaffelPilot` und ist von diesem Artefakt unberuehrt.

Artefakt im HomePI-Gateway. Grundgeruest kommt aus `homepi-core`:
Einstellungen, Logging, `/health`, `/info`, Fehlerformat, Anfrage-Kennung,
Anmeldung. Das Artefakt ist `Zugang.GESCHUETZT` - in einem Spielbericht stehen
Namen und Entscheidungen ueber Personen.

**Fuer Agenten: [AGENTS.md](AGENTS.md)** - dort steht, was zu tun ist.

## Entwickeln

```bash
make dev                  # Umgebung hoch (Frontend 5173, API 18000)
make dev-testkonto        # Konto zum Durchklicken
uv sync
uv run ptw . --now        # Unit-Tests im Watch-Modus
```

Integrationstests brauchen die laufende Datenbank:

```bash
HOMEPI_TEST_DATABASE_URL='postgresql+asyncpg://app:app@127.0.0.1:15432/test' \
  uv run pytest -m 'not smoke' --cov
```

Wie genau geprueft wird, steht in
[docs/12-testen.md](../../docs/12-testen.md).

### Wenn das Schema sich geaendert hat

`homepi schema` legt Fehlendes an und aendert nichts Vorhandenes - es ist kein
Migrationssystem. Eine **neue Tabelle** kommt beim naechsten Start von allein;
eine **neue Spalte in einer bestehenden Tabelle** nicht, und dann bleibt das
Gateway auf `unhealthy` stehen mit

```
Schema unvollständig: staffelpilot_befunde ohne weg
```

Das ist richtig so: lieber gar nicht starten als halb. In der Entwicklung
entweder `make dev-reset` (wirft die Datenbank weg) oder die Spalte von Hand
nachziehen.

### Der Schlüssel für die Zugangsdaten

`compose.dev.yml` setzt `STAFFELPILOT_SCHLUESSEL` fest -- zum Entwickeln, und
nur dafuer. In Produktion gehoert er in ein Secret:

```bash
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

Ohne ihn laeuft alles andere weiter; nur der DFBnet-Zugang laesst sich nicht
hinterlegen, und das steht dann in der Oberflaeche.

## Ausrollen

```bash
homepi deploy -s staffelpilot
```

Danach erscheint die Kachel auf der Startseite - ohne Frontend-Aenderung.
