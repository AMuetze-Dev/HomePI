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
import re
import time
from collections.abc import Callable
from typing import Any

from . import aufstellung, auswahl, dienst, meldung
from .bericht import MatchReport, MatchReportExtractor
from .dienst import Spielzeile, Staffelkennung, StaffelNichtGefunden

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


def _hat_paarung(html: str) -> bool:
    """Ob die Infoseite die beiden Mannschaften nennt."""
    meta = MatchReportExtractor(info_html=html).extract().meta
    return bool(meta.home_team and meta.away_team)


def _hat_verlauf(html: str) -> bool:
    """Ob der Spielverlauf da ist.

    Die Bestaetigungen zaehlen, und ersatzweise die Ereignisse: ein Spiel ohne
    jede Karte und ohne Tor gibt es, ein Spielbericht ohne Bestaetigungsblock
    in der Praxis nicht.
    """
    bericht = MatchReportExtractor(history_html=html).extract()
    return bool(bericht.confirmations or bericht.cards or bericht.goals)


def _html_mit(seite: Any, hat_inhalt: Callable[[str], bool], grenze_ms: int = 20_000) -> str:
    """Den Seiteninhalt holen, sobald er den gesuchten Inhalt traegt.

    Auf ein Element zu warten reicht bei dieser Anwendung nicht: das Geruest
    steht da, bevor die Daten kommen, und wer dann liest, bekommt eine leere
    Seite, die aussieht wie ein Bericht ohne Vorkommnisse.
    """
    schluss = time.time() + grenze_ms / 1000
    html = ""
    while time.time() < schluss:
        html = str(seite.content())
        try:
            if hat_inhalt(html):
                return html
        except Exception:
            logger.exception("Der Seiteninhalt liess sich nicht pruefen")
        seite.wait_for_timeout(500)
    return ""


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

    def spiele(self, staffel: Staffelkennung, von: dt.date, bis: dt.date) -> list[Spielzeile]:
        """Die Trefferliste einer Staffel im Zeitraum.

        Die Reihenfolge der Felder ist nicht beliebig, sie ist teuer bezahlt:

        1. **Saison** -- DFBnet steht auf der laufenden. Wer die vorige prueft,
           sieht sonst nichts.
        2. **Mannschaftsart vor Spielklasse** -- Herren und Ue35 teilen sich
           dieselben Spielklassennamen ("1.Kreisklasse"). Ohne diesen Schritt
           liest ein Ue35-Lauf die Herrenspiele.
        3. **Spielklasse und Staffel** -- je nach Verband steht die Staffel in
           dem einen oder dem anderen Feld. Beide versuchen, eines muss sitzen.

        Sitzt keines von beiden, wird **nicht** gesucht: eine Suche ohne Filter
        liefert alles, was das Konto sieht, und das landete dann als Spiele
        dieser Staffel im Artefakt.
        """
        seite = self._seite
        if seite is None:
            raise RuntimeError("Erst anmelden, dann lesen")

        seite.get_by_role("link", name="Spielberichte").first.click(timeout=ZEIT_MS)
        seite.wait_for_load_state("domcontentloaded")
        seite.get_by_role("button", name="Suchen").first.wait_for(state="visible")

        if staffel.saison:
            self._feld(seite, "Saison", [staffel.saison])

        # Zuerst genau, dann als Teilstueck: "Herren" darf nicht "Herren Ue35"
        # verschlucken.
        arten = auswahl.mannschaftsart_kandidaten(staffel.altersklasse)
        if arten and not self._feld(seite, "Mannschaftsart", arten, genau=True):
            self._feld(seite, "Mannschaftsart", arten)

        spielklasse_ok = self._feld(seite, "Spielklasse", staffel.kandidaten)
        staffel_ok = self._feld(seite, "Staffel", staffel.kandidaten)
        if not spielklasse_ok and not staffel_ok:
            raise StaffelNichtGefunden(
                f"Weder Spielklasse noch Staffel liessen sich auf {staffel.kandidaten!r} "
                "setzen. Die angebotenen Optionen stehen im Protokoll des Dienstes; "
                "der Wert muss der Spielklasse in DFBnet entsprechen -- die "
                "Altersklasse steckt in der Mannschaftsart."
            )

        felder = seite.locator("input[id*='datepicker']").all()
        if len(felder) >= 2:
            felder[0].fill(dienst.als_dfbnet_datum(von))
            felder[1].fill(dienst.als_dfbnet_datum(bis))
        seite.get_by_role("button", name="Suchen").first.click(timeout=ZEIT_MS)
        # Auf die Treffer warten und **nicht** auf "networkidle": die Seite
        # haelt eine Verbindung offen, und dann wartet der Lauf zwei Minuten
        # und faellt um -- an einer Stelle, an der die Liste laengst dasteht.
        _warten_auf(
            seite,
            [
                "a[href*='/match-report/report/']",
                "text=Es sind keine Eintraege vorhanden",
                "text=Keine Ergebnisse",
            ],
            grenze_ms=30_000,
        )

        return self._trefferliste()

    def _feld(
        self, seite: Any, beschriftung: str, kandidaten: list[str], genau: bool = False
    ) -> bool:
        """Ein Auswahlfeld von DFBnet auf einen der Kandidaten setzen.

        Uebernommen aus `navigator._select_dropdown`. Es ist kein `<select>`,
        sondern ein nachgebautes Feld aus `li[role='option']` -- deshalb
        klicken und nicht `select_option`.

        **Verglichen wird in `auswahl.py`**, nicht hier: dort laesst sich ohne
        Browser pruefen, dass "1. Stadtklasse" nicht gegen "11. Stadtklasse"
        gewinnt.
        """
        try:
            feld = seite.locator(
                f".dfb-Dropdown:has(.dfb-Dropdown-label:has-text('{beschriftung}'))"
            ).first
            if feld.count() == 0:
                logger.warning("Das Feld %r gibt es auf dieser Seite nicht", beschriftung)
                return False

            erweitert = auswahl.expand_candidates(kandidaten)

            steht_schon = feld.locator(".dfb-Dropdown-value").first
            if steht_schon.count() > 0:
                text = (steht_schon.text_content() or "").strip()
                if text and auswahl.best_option([text], erweitert, exact=genau):
                    logger.info("%s steht schon auf %r", beschriftung, text)
                    return True

            klappe = feld.locator(".dfb-Dropdown-combobox").first
            klappe.click()
            seite.wait_for_timeout(400)

            elemente = feld.locator("li[role='option']").all()
            texte = [(el.text_content() or "").strip() for el in elemente]
            treffer = auswahl.best_option(texte, erweitert, exact=genau)
            if treffer is not None:
                elemente[texte.index(treffer)].click()
                # Warten, bis das Feld zu ist und die abhaengigen Felder neu
                # geladen haben.
                seite.wait_for_timeout(800)
                logger.info("%s auf %r gesetzt", beschriftung, treffer)
                return True

            klappe.press("Escape")
            seite.wait_for_timeout(200)
            # Die Optionen zu nennen macht aus "warum wird die Staffel
            # uebersprungen" einen Blick statt einer Suche.
            logger.warning(
                "%s liess sich nicht setzen. Gesucht: %s. Angeboten: %s",
                beschriftung,
                erweitert,
                texte or "(keine Optionen)",
            )
            return False
        except Exception:
            logger.exception("%s liess sich nicht setzen", beschriftung)
            return False

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
        """Einen Spielbericht lesen -- Kopfdaten, Aufstellung, Spielverlauf.

        **Ueber den Verweis in der Trefferliste, nicht ueber die Adresse.**
        Direkt angesprungen laedt DFBnet eine Seite, die aussieht wie der
        Bericht, aber leer bleibt: keine Ereignisse, keine Bestaetigungen, und
        die Schnittstelle antwortet 401. Ueber den Verweis oeffnet sich ein
        eigenes Fenster mit einer Sitzung, die alles beantwortet. Genau so
        macht es die alte Anwendung.

        `None` heisst: nicht gelesen. Der Aufrufer macht daraus eine Warnung
        am Spiel; er darf es nicht als "geprueft und sauber" durchgehen
        lassen.
        """
        seite = self._seite
        if seite is None:
            raise RuntimeError("Erst anmelden, dann lesen")

        verweis = seite.locator(f"a[href*='{kennung}']").first
        if verweis.count() == 0:
            logger.warning("Bericht %s: der Verweis steht nicht in der Trefferliste", kennung)
            return None

        try:
            with seite.expect_popup(timeout=ZEIT_MS) as fenster:
                verweis.click()
            popup = fenster.value
        except Exception:
            logger.exception("Bericht %s: das Fenster ging nicht auf", kennung)
            return None

        try:
            popup.set_default_timeout(ZEIT_MS)
            popup.wait_for_load_state("domcontentloaded")
            if not _warten_auf(popup, ["mr-report-info"]):
                logger.warning("Bericht %s: die Infoseite kam nicht", kennung)
                return None

            # Das Geruest steht frueher da als die Daten. Gewartet wird
            # deshalb auf **die Paarung** und nicht auf ein Element: ohne sie
            # laesst sich kein Kader einer Seite zuordnen, und die Karten
            # finden ihre Spieler nicht mehr.
            info_html = _html_mit(popup, _hat_paarung)
            if not info_html:
                logger.warning("Bericht %s: die Infoseite blieb leer", kennung)
                return None

            # Die Schnittstelle fragt nach der Kennung aus der geoeffneten
            # Adresse -- die ist eine andere als die aus der Trefferliste.
            api_kennung = dienst.kennung_aus_href(popup.url) or kennung
            aufstellungen = self._aufstellungen(popup, api_kennung)

            verlauf_html = self._verlauf(popup, kennung)
            if not verlauf_html:
                # Ohne den Spielverlauf fehlen Karten, Tore **und** die
                # Bestaetigungen der Mannschaften. Den Bericht trotzdem
                # auszuwerten hiesse, jedem Spiel zwei fehlende
                # Bestaetigungen anzudichten.
                return None

            bericht = MatchReportExtractor(
                info_html=info_html,
                teams_html="",
                history_html=verlauf_html,
                teams_data=aufstellungen,
            ).extract()

            # Die Kader werden ueber die Namen zugeordnet. Passt das nicht,
            # liegt der Gastkader auf der Heimseite -- und jede Karte sucht
            # ihren Spieler in der falschen Mannschaft.
            if aufstellungen and bericht.home_squad.team_name != bericht.meta.home_team:
                logger.warning(
                    "Bericht %s: Kader %r passt nicht zur Heimmannschaft %r",
                    kennung,
                    bericht.home_squad.team_name,
                    bericht.meta.home_team,
                )
            return bericht
        except Exception:
            logger.exception("Bericht %s liess sich nicht lesen", kennung)
            return None
        finally:
            try:
                popup.close()
            except Exception:
                logger.exception("Das Berichtsfenster liess sich nicht schliessen")

    def _verlauf(self, popup: Any, kennung: str) -> str:
        """Der Reiter "Spielverlauf".

        Dort stehen nicht nur Tore und Karten, sondern auch die
        **elektronischen Bestaetigungen** und die **Vorkommnisse**; die
        Infoseite kennt sie nicht. Ohne diesen Reiter sieht jedes Spiel aus,
        als haette keine Mannschaft bestaetigt -- am ersten echten Lauf waren
        das 48 erfundene Befunde auf 24 Spielen.
        """
        try:
            popup.locator(".nav-tab").nth(2).click(timeout=ZEIT_MS)
        except Exception:
            logger.exception("Bericht %s: der Reiter Spielverlauf ging nicht auf", kennung)
            return ""

        # Auf die Bestaetigungen warten, nicht auf ein Element: sie sind der
        # Grund, warum dieser Reiter geoeffnet wird. Ein Bericht ohne sie
        # laesst jede Mannschaft unbestaetigt aussehen.
        verlauf = _html_mit(popup, _hat_verlauf)
        if not verlauf:
            logger.warning("Bericht %s: der Spielverlauf kam nicht", kennung)
            return ""
        return verlauf

    def _aufstellungen(self, seite: Any, kennung: str) -> list[dict[str, Any]]:
        """Die Kader ueber die Schnittstelle, mit der Sitzung der Seite.

        Nicht aus dem HTML: dort stehen nur die beiden Mannschaftsnamen. An
        diesen Daten haengen die Regeln, die etwas wert sind -- Spielerfoto,
        Spielrecht, Altersklasse.

        Geht etwas schief, kommt eine **leere** Liste. Die alte Anwendung
        faellt hier auf das Aufklappen im DOM zurueck; das ist nicht portiert,
        und eine leere Aufstellung ist fuer die Regeln *unbekannt* und kein
        Verstoss (`regeln.aufstellung_bekannt`).
        """
        try:
            # Erst den Reiter, dann die Schnittstelle: die alte Anwendung tat
            # es in dieser Reihenfolge, und ein 401 an dieser Stelle kostet den
            # ganzen Kader -- also die Regeln, die etwas wert sind.
            try:
                seite.locator(".nav-tab").nth(1).click(timeout=10_000)
                seite.wait_for_timeout(1500)
            except Exception:
                logger.info("Der Reiter Mannschaften liess sich nicht antippen")

            antwort = seite.context.request.get(
                aufstellung.ADRESSE_MANNSCHAFTEN.format(kennung=kennung), timeout=ZEIT_MS
            )
            if antwort.status != 200:
                logger.warning(
                    "Bericht %s: die Mannschaften kamen mit Status %s", kennung, antwort.status
                )
                return []
            mannschaften = aufstellung.json_lesen(antwort.body())
        except Exception:
            logger.exception("Bericht %s: die Mannschaften liessen sich nicht holen", kennung)
            return []

        gefunden: list[dict[str, Any]] = []
        for mannschaft in mannschaften:
            nummer = mannschaft.get("id")
            if not nummer:
                continue
            try:
                antwort = seite.context.request.get(
                    aufstellung.ADRESSE_AUFSTELLUNG.format(mannschaft=nummer), timeout=ZEIT_MS
                )
                if antwort.status != 200:
                    logger.warning(
                        "Aufstellung %s: Status %s -- diese Mannschaft bleibt leer",
                        nummer,
                        antwort.status,
                    )
                    continue
                eintrag = aufstellung.mannschaft_aus_api(
                    mannschaft, aufstellung.json_lesen(antwort.body())
                )
            except Exception:
                logger.exception("Aufstellung %s liess sich nicht holen", nummer)
                continue
            if eintrag is not None:
                gefunden.append(eintrag)
        return gefunden

    def mannschaften(self, staffel: Staffelkennung, verband: str = "") -> list[dict[str, object]]:
        """Die Meldung einer Staffel: Meisterschaft, Staffel, Reiter, Tabelle.

        Der Weg stammt aus `navigator.py` der alten Anwendung. Nicht
        uebernommen ist der Filter **Gebiet**: dort stand er auf einem Kreis
        aus der Konfiguration, und fuer jeden anderen suchte die
        Initialisierung am falschen Ort. Mit "Eigene Staffeln" ist die Liste
        ohnehin auf die eigenen beschraenkt.

        Die **Mannschaftsart** bleibt auf "Keine Auswahl": so trifft der
        Staffelname unabhaengig von der Altersklasse.

        Eine leere Liste ueberschreibt im Artefakt nichts -- und der Auftrag
        meldet dann, dass nichts kam, statt einen Erfolg.
        """
        seite = self._seite
        if seite is None:
            raise RuntimeError("Erst anmelden, dann lesen")

        try:
            self._zur_spielplanbearbeitung(seite)
            self._suchmaske_fuellen(seite, staffel.saison, verband)
            seite.locator("button:has-text('SUCHEN')").first.click(timeout=ZEIT_MS)
            _warten_auf(seite, ["table tbody tr"])

            if not self._staffel_oeffnen(seite, staffel):
                raise StaffelNichtGefunden(
                    f"{staffel.name!r} steht nicht in der Meisterschaftsliste "
                    f"(gesucht wurde nach {staffel.kandidaten!r})"
                )

            reiter = seite.get_by_role("tab", name=re.compile("Mannschaften", re.IGNORECASE)).first
            reiter.click(timeout=ZEIT_MS)
            _warten_auf(seite, ["table"])
            return meldung.mannschaften_lesen(self._mannschaftstabelle(seite))
        except StaffelNichtGefunden:
            raise
        except Exception:
            logger.exception("Die Meldung zu %r liess sich nicht holen", staffel.name)
            return []

    def _zur_spielplanbearbeitung(self, seite: Any) -> None:
        """Meisterschaft -> Spielplanbearbeitung.

        Diese Maske und nicht die Spielplanansicht: nur sie hat "Eigene
        Staffeln" und den Reiter "Mannschaften".
        """
        seite.get_by_role("link", name="Meisterschaft").first.click(timeout=ZEIT_MS)
        seite.wait_for_load_state("domcontentloaded")
        seite.get_by_role("link", name="Spielplanbearbeitung").first.click(timeout=ZEIT_MS)
        seite.wait_for_load_state("domcontentloaded")
        seite.locator("button:has-text('SUCHEN')").first.wait_for(state="visible")

    def _suchmaske_fuellen(self, seite: Any, saison: str, verband: str) -> None:
        try:
            seite.get_by_role("button", name="Eingaben leeren").first.click(timeout=3000)
            seite.wait_for_timeout(800)
        except Exception:
            logger.warning("Die Suchmaske liess sich nicht leeren")

        if saison:
            self._auswahl(seite, "Saison", saison)
        # Auf dieser Seite heisst das Feld "Verband", woanders "Landesverband".
        # Beides versuchen, sonst bleibt der Filter leer.
        if verband and not self._auswahl(seite, "Verband", verband):
            self._auswahl(seite, "Landesverband", verband)

        for sucher in ("Eigene Staffeln", "label:has-text('Eigene Staffeln')"):
            try:
                if sucher.startswith("label:"):
                    seite.locator(sucher).first.click(timeout=3000)
                else:
                    seite.get_by_label(sucher).first.click(timeout=3000)
                return
            except Exception:
                continue
        logger.warning("Der Haken 'Eigene Staffeln' liess sich nicht setzen")

    def _auswahl(self, seite: Any, feld: str, wert: str) -> bool:
        try:
            seite.get_by_label(feld).first.select_option(label=wert, timeout=3000)
            return True
        except Exception:
            logger.info("Das Feld %r liess sich nicht auf %r setzen", feld, wert)
            return False

    def _staffel_oeffnen(self, seite: Any, staffel: Staffelkennung) -> bool:
        """Die Zeile mit diesem Namen aufmachen.

        Verglichen wird ohne Gross- und Kleinschreibung und als Teilstueck:
        DFBnet schreibt den Staffelnamen in der Liste nicht immer genauso wie
        im Spielplan.
        """
        for zeile in seite.locator("table tbody tr").all():
            text = (zeile.text_content() or "").strip()
            if not any(k.lower() in text.lower() for k in staffel.kandidaten):
                continue
            knopf = zeile.locator("button[title='Staffel bearbeiten']").first
            if knopf.count() == 0:
                continue
            knopf.click(timeout=ZEIT_MS)
            seite.wait_for_load_state("domcontentloaded")
            return True
        return False

    def _mannschaftstabelle(self, seite: Any) -> str:
        """Die Tabelle mit der Spalte "Mannschaft", sonst die erste."""
        tabelle = (
            seite.locator("table")
            .filter(has=seite.locator("th").filter(has_text="Mannschaft"))
            .first
        )
        if tabelle.count() == 0:
            tabelle = seite.locator("table").first
        return str(tabelle.evaluate("el => el.outerHTML"))

    def schliessen(self) -> None:
        for teil, name in ((self._browser, "browser"), (self._playwright, "playwright")):
            if teil is None:
                continue
            try:
                teil.stop() if name == "playwright" else teil.close()
            except Exception:
                logger.exception("Konnte %s nicht schliessen", name)
        self._browser = self._playwright = self._seite = None
