"""Der Leser, der wirklich nach DFBnet geht.

Die Selektoren stammen aus der bestehenden Anwendung
(`D:/DevLibrary/StaffelPilot/src/automation/navigator.py` und
`match_list_loader.py`) — sie sind dort über eine Saison gewachsen und haben
sich bewährt. Neu ist nur, dass das Zerlegen einer Zeile hier nicht passiert:
das steht in `dienst.zeile_zerlegen` und ist damit prüfbar, ohne dass ein
Browser startet.

> **Nicht gegen das echte DFBnet geprüft.** Von diesem Rechner aus gibt es
> keine Zugangsdaten, und ein Probelauf gegen das Livesystem ist eine Handlung,
> die ein Verband sieht. Geprüft ist alles davor und danach — mit
> `leser.DemoLeser`. Der erste echte Lauf ist der Beweis, nicht dieser Text.
"""

from __future__ import annotations

import datetime as dt
import logging
import time
from collections.abc import Callable
from typing import Any

from . import dienst
from .bericht import MatchReport, MatchReportExtractor
from .dienst import Spielzeile

logger = logging.getLogger(__name__)

ANMELDESEITE = "https://www.dfbnet.org/spielplus/login.do"

#: DFBnet ist an manchen Abenden zaeh. Zwei Minuten sind laenger, als es
#: bequem ist, und kuerzer als ein haengender Lauf.
ZEIT_MS = 120_000


def _warten_auf(seite: Any, sucher: list[str], grenze_ms: int = 9000) -> bool:
    """Warten, bis eines von mehreren Dingen sichtbar ist.

    Uebernommen aus `_wait_for_any` der alten Anwendung. Mehrere Sucher, weil
    dieselbe Seite je nach Sprache und Fuellstand anders aussieht -- "keine
    Eintraege" ist auch eine Antwort.
    """
    schluss = time.time() + grenze_ms / 1000
    while time.time() < schluss:
        for eintrag in sucher:
            try:
                if eintrag.startswith("text="):
                    seite.get_by_text(eintrag[5:]).first.wait_for(state="visible", timeout=500)
                else:
                    seite.locator(eintrag).first.wait_for(state="visible", timeout=500)
                return True
            except Exception:
                continue
        time.sleep(0.25)
    return False


class DfbnetLeser:
    """Ein Browser, der sich anmeldet und die Trefferliste ausliest."""

    def __init__(self, sichtbar: bool = False) -> None:
        self._sichtbar = sichtbar
        self._playwright: Any = None
        self._browser: Any = None
        self._seite: Any = None

    # ── Anmelden ──────────────────────────────────────────────────────────

    def anmelden(self, benutzer: str, passwort: str) -> None:
        # Erst hier importiert: wer den Demo-Leser benutzt, braucht kein
        # Playwright -- und ein Import, der einen Browser mitbringt,
        # gehoert nicht in den Start eines Dienstes, der ihn nie oeffnet.
        from playwright.sync_api import sync_playwright

        self._playwright = sync_playwright().start()
        self._browser = self._playwright.chromium.launch(headless=not self._sichtbar)
        kontext = self._browser.new_context(viewport={"width": 1400, "height": 900})
        self._seite = kontext.new_page()
        self._seite.set_default_timeout(ZEIT_MS)

        self._seite.goto(ANMELDESEITE, wait_until="domcontentloaded")
        self._zustimmung_wegklicken()

        # Der zweite "Anmelden"-Verweis ist der richtige; der erste fuehrt in
        # die Hilfe. Das steht so auch in der alten Anwendung.
        self._seite.get_by_role("link", name="Anmelden").nth(1).click()
        self._seite.get_by_role("textbox", name="Benutzerkennung").fill(benutzer)
        self._seite.get_by_role("textbox", name="Passwort").fill(passwort)
        self._seite.get_by_role("button", name="Anmelden").click()

        # Nicht auf die URL warten, sondern auf etwas Sichtbares: DFBnet
        # schiebt nach der Anmeldung ueber mehrere Seiten weiter.
        self._seite.get_by_role("link", name="Spielberichte").first.wait_for(
            state="visible", timeout=ZEIT_MS
        )
        logger.info("Bei DFBnet angemeldet als %s", benutzer)

    def _zustimmung_wegklicken(self) -> None:
        """Die Einwilligung ablehnen, wo sie ablehnbar ist.

        Der Reihe nach, und der erste Treffer gewinnt. Kein Fehler, wenn
        nichts davon da ist -- die Banner kommen und gehen.
        """
        sucher: list[tuple[str, Callable[[], Any]]] = [
            ("Alles ablehnen", lambda: self._seite.get_by_test_id("uc-deny-all-button")),
            ("Ablehnen", lambda: self._seite.locator("button:has-text('Ablehnen')").first),
            ("Schließen", lambda: self._seite.locator("[aria-label='Schließen']").first),
        ]
        for beschreibung, finder in sucher:
            try:
                finder().click(timeout=3000)
                logger.info("Banner weggeklickt: %s", beschreibung)
                return
            except Exception:
                continue

    # ── Lesen ─────────────────────────────────────────────────────────────

    def spiele(self, staffel: str, von: dt.date, bis: dt.date) -> list[Spielzeile]:
        seite = self._seite
        if seite is None:
            raise RuntimeError("Erst anmelden, dann lesen")

        seite.get_by_role("link", name="Spielberichte").first.click()
        seite.wait_for_load_state("domcontentloaded")
        seite.get_by_role("button", name="Suchen").first.wait_for(state="visible")

        felder = seite.locator("input[id*='datepicker']").all()
        if len(felder) >= 2:
            felder[0].fill(dienst.als_dfbnet_datum(von))
            felder[1].fill(dienst.als_dfbnet_datum(bis))
        seite.get_by_role("button", name="Suchen").first.click()
        seite.wait_for_load_state("networkidle")

        return self._trefferliste()

    def _trefferliste(self) -> list[Spielzeile]:
        """Jede Zeile mit einem Link auf einen Bericht.

        In einem Rutsch aus der Seite geholt statt Locator fuer Locator: bei
        achtzig Spielen ist der Unterschied zwischen einer Sekunde und einer
        Minute.
        """
        seite = self._seite
        if seite.locator("a[href*='/match-report/report/']").count() == 0:
            logger.info("Keine Spielberichte im Zeitraum")
            return []

        roh = seite.evaluate(
            """
            () => Array.from(
                document.querySelectorAll("a[href*='/match-report/report/']")
            ).map((a) => {
                const reihe = a.closest("tr");
                return {
                    href: a.getAttribute("href") || "",
                    zellen: reihe
                        ? Array.from(reihe.querySelectorAll("td")).map(
                            (td) => (td.innerText || "").trim())
                        : [],
                };
            })
            """
        )

        return [
            dienst.zeile_zerlegen(eintrag["zellen"], dienst.kennung_aus_href(eintrag["href"]))
            for eintrag in roh
        ]

    def bericht(self, kennung: str) -> MatchReport | None:
        """Die Seite eines Spielberichts lesen -- Info und Spielverlauf.

        Die Aufstellung fehlt mit Absicht: sie steht nicht im HTML, sondern in
        der Aufstellungsschnittstelle (siehe `aufstellung.py`), und deren
        Abruf ist noch nicht portiert. Ein leerer Kader ist fuer die Regeln
        *unbekannt* und kein Verstoss -- `regeln.aufstellung_bekannt` haelt
        genau das fest.

        `None` heisst: nicht gelesen. Der Aufrufer macht daraus eine Warnung
        am Spiel; er darf es nicht als "geprueft und sauber" durchgehen
        lassen.
        """
        seite = self._seite
        if seite is None:
            raise RuntimeError("Erst anmelden, dann lesen")

        unterseite = seite.context.new_page()
        try:
            unterseite.set_default_timeout(ZEIT_MS)
            unterseite.goto(dienst.bericht_adresse(kennung), wait_until="domcontentloaded")
            if not _warten_auf(unterseite, ["mr-report-info"]):
                logger.warning("Bericht %s: die Infoseite kam nicht", kennung)
                return None
            info_html = unterseite.content()

            verlauf_html = ""
            try:
                unterseite.locator(".nav-tab").nth(2).click(timeout=ZEIT_MS)
                if _warten_auf(
                    unterseite,
                    [
                        ".event-list mr-match-event",
                        ".no-events",
                        "text=Es sind keine Eintraege vorhanden",
                        "text=Endergebnis",
                    ],
                ):
                    verlauf_html = unterseite.content()
                else:
                    # Ohne Spielverlauf fehlen Karten und Tore. Das ist eine
                    # Luecke und keine Fehlanzeige -- sie gehoert ins
                    # Protokoll, nicht in ein stilles leeres Feld.
                    logger.warning("Bericht %s: der Spielverlauf kam nicht", kennung)
            except Exception:
                logger.exception(
                    "Bericht %s: der Reiter Spielverlauf liess sich nicht oeffnen", kennung
                )

            return MatchReportExtractor(
                info_html=info_html, teams_html="", history_html=verlauf_html
            ).extract()
        except Exception:
            logger.exception("Bericht %s liess sich nicht lesen", kennung)
            return None
        finally:
            try:
                unterseite.close()
            except Exception:
                logger.exception("Die Berichtsseite liess sich nicht schliessen")

    def mannschaften(self, staffel: str) -> list[dict[str, object]]:
        """Die Meldung einer Staffel.

        Noch nicht portiert: sie steckt in der alten Anwendung in
        `staffel_initialisierung.py` und haengt an mehreren Auswahlfeldern, die
        sich nur gegen das echte DFBnet erproben lassen. Eine leere Liste ist
        hier die ehrliche Antwort -- sie ueberschreibt im Artefakt nichts.
        """
        logger.warning(
            "Das Holen der Meldung zu %r ist noch nicht portiert; es kommt nichts.",
            staffel,
        )
        return []

    def schliessen(self) -> None:
        for teil, name in ((self._browser, "browser"), (self._playwright, "playwright")):
            if teil is None:
                continue
            try:
                teil.stop() if name == "playwright" else teil.close()
            except Exception:
                logger.exception("Konnte %s nicht schliessen", name)
        self._browser = self._playwright = self._seite = None
