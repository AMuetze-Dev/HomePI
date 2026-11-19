"""Das Gedächtnis der Sperre: welcher Name wann falsch angemeldet wurde.

Im Speicher und nicht in der Datenbank, mit Absicht. Das Gateway läuft als
EIN Prozess (``WEB_CONCURRENCY=1``, Begründung in docs/06-artefakte.md),
also gibt es genau ein Gedächtnis. Ein Neustart vergisst die Fehlversuche -
das ist eine Viertelstunde Sperre, die verfällt, und kein Schaden. Eine
Tabelle dafür hiesse eine Migration und einen Schreibzugriff bei jedem
Vertipper.

Was hier gilt, entscheidet ``dienst.wartezeit``. Diese Klasse merkt sich
nur, und sie entscheidet nichts.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime

from .dienst import FEHLVERSUCH_FENSTER


def _schluessel(name: str) -> str:
    # Sonst probiert man "Aaron", "aaron" und " aaron " und hat dreimal so
    # viele Versuche - der Benutzername ist ohnehin klein geschrieben.
    return name.strip().lower()


class Anmeldedrossel:
    """Fehlversuche je Benutzername."""

    #: Ab so vielen Namen wird bei jedem Vermerk aufgeraeumt. Wer tausend
    #: erfundene Namen durchprobiert, soll damit nicht den Speicher fuellen.
    AUFRAEUMEN_AB = 1000

    def __init__(self) -> None:
        self._fehler: dict[str, list[datetime]] = defaultdict(list)

    @property
    def anzahl_namen(self) -> int:
        return len(self._fehler)

    def fehlversuche(self, name: str) -> list[datetime]:
        return list(self._fehler.get(_schluessel(name), []))

    def vermerke(self, name: str, wann: datetime) -> None:
        self._fehler[_schluessel(name)].append(wann)
        if len(self._fehler) > self.AUFRAEUMEN_AB:
            self.raeume_auf(wann)

    def vergiss(self, name: str) -> None:
        self._fehler.pop(_schluessel(name), None)

    def raeume_auf(self, jetzt: datetime) -> None:
        """Wirft weg, was aus dem Fenster gefallen ist - und leere Namen."""
        for name in list(self._fehler):
            frisch = [z for z in self._fehler[name] if jetzt - z < FEHLVERSUCH_FENSTER]
            if frisch:
                self._fehler[name] = frisch
            else:
                del self._fehler[name]
