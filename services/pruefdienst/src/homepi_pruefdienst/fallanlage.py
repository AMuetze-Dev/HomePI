"""Einen Sportgerichtsfall in DFBnet anlegen -- **die zweite Handlung dieses
Dienstes, die DFBnet sieht, und die folgenreichere.**

Woertlich uebernommen aus
`D:/DevLibrary/StaffelPilot/src/automation/fallanlage.py`. Die Selektoren sind
dort am 31.08.2026 am lebenden Modul abgelesen -- bis vor das Speichern, nicht
darueber hinaus. Nichts davon ist aus dem DOM einer anderen Seite geraten.

Der Weg:

    Sportgerichtsbarkeit -> Fall -> Suche (Saison + Spielkennung) -> Bearbeiten
    -> Reiter "Erstellung" -> Speichern

Die Suche nimmt Saison und Spielkennung allein an -- DFBnet sagt das auf der
Seite selbst -, und genau das macht sie eindeutig. Jede andere Kombination
(Gebiet, Mannschaftsart, Spielklasse) zoege das Mannschaftsart-Problem des
Prueflaufs hier mit herein.

Die Adresse des Formulars traegt ein Sitzungsmerkmal
(`webflow1788177266345.do`); es ist deshalb nur durch Navigieren erreichbar,
nie ueber einen direkten Verweis.

**Das legt ein echtes Verfahren gegen eine benannte Person an.** Es laeuft nur,
wenn der Staffelleiter den Knopf dafuer drueckt -- nie nebenbei, weil jemand
einen Spielbericht abgehakt hat -, und es meldet das Aktenzeichen zurueck, das
DFBnet vergibt: aus dieser Nummer entsteht die Mail an den Sportrichter.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass

logger = logging.getLogger(__name__)

MENUE_SPORTGERICHTSBARKEIT = "Sportgerichtsbarkeit"
MENUE_FALL = "Fall"

# ── Suche ──────────────────────────────────────────────────────────────────
SUCHE_SAISON = "select[name='kontext.suche.saisonId']"
SUCHE_SPIELKENNUNG = "input[name='kontext.suche.spielkennung']"
SUCHE_GERICHT = "select[name='kontext.suche.gerichtId']"
SUCHE_ABSENDEN = "input[name='SEARCH']"
#: The result row carries icons rather than links; this one opens the case.
TREFFER_BEARBEITEN = "table [title='Bearbeiten']"

# ── Formular „Erstellung" ──────────────────────────────────────────────────
#: Read-only mirrors DFBnet fills in. Prefixed with an underscore by its own
#: convention; useful to confirm the right match was opened.
ANZEIGE_SPIELKENNUNG = "input[name='_kontext.fall.spielKennung']"
ANZEIGE_SPIELDATUM = "input[name='_kontext.fall.spielAnstoss']"

VORGANGSDATUM = "input[name='kontext.currentVorgang.datum']"
TATBESTAND = "textarea[name='kontext.currentVorgang.tatbestand']"
DATUM_ANZEIGE = "input[name='kontext.fall.datumAnzeige']"
ANZEIGE_VON = "input[name='kontext.fall.anzeigeVon']"
SITZUNGSDATUM = "input[name='kontext.fall.sitzung.datum']"
GERICHT = "select[name='kontext.fall.sitzung.gericht']"
BESETZUNG = "textarea[name='kontext.fall.sitzung.besetzungFreitext']"

SPEICHERN = "input[name='SAVE_ERSTELLUNG']"

#: The number DFBnet hands back, e.g. "00042-26/27-SPG_DD". Searched for in the
#: page after saving; the field that holds it is confirmed by the first real
#: creation, so the pattern is what identifies it rather than a selector.
AKTENZEICHEN_MUSTER = re.compile(r"\b\d{4,6}-\d{2}/\d{2}-[A-Z_]+\b")

LADEN_MS = 7000
KLICK_MS = 15000


class FallanlageFehler(RuntimeError):
    """The case was not created. The message says how far it got."""


@dataclass(frozen=True)
class Anlage:
    """What a Sportgerichtsfall needs at creation time."""

    spielkennung: str
    saison: str
    gericht: str
    tatbestand: str
    #: Left empty means "keep whatever DFBnet pre-filled". Its own defaults are
    #: usually right, and overwriting a date the Verband set is not this app's
    #: business.
    vorgangsdatum: str = ""
    datum_anzeige: str = ""
    anzeige_von: str = ""

    def fehlende_felder(self) -> list[str]:
        pflicht = {
            "Spielkennung": self.spielkennung,
            "Saison": self.saison,
            "Gericht": self.gericht,
            "Tatbestand": self.tatbestand,
        }
        return [name for name, wert in pflicht.items() if not wert.strip()]


@dataclass(frozen=True)
class Ergebnis:
    erfolg: bool
    meldung: str
    #: The Aktenzeichen DFBnet assigned, when it could be read back.
    aktenzeichen: str = ""


def _navigieren(seite) -> None:
    """Sportgerichtsbarkeit → Fall."""
    seite.get_by_role("link", name=MENUE_SPORTGERICHTSBARKEIT).first.click(timeout=KLICK_MS)
    seite.wait_for_timeout(LADEN_MS)
    seite.get_by_role("link", name=MENUE_FALL, exact=True).first.click(timeout=KLICK_MS)
    seite.wait_for_timeout(LADEN_MS)


def _suchen(seite, anlage: Anlage) -> None:
    """Find the match. Saison plus Spielkennung is enough, per DFBnet itself."""
    seite.select_option(SUCHE_SAISON, label=anlage.saison)
    seite.locator(SUCHE_SPIELKENNUNG).fill(anlage.spielkennung)
    try:
        seite.select_option(SUCHE_GERICHT, label=anlage.gericht)
    except Exception:
        # Not part of the minimum search. Its absence is worth a line, not a
        # failure — the court is chosen again on the form itself.
        logger.warning("Could not preselect the court %r in the search", anlage.gericht)
    seite.locator(SUCHE_ABSENDEN).first.click(timeout=KLICK_MS)
    seite.wait_for_load_state("domcontentloaded")
    seite.wait_for_timeout(LADEN_MS)


def _formular_oeffnen(seite, anlage: Anlage) -> None:
    """Open the case form for the one search hit, and check it is the right one."""
    treffer = seite.locator(TREFFER_BEARBEITEN)
    if not treffer.count():
        raise FallanlageFehler(
            f"Zur Spielkennung {anlage.spielkennung} in Saison {anlage.saison} "
            "hat DFBnet kein Spiel gefunden."
        )
    treffer.first.click(timeout=KLICK_MS)
    seite.wait_for_load_state("domcontentloaded")
    seite.wait_for_timeout(LADEN_MS)

    if not seite.locator(TATBESTAND).count():
        raise FallanlageFehler("Das Formular „Erstellung“ kam nicht vollständig hoch.")

    # DFBnet mirrors the Spielkennung into a read-only field. Checking it is
    # cheap and rules out the one mistake that would be invisible afterwards:
    # a case opened against the wrong match.
    try:
        gezeigt = seite.locator(ANZEIGE_SPIELKENNUNG).first.input_value().strip()
    except Exception:
        gezeigt = ""
    if gezeigt and anlage.spielkennung not in gezeigt:
        raise FallanlageFehler(
            f"Das Formular gehört zu Spiel {gezeigt}, erwartet war {anlage.spielkennung}."
        )


def _ausfuellen(seite, anlage: Anlage) -> None:
    seite.locator(TATBESTAND).fill(anlage.tatbestand)
    for auswahl, wert in (
        (VORGANGSDATUM, anlage.vorgangsdatum),
        (DATUM_ANZEIGE, anlage.datum_anzeige),
        (ANZEIGE_VON, anlage.anzeige_von),
    ):
        if wert.strip():
            seite.locator(auswahl).fill(wert.strip())
    try:
        seite.select_option(GERICHT, label=anlage.gericht)
    except Exception as exc:
        raise FallanlageFehler(
            f"Das Gericht {anlage.gericht!r} steht im Formular nicht zur Auswahl."
        ) from exc
    seite.wait_for_timeout(500)


def aktenzeichen_lesen(seite) -> str:
    """The Aktenzeichen DFBnet assigned, or "" if it is not on the page."""
    text = seite.evaluate("() => document.body.innerText || ''") or ""
    treffer = AKTENZEICHEN_MUSTER.search(text)
    return treffer.group(0) if treffer else ""


def fall_anlegen(context, anlage: Anlage) -> Ergebnis:
    """Create one Sportgerichtsfall and return its Aktenzeichen.

    This is the one function in StaffelPilot that opens proceedings. It is
    called from an explicit button, never as a side effect of ticking a match
    off, and it refuses an incomplete Anlage rather than creating a case with a
    gap in it.
    """
    fehlt = anlage.fehlende_felder()
    if fehlt:
        return Ergebnis(False, "Es fehlt noch: " + ", ".join(fehlt) + ".")

    seite = context.new_page()
    try:
        _navigieren(seite)
        _suchen(seite, anlage)
        _formular_oeffnen(seite, anlage)
        _ausfuellen(seite, anlage)

        logger.info("Creating Sportgerichtsfall for match %s", anlage.spielkennung)
        seite.locator(SPEICHERN).first.click(timeout=KLICK_MS)
        seite.wait_for_load_state("domcontentloaded")
        seite.wait_for_timeout(LADEN_MS)

        aktenzeichen = aktenzeichen_lesen(seite)
        if not aktenzeichen:
            # The case may well exist. Saying "created, number unknown" is the
            # honest answer; claiming failure would invite a second case for
            # the same offence, which is worse than a number typed by hand.
            return Ergebnis(
                True,
                "Fall gespeichert, das Aktenzeichen war auf der Seite aber nicht zu "
                "finden — bitte in DFBnet nachsehen und eintragen.",
            )
        logger.info("Sportgerichtsfall created: %s", aktenzeichen)
        return Ergebnis(True, f"Fall angelegt, Aktenzeichen {aktenzeichen}.", aktenzeichen)
    finally:
        try:
            seite.close()
        except Exception:
            logger.debug("Could not close the Sportgerichtsbarkeit tab", exc_info=True)
