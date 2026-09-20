"""Die Prueferfreigabe fuer einen Spielbericht -- **die einzige Handlung
dieses Dienstes, die DFBnet sieht.**

Woertlich uebernommen aus
`D:/DevLibrary/StaffelPilot/src/automation/freigabe.py`. Die Selektoren sind
dort am 30.08.2026 gegen einen echten Bericht geprueft, und nichts davon ist
aus dem DOM einer anderen Seite geraten.

Eine Aenderung: die Seite wird **uebergeben** und nicht selbst geoeffnet. Ein
direkt angesprungener Bericht bleibt bei DFBnet leer (siehe `dfbnet.bericht`);
das Fenster kommt deshalb ueber den Verweis in der Trefferliste.

Alles hier ist so geschrieben, dass ein Fehlschlag laut ist. Der eine Ausgang,
den es nie geben darf, ist eine Meldung "erledigt", waehrend in DFBnet noch
"Schiedsrichterfreigabe" steht: der Staffelleiter glaubte dann, die Freigabe
sei passiert, und sieht nie wieder hin. Deshalb wird der Status
**zurueckgelesen** -- ein Klick, der keine Ausnahme wirft, ist kein Beweis.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from typing import Any

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class Ergebnis:
    """Womit eine Handlung in DFBnet zurueckkam."""

    erfolg: bool
    meldung: str
    #: True, wenn DFBnet schon im gewuenschten Zustand war. Kein
    #: Fehlschlag: der Staffelleiter kann es von Hand getan haben.
    schon_erledigt: bool = False


#: Third tab of the report. Addressed by id because the labels are rendered in
#: upper case by CSS, not in the DOM, which makes text matching a coin flip.
SPIELVERLAUF_TAB = "#navTab2"

#: Button labels, matched case-insensitively against the trimmed text.
FREIGABE_LABEL = "prüferfreigabe"
ZURUECKNEHMEN_LABEL = "freigabe zurücknehmen"

#: What the report shows once the release went through.
ZIEL_STATUS = "prüferfreigabe"

#: DFBnet asks before releasing: a modal titled "Spiel freigeben" saying the
#: Spielverlauf can no longer be changed by the club or the referee, with OK
#: and ABBRECHEN. Confirming it is part of the release, not an optional extra —
#: without the click nothing happens at all.
#:
#: Addressed by the container Bootstrap marks as open (`.modal.in`) rather than
#: by its wording: the page keeps several hidden modals in the DOM, and the
#: sentence is one text node together with the paragraph above it, so matching
#: the question exactly finds nothing.
DIALOG_CONTAINER = ".modal.in"
DIALOG_TITEL = "Spiel freigeben"
DIALOG_OK = "OK"

LADEN_MS = 8000
KLICK_MS = 8000
DIALOG_MS = 6000

#: How often the report is reloaded to confirm the new status before the job
#: counts as failed.
VERSUCHE_NACHLESEN = 2


class FreigabeFehler(RuntimeError):
    """The release did not happen. The message says what was seen instead."""


def _aktion(seite, label: str):
    """Locator for one button of the report's action bar.

    Matched case-insensitively against the element's text: DFBnet renders these
    labels in capitals through CSS `text-transform`, so the DOM says
    "Prüferfreigabe" while the screen says "PRÜFERFREIGABE". Matching the
    screen text exactly is how the first live attempt timed out.

    One locator for both the check and the click, so the button that is
    inspected is the button that is pressed.
    """
    muster = re.compile(rf"^\s*{re.escape(label)}\s*$", re.IGNORECASE)
    return seite.locator("a.btn, button.btn, a[role='button']").filter(has_text=muster)


def _vorhanden(knopf) -> bool:
    try:
        return knopf.count() > 0 and knopf.first.is_visible()
    except Exception:
        return False


def _gesperrt(knopf) -> bool:
    try:
        klassen = knopf.first.get_attribute("class") or ""
    except Exception:
        return False
    return "disabled" in klassen


def _status_text(seite) -> str:
    """Whatever the report prints next to "Spielberichtsstatus"."""
    return (
        seite.evaluate(
            """
            () => {
              const knoten = Array.from(document.querySelectorAll('*'))
                .filter(n => n.children.length === 0);
              const i = knoten.findIndex(n => (n.textContent || '').trim() === 'Spielberichtsstatus');
              if (i < 0 || i + 1 >= knoten.length) return '';
              return (knoten[i + 1].textContent || '').trim();
            }
            """
        )
        or ""
    )


def _dialog(seite):
    """Locator for the open release dialog."""
    return seite.locator(DIALOG_CONTAINER).filter(
        has_text=re.compile(re.escape(DIALOG_TITEL), re.IGNORECASE)
    )


def _dialog_bestaetigen(seite) -> bool:
    """Click OK in the release dialog. Returns whether it was confirmed.

    The OK button is looked up *inside* the dialog. Several hidden modals with
    their own OK live in this page, and clicking one of those would look like
    success while nothing was released.
    """
    dialog = _dialog(seite)
    try:
        dialog.first.wait_for(state="visible", timeout=DIALOG_MS)
    except Exception:
        logger.warning("No %r dialog appeared after the release click", DIALOG_TITEL)
        return False

    ok = dialog.first.locator("button").filter(
        has_text=re.compile(rf"^\s*{DIALOG_OK}\s*$", re.IGNORECASE)
    )
    try:
        ok.first.click(timeout=DIALOG_MS)
    except Exception:
        logger.warning("The %r dialog is up but its OK button was not clickable", DIALOG_TITEL)
        return False
    logger.info("Confirmed the %r dialog", DIALOG_TITEL)
    return True


def pruferfreigabe(seite: Any, report_id: str) -> Ergebnis:
    """Die Prueferfreigabe fuer einen Bericht erteilen.

    Die Seite ist der **geoeffnete Bericht** -- das Fenster, das der Leser
    ueber den Verweis in der Trefferliste aufgemacht hat. Wer sie schliesst,
    entscheidet der Aufrufer.

    Wirft nicht bei einer normalen Weigerung -- ein Bericht, der sich nicht
    freigeben laesst, ist eine Antwort und kein Absturz --, aber sehr wohl,
    wenn die Seite nie benutzbar wurde: das ist einen zweiten Versuch wert.
    """
    seite.wait_for_timeout(LADEN_MS)

    vorher = _status_text(seite)
    if ZIEL_STATUS in vorher.lower():
        logger.info("Report %s is already at %r", report_id, vorher)
        return Ergebnis(True, f"War bereits {vorher}.", schon_erledigt=True)

    seite.locator(SPIELVERLAUF_TAB).click(timeout=KLICK_MS)
    seite.wait_for_timeout(LADEN_MS)
    # The action bar sits under the whole Spielverlauf; without this the
    # button exists in the DOM but has no box, and the click is a no-op.
    for _ in range(6):
        seite.mouse.wheel(0, 4000)
        seite.wait_for_timeout(400)

    knopf = _aktion(seite, FREIGABE_LABEL)
    if not _vorhanden(knopf):
        if (
            _vorhanden(_aktion(seite, ZURUECKNEHMEN_LABEL))
            and ZIEL_STATUS in _status_text(seite).lower()
        ):
            return Ergebnis(True, "War bereits freigegeben.", schon_erledigt=True)
        raise FreigabeFehler(
            f"Knopf „Prüferfreigabe“ nicht gefunden. Status laut DFBnet: {vorher or 'unbekannt'}."
        )
    if _gesperrt(knopf):
        return Ergebnis(
            False,
            f"„Prüferfreigabe“ ist gesperrt. Status laut DFBnet: {vorher or 'unbekannt'}.",
        )

    knopf.first.click(timeout=KLICK_MS)
    bestaetigt = _dialog_bestaetigen(seite)

    # Read the status back. A click that "worked" is not evidence.
    #
    # From a reloaded page, not from this one: the status lives on the Info
    # tab, which Angular leaves in the DOM untouched while the release
    # happens on the Spielverlauf tab. Reading it in place reported
    # "Schiedsrichterfreigabe" on a report DFBnet had just released — a
    # false failure, and the one kind of wrong answer that would have the
    # user chasing releases that already went through.
    nachher = ""
    for _ in range(VERSUCHE_NACHLESEN):
        seite.wait_for_timeout(2000)
        seite.reload(wait_until="domcontentloaded")
        seite.wait_for_timeout(LADEN_MS)
        nachher = _status_text(seite)
        if ZIEL_STATUS in nachher.lower():
            logger.info("Report %s released, status is now %r", report_id, nachher)
            return Ergebnis(True, f"Freigegeben, Status {nachher}.")

    raise FreigabeFehler(
        (
            "Der Bestätigungsdialog kam nicht oder ließ sich nicht bestätigen; "
            if not bestaetigt
            else ""
        )
        + "der Spielbericht steht weiterhin auf "
        + f"{nachher or vorher or 'unbekannt'}."
    )
