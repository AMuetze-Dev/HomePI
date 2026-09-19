"""Woher die Spiele kommen — und ein Leser, der dafür kein DFBnet braucht.

Der Prüfdienst kennt nur dieses Protokoll. Das ist kein Selbstzweck: DFBnet
lässt sich von hier aus nicht prüfen (keine Zugangsdaten, und ein Testlauf
gegen das echte System ist eine Handlung, die ein Verband sieht). Mit einem
zweiten Leser lässt sich der **ganze** Weg prüfen — anfordern, anmelden,
lesen, einspielen, abschließen —, und offen bleibt allein, ob die Selektoren
in `dfbnet.py` noch zur Seite passen.
"""

from __future__ import annotations

import datetime as dt
from typing import Protocol

from .dienst import Spielzeile


class Leser(Protocol):
    """Was der Prüfdienst von einer Quelle braucht."""

    def anmelden(self, benutzer: str, passwort: str) -> None: ...

    def spiele(self, staffel: str, von: dt.date, bis: dt.date) -> list[Spielzeile]: ...

    def mannschaften(self, staffel: str) -> list[dict[str, object]]: ...

    def schliessen(self) -> None: ...


class DemoLeser:
    """Ein Leser aus dem Gedächtnis, für Tests und den ersten Start.

    Er meldet sich nirgends an und liest nichts — er gibt zurück, was ihm
    mitgegeben wurde. Damit lässt sich der Dienst hochfahren und die ganze
    Kette ansehen, bevor je ein Passwort im Spiel war.
    """

    def __init__(
        self,
        spiele_je_staffel: dict[str, list[Spielzeile]] | None = None,
        mannschaften_je_staffel: dict[str, list[dict[str, object]]] | None = None,
    ) -> None:
        self._spiele = spiele_je_staffel or {}
        self._mannschaften = mannschaften_je_staffel or {}
        self.angemeldet_als = ""
        self.geschlossen = False

    def anmelden(self, benutzer: str, passwort: str) -> None:
        # Das Passwort wird bewusst nicht gemerkt: auch ein Demo-Leser soll
        # nicht das Muster vorleben, eines in einem Feld liegen zu lassen.
        self.angemeldet_als = benutzer

    def spiele(self, staffel: str, von: dt.date, bis: dt.date) -> list[Spielzeile]:
        return [
            z
            for z in self._spiele.get(staffel, [])
            if z.datum is not None and von <= z.datum <= bis
        ]

    def mannschaften(self, staffel: str) -> list[dict[str, object]]:
        return self._mannschaften.get(staffel, [])

    def schliessen(self) -> None:
        self.geschlossen = True
