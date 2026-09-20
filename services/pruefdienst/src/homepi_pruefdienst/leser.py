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
import hashlib
from typing import Protocol

from .bericht import MatchReport
from .dienst import Spielzeile, Staffelkennung


class Leser(Protocol):
    """Was der Prüfdienst von einer Quelle braucht."""

    def anmelden(self, benutzer: str, passwort: str) -> None: ...

    def spiele(self, staffel: Staffelkennung, von: dt.date, bis: dt.date) -> list[Spielzeile]: ...

    def bericht(self, kennung: str) -> MatchReport | None: ...

    def mannschaften(
        self, staffel: Staffelkennung, verband: str = ""
    ) -> list[dict[str, object]]: ...

    #: Die Spieltage der zuletzt geholten Meldung. 0 heisst *nicht bekannt*.
    spieltage: int

    #: Ob beim naechsten Anmelden zuzusehen sein soll. Der Schalter dafuer
    #: steht in den Einstellungen des Artefakts.
    sichtbar: bool

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
        berichte_je_spiel: dict[str, MatchReport] | None = None,
    ) -> None:
        self._spiele = spiele_je_staffel or {}
        self._mannschaften = mannschaften_je_staffel or {}
        self._berichte = berichte_je_spiel or {}
        self.angemeldet_als = ""
        self.geschlossen = False
        self.spieltage = 0
        self.sichtbar = False

    def anmelden(self, benutzer: str, passwort: str) -> None:
        # Das Passwort wird bewusst nicht gemerkt: auch ein Demo-Leser soll
        # nicht das Muster vorleben, eines in einem Feld liegen zu lassen.
        self.angemeldet_als = benutzer

    def spiele(self, staffel: Staffelkennung, von: dt.date, bis: dt.date) -> list[Spielzeile]:
        return [
            z
            for z in self._spiele.get(staffel.name, [])
            if z.datum is not None and von <= z.datum <= bis
        ]

    def bericht(self, kennung: str) -> MatchReport | None:
        """Den Bericht, den man ihm mitgegeben hat -- sonst keinen.

        `None` heisst durchgehend: **nicht gelesen**. Einen leeren Bericht
        zurueckzugeben hiesse, einen Spielbericht ohne Karten, ohne
        Bestaetigungen und ohne Vorkommnisse zu behaupten -- und die Regeln
        wuerden ihn pruefen und sauber nennen.
        """
        return self._berichte.get(kennung)

    def mannschaften(self, staffel: Staffelkennung, verband: str = "") -> list[dict[str, object]]:
        return self._mannschaften.get(staffel.name, [])

    def schliessen(self) -> None:
        self.geschlossen = True


# ── Beispieldaten ─────────────────────────────────────────────────────────

#: Vier Vereine, davon eine Spielgemeinschaft und ein Verein mit zweiter
#: Mannschaft -- damit die Oberflaeche zeigen kann, was sie kann: geratene
#: Zuordnung, "pruefen" an der SG, und eine echte Paarung.
_VEREINE = [
    ("SG Gittersee/Coschütz", True),
    ("SV Loschwitz", False),
    ("SV Loschwitz 2", False),
    ("Dresdner SC 1898", False),
]

#: Zwei Befunde, einer davon kritisch und mit Weg -- sonst gibt es in der
#: Oberflaeche nichts zu entscheiden und nichts zu entwerfen.
_BEFUNDE = [
    {
        "regel": "rote_karte",
        "schwere": "kritisch",
        "titel": "Feldverweis auf Dauer",
        "text": "Feldverweis in Minute 71 wegen Tätlichkeit.",
        "person": "Max Müller",
        "weg": "sportgericht",
    },
    {
        "regel": "ordnungsdienst_fehlt",
        "schwere": "warnung",
        "titel": "Ordnungsdienst nicht benannt",
        "text": "Im Spielbericht ist kein Ordnungsdienst eingetragen.",
        "person": "",
        "weg": "mahnung",
    },
]


def _kurz(staffel: str) -> str:
    """Eine kurze, **stabile** Kennung aus dem Staffelnamen.

    Nicht `hash()`: der ist je Prozess anders gesalzen, und derselbe
    Prueflauf haette nach jedem Neustart des Containers andere Kennungen --
    also lauter neue Spiele statt aufgefrischter.
    """
    return hashlib.sha256(staffel.encode()).hexdigest()[:4]


class BeispielLeser(DemoLeser):
    """Ein Leser, der zu jeder Staffel plausible Daten erfindet.

    **Er ist eine Attrappe und sagt das auch:** jedes Spiel traegt eine
    Kennung, die mit ``DEMO-`` anfaengt, und jeder Befund den Hinweis im Text.
    Wer das in der Oberflaeche sieht, weiss, dass niemand bei DFBnet war.

    Wozu er da ist: ohne ihn laesst sich der Weg von "Staffel anlegen" bis
    "freigeben" nirgends durchklicken, ohne einen Verband anzufassen.
    """

    #: So viele Spieltage zurueck. Drei reichen, um eine Liste zu fuellen, und
    #: liegen sicher im voreingestellten Pruefzeitraum von dreissig Tagen.
    SPIELTAGE = 3

    def spiele(self, staffel: Staffelkennung, von: dt.date, bis: dt.date) -> list[Spielzeile]:
        gefunden: list[Spielzeile] = []
        for nummer in range(self.SPIELTAGE):
            tag = bis - dt.timedelta(days=7 * nummer)
            if tag < von:
                break
            heim, gast = _VEREINE[nummer % 2][0], _VEREINE[(nummer % 2) + 2][0]
            gefunden.append(
                Spielzeile(
                    dfbnet_id=f"DEMO-{_kurz(staffel.name)}-{nummer + 1}",
                    datum=tag,
                    heim=heim,
                    gast=gast,
                    ergebnis=f"{nummer + 1} : {nummer}",
                    status="freigegeben",
                )
            )
        return gefunden

    def mannschaften(self, staffel: Staffelkennung, verband: str = "") -> list[dict[str, object]]:
        return [{"name": name, "ist_sg": ist_sg} for name, ist_sg in _VEREINE]

    @staticmethod
    def befunde_zu(zeile: Spielzeile) -> list[dict[str, object]]:
        """Nur am ersten Spiel, und deutlich als Attrappe gekennzeichnet.

        An jedem Spiel waere die Warteschlange voller Arbeit, die es nicht
        gibt -- und der Unterschied zwischen "geprueft und sauber" und
        "geprueft und auffaellig" waere nicht mehr zu sehen.
        """
        if not zeile.dfbnet_id.endswith("-1"):
            return []
        return [
            {**befund, "mannschaft": zeile.heim, "text": f"{befund['text']} (Beispieldaten)"}
            for befund in _BEFUNDE
        ]
