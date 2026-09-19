"""Das anpassbare Regelwerk.

Die Prüfungen der Spielordnung stehen nicht im Programm, sondern in
Python-Dateien, die dem Staffelleiter gehören: ein Ordner, der ein neues
Abbild überlebt und sich ohne Kenntnis des übrigen Codes ändern lässt.
Übernommen aus `D:/DevLibrary/StaffelPilot/src/rules/regelwerk/`.

Der Aufbau in fünf Teilen:

* `spiel.py`       — der Spielbericht in der Sprache der Spielordnung
* `uebersetzer.py` — die einzige Stelle, die DFBnets Feldnamen kennt
* `dekorator.py`   — `@regel(...)`: Schwere, Weg, Paragraf, alles an der Regel
* `lader.py`       — lädt die Dateien und führt einzelne Regeln aus
* `ordner.py`      — wo die Dateien liegen (`PRUEFDIENST_REGELN`)

Was hier nicht hingehört: das Auslesen des Spielberichts, die Fristenlogik der
Bestätigungen, das Auflösen von Spielgemeinschaften. Das ist Datenbeschaffung
und Verfahren, kein Regelwerk — und in einer Konfigurationsdatei wäre es weder
lesbar noch prüfbar.

**`StoreAuskunft` ist nicht mitgekommen.** Sie las die SQLite-Datenbank der
alten Anwendung. Hier gibt es sie nicht, und solange niemand die Karten einer
Saison zählen kann, antwortet `Auskunft` durchgehend `None` — *weiß ich
nicht*. Die Regeln, die davon abhängen, schweigen dann, statt eine 0 zu
behaupten.
"""

from . import schalter
from .auskunft import Auskunft
from .dekorator import Regel, Registry, Sammler, id_aus_name
from .lader import (
    Befund,
    Ladung,
    ausfuehren,
    laden,
    vorlagen_ausrollen,
)
from .ordner import regelordner
from .spiel import (
    Einsatz,
    Karte,
    Mannschaft,
    Person,
    Spiel,
    Staffel,
    datum_lesen,
)
from .uebersetzer import uebersetzen

__all__ = [
    "Auskunft",
    "Befund",
    "Einsatz",
    "Karte",
    "Ladung",
    "Mannschaft",
    "Person",
    "Regel",
    "Registry",
    "Sammler",
    "Spiel",
    "Staffel",
    "ausfuehren",
    "datum_lesen",
    "id_aus_name",
    "laden",
    "regelordner",
    "schalter",
    "uebersetzen",
    "vorlagen_ausrollen",
]
