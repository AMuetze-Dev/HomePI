"""Was eine Regel über das einzelne Spiel hinaus erfahren darf.

§ 58 rechnet über die Saison: die fünfte Verwarnung sperrt, nach jeder
verwirkten Sperre fängt der Zähler von vorn an, und Pokal zählt getrennt.
Nichts davon steht im Spielbericht — es steht in den Karten, die das Artefakt
aufhebt.

Übernommen aus `StoreAuskunft` der alten Anwendung, die dasselbe über eine
SQLite-Datei beantwortete.

Zwei Dinge entscheiden alles hier:

**`None` heißt „weiß ich nicht", nicht „null".** Ohne Passnummer, ohne
Verbindung zum Artefakt oder bei einem Fehler gibt es keine Zahl. Eine 0 wäre
eine Behauptung — „diese Person hat keine Verwarnungen" —, und eine Regel, die
daraufhin schweigt, sähe aus, als hätte sie geprüft.

**Nur lesen.** Die Schnittstelle hat kein schreibendes Verfahren. Eine Regel,
die schreiben könnte, machte die Reihenfolge der Regeln zu einem Teil des
Ergebnisses.
"""

from __future__ import annotations

import datetime as dt
import logging
from typing import Any

from .regelwerk.auskunft import Auskunft
from .regelwerk.spiel import wettbewerbskategorie

logger = logging.getLogger(__name__)

#: § 58 (2) a): die 5. Verwarnung in Meisterschaftsspielen sperrt.
#: § 58 (2) c): im Pokal ist es die 2.
#:
#: Dieselben Zahlen stehen in `30_karten.py`, und das ist keine Schlamperei:
#: dort entscheiden sie, **was gemeldet wird**, hier nur, **ab wann der Zähler
#: von vorn läuft**. Wer die Zahl in der Regeldatei ändert, ändert die Meldung;
#: wer sie hier ändern will, ändert die Zählweise und sollte das wissen.
GRENZE_JE_KATEGORIE = {"Meisterschaft": 5, "Pokal": 2, "Turnier": 2}

#: Was als Verwarnung zählt, und was eine Sperre für sich ist.
VERWARNUNG = "Gelbe Karte"
SPERRKARTEN = ("Gelb-Rote Karte", "Rote Karte")


class GatewayAuskunft(Auskunft):
    """Die Auskunft über die Karten im Artefakt.

    Ein Zwischenspeicher je Person und Lauf: eine Elf mit Bank sind
    siebzehn Spieler, achtzig Berichte wären sonst tausend Abfragen für
    dieselben Antworten.
    """

    def __init__(self, gateway: Any, saisonbeginn: dt.date | None = None) -> None:
        self._gateway = gateway
        self._saisonbeginn = saisonbeginn
        self._gemerkt: dict[str, list[dict[str, Any]] | None] = {}

    # ── Die Fragen der Regeln ─────────────────────────────────────────────

    def letzte_sperre(self, pass_nr: str, wettbewerb: str) -> dt.date | None:
        """Wann zuletzt eine Sperre verwirkt wurde.

        Verwirkt heißt: an diesem Tag fiel die Karte, die sie auslöste — eine
        Gelb-Rote oder Rote Karte, oder die fünfte Verwarnung (im Pokal die
        zweite). Ab dem Tag danach zählt der nächste Zähler.
        """
        karten = self._karten(pass_nr, wettbewerb)
        if karten is None:
            return None

        grenze = GRENZE_JE_KATEGORIE.get(wettbewerb, 5)
        zaehler = 0
        letzte: dt.date | None = None
        for tag, im_spiel in self._nach_spielen(karten):
            arten = {k["art"] for k in im_spiel}
            if arten & set(SPERRKARTEN):
                # § 58 (1) c): die gelbe Karte desselben Spiels gilt als
                # verbraucht -- sie zaehlt nicht mit und wird hier auch nicht
                # gezaehlt.
                letzte = tag
                zaehler = 0
                continue
            if VERWARNUNG in arten:
                zaehler += 1
                if zaehler >= grenze:
                    letzte = tag
                    zaehler = 0
        return letzte

    def verwarnungen(
        self, pass_nr: str, wettbewerb: str, seit: dt.date | None = None
    ) -> int | None:
        """Verwarnungen dieser Person in diesem Wettbewerb.

        `seit` ist der Tag einer verwirkten Sperre. Die Karten **dieses Tages**
        gehören noch zum Zähler, den sie geschlossen hat — gezählt wird ab dem
        Tag danach. Sonst stünde der neue Zähler sofort wieder bei eins.
        """
        karten = self._karten(pass_nr, wettbewerb)
        if karten is None:
            return None

        anzahl = 0
        for tag, im_spiel in self._nach_spielen(karten):
            if seit is not None and tag <= seit:
                continue
            arten = {k["art"] for k in im_spiel}
            if arten & set(SPERRKARTEN):
                continue
            if VERWARNUNG in arten:
                anzahl += 1
        return anzahl

    # ── Die Karten ────────────────────────────────────────────────────────

    def _karten(self, pass_nr: str, wettbewerb: str) -> list[dict[str, Any]] | None:
        """Die Karten dieser Person in dieser Wettbewerbskategorie.

        Das Artefakt kennt den Wettbewerb so, wie DFBnet ihn nennt
        ("Kreispokal Herren"); die Regel fragt nach der Kategorie ("Pokal").
        Übersetzt wird hier — mit derselben Funktion, die auch das Spiel
        einordnet.
        """
        if not pass_nr:
            return None

        alle = self._gemerkt.get(pass_nr, ...)
        if alle is ...:
            try:
                alle = self._gateway.karten(pass_nr, seit=self._saisonbeginn)
            except Exception:
                # Eine Auskunft darf den Lauf nie kippen -- und eine erfundene
                # Zahl waere schlimmer als keine.
                logger.exception("Karten zu %s nicht lesbar", pass_nr)
                alle = None
            self._gemerkt[pass_nr] = alle
        if alle is None:
            return None
        return [
            k for k in alle if wettbewerbskategorie(str(k.get("wettbewerb") or "")) == wettbewerb
        ]

    @staticmethod
    def _nach_spielen(
        karten: list[dict[str, Any]],
    ) -> list[tuple[dt.date, list[dict[str, Any]]]]:
        """Die Karten nach Spiel gebündelt, ältestes zuerst.

        Nach Spiel und nicht nach Karte, weil § 58 (1) c) auf das Spiel sieht:
        wer in einem Spiel Gelb und dann Gelb-Rot bekommt, hat **keine**
        zählende Verwarnung erhalten.
        """
        spiele: dict[str, list[dict[str, Any]]] = {}
        for karte in karten:
            spiele.setdefault(str(karte.get("spielbericht_id") or ""), []).append(karte)

        gebuendelt: list[tuple[dt.date, list[dict[str, Any]]]] = []
        for im_spiel in spiele.values():
            tag = _datum(im_spiel[0].get("datum"))
            if tag is None:
                # Ohne Datum laesst sich nicht sagen, ob die Karte vor oder
                # nach einer Sperre fiel. Sie zaehlt deshalb nicht mit --
                # falsch einzusortieren waere schlimmer als auszulassen.
                continue
            gebuendelt.append((tag, im_spiel))
        return sorted(gebuendelt, key=lambda paar: paar[0])


def _datum(wert: object) -> dt.date | None:
    if isinstance(wert, dt.date):
        return wert
    try:
        return dt.date.fromisoformat(str(wert)[:10])
    except (TypeError, ValueError):
        return None
