"""Die Fallanlage gegen eine nachgebaute Seite — mit einem echten Browser.

**Warum zusätzlich zu `test_fallanlage.py`.** Dort steht derselbe Ablauf gegen
eine nachgebaute Playwright-Schnittstelle: schnell, ohne Browser, und blind für
die eine Frage, auf die es hier ankommt — ob diese Selektoren in einem echten
DOM überhaupt etwas treffen. Ein Tippfehler in
`input[name='kontext.suche.spielkennung']` fällt einem Attrappen-Locator nicht
auf; er fällt beim ersten echten Fall auf, und der ist nicht zurückzunehmen.

**Nichts hier kommt an das echte DFBnet.** Die Seiten unter
`tests/seiten/sportgericht/` tragen die Formen des lebenden Moduls (abgelesen
am 31.08.2026) und werden von einem lokalen Webserver ausgeliefert. Es gibt
keinen Pfad von hier nach draußen, und das ist Absicht: eine Testsammlung, die
ein Verfahren gegen eine benannte Person eröffnen könnte, ist eine, die
niemand zu starten wagt.

Diese Tests brauchen Chromium (`uv run playwright install chromium`) und
laufen deshalb unter einer eigenen Marke:

    uv run pytest -m browser
"""

from __future__ import annotations

import http.server
import threading
from collections.abc import Iterator
from functools import partial
from pathlib import Path

import pytest

from homepi_pruefdienst.fallanlage import Anlage, FallanlageFehler, fall_anlegen

pytestmark = pytest.mark.browser

SEITEN = Path(__file__).resolve().parents[1] / "seiten" / "sportgericht"

#: Dieselben Angaben wie in `test_fallanlage.py`. Derselbe Fall, zweimal
#: geprüft: einmal ohne Browser auf die Logik, einmal mit Browser auf die
#: Formen.
ANLAGE = {
    "spielkennung": "633203004",
    "saison": "26/27",
    "gericht": "Sportgericht Stadtverband Fußball Dresden e.V.",
    "tatbestand": "Feldverweis auf Dauer wegen Beleidigung des Schiedsrichters.",
}


def anlage(**felder: str) -> Anlage:
    return Anlage(**{**ANLAGE, **felder})


class StillerServer(http.server.SimpleHTTPRequestHandler):
    """Ohne Zeile je Abruf. Ein Testlauf, der dreissig Zeilen Webserver
    protokolliert, verdeckt die eine Zeile, auf die es ankommt."""

    def log_message(self, *_: object) -> None:
        return


@pytest.fixture(scope="module")
def adresse() -> Iterator[str]:
    """Die nachgebauten Seiten über HTTP, nicht über `file://`.

    Der Unterschied ist kein Feinschliff: über `file://` gilt jede Seite als
    eigener Ursprung, Formulare verlieren dabei ihre Parameter, und genau die
    tragen hier die Spielkennung von der Suche ins Formular.
    """
    dienst = http.server.ThreadingHTTPServer(
        ("127.0.0.1", 0), partial(StillerServer, directory=str(SEITEN))
    )
    faden = threading.Thread(target=dienst.serve_forever, daemon=True)
    faden.start()
    try:
        yield f"http://127.0.0.1:{dienst.server_address[1]}/start.html"
    finally:
        dienst.shutdown()
        dienst.server_close()


@pytest.fixture(autouse=True)
def ohne_wartezeiten(monkeypatch: pytest.MonkeyPatch) -> None:
    """Die sieben Sekunden je Schritt gelten DFBnet, nicht diesem Server.

    Dort warten sie auf eine Maske, die ueber das Internet kommt; hier
    antwortet der Server in Mikrosekunden. Ungekuerzt dauerte diese Datei
    siebeneinhalb Minuten -- und ein Test, der so lange braucht, wird nicht
    mehr ausgefuehrt.
    """
    from homepi_pruefdienst import fallanlage

    monkeypatch.setattr(fallanlage, "LADEN_MS", 50)


@pytest.fixture
def browser() -> Iterator[object]:
    playwright = pytest.importorskip("playwright.sync_api")
    with playwright.sync_playwright() as p:
        chromium = p.chromium.launch()
        try:
            yield chromium
        finally:
            chromium.close()


@pytest.fixture
def kontext(browser: object) -> Iterator[object]:
    neuer = browser.new_context(locale="de-DE")  # type: ignore[attr-defined]
    try:
        yield neuer
    finally:
        neuer.close()


def _seiten(kontext: object) -> int:
    return len(kontext.pages)  # type: ignore[attr-defined]


class TestDerWegDurchDieSeiten:
    def test_der_fall_wird_angelegt_und_die_nummer_gelesen(
        self, kontext: object, adresse: str
    ) -> None:
        ergebnis = fall_anlegen(kontext, anlage(), start=adresse)

        assert ergebnis.erfolg is True, ergebnis.meldung
        assert ergebnis.aktenzeichen == "00042-26/27-SPG_DD"

    def test_der_tatbestand_steht_wirklich_im_feld(self, kontext: object, adresse: str) -> None:
        """Nicht nur "gefüllt" laut Attrappe, sondern im abgeschickten
        Formular."""
        ergebnis = fall_anlegen(kontext, anlage(), start=adresse)

        assert ergebnis.erfolg is True, ergebnis.meldung

    def test_das_fenster_wird_geschlossen(self, kontext: object, adresse: str) -> None:
        vorher = _seiten(kontext)

        fall_anlegen(kontext, anlage(), start=adresse)

        assert _seiten(kontext) == vorher


class TestWasAbgewiesenWird:
    def test_ohne_treffer_wird_nichts_angelegt(self, kontext: object, adresse: str) -> None:
        with pytest.raises(FallanlageFehler, match="kein Spiel gefunden"):
            fall_anlegen(kontext, anlage(), start=f"{adresse}?fall=leer")

    def test_ein_halbes_formular_wird_nicht_ausgefuellt(
        self, kontext: object, adresse: str
    ) -> None:
        with pytest.raises(FallanlageFehler, match="nicht vollständig"):
            fall_anlegen(kontext, anlage(), start=f"{adresse}?fall=halb")

    def test_die_falsche_akte_wird_erkannt(self, kontext: object, adresse: str) -> None:
        """Der eine Fehler, der hinterher unsichtbar wäre: ein Verfahren am
        falschen Spiel."""
        with pytest.raises(FallanlageFehler, match="gehört zu Spiel 999999999"):
            fall_anlegen(kontext, anlage(), start=f"{adresse}?fall=fremd")

    def test_ein_gericht_ohne_eintrag_haelt_an(self, kontext: object, adresse: str) -> None:
        with pytest.raises(FallanlageFehler, match="nicht zur Auswahl"):
            fall_anlegen(kontext, anlage(), start=f"{adresse}?fall=ohne_gericht")

    def test_das_fenster_wird_auch_beim_scheitern_geschlossen(
        self, kontext: object, adresse: str
    ) -> None:
        vorher = _seiten(kontext)

        with pytest.raises(FallanlageFehler):
            fall_anlegen(kontext, anlage(), start=f"{adresse}?fall=leer")

        assert _seiten(kontext) == vorher

    def test_eine_unvollstaendige_anlage_startet_keinen_browser(
        self, kontext: object, adresse: str
    ) -> None:
        ergebnis = fall_anlegen(kontext, anlage(tatbestand="  "), start=adresse)

        assert ergebnis.erfolg is False
        assert "Tatbestand" in ergebnis.meldung
        assert _seiten(kontext) == 0


class TestOhneNummer:
    def test_gespeichert_zaehlt_auch_ohne_aktenzeichen(self, kontext: object, adresse: str) -> None:
        """Der Fall ist womöglich da. "Angelegt, Nummer unbekannt" ist die
        ehrliche Auskunft -- „gescheitert" lüde zu einem zweiten Verfahren
        wegen desselben Vergehens ein, und das ist schlimmer als eine von Hand
        abgetippte Nummer."""
        ergebnis = fall_anlegen(kontext, anlage(), start=f"{adresse}?fall=ohne_nummer")

        assert ergebnis.erfolg is True
        assert ergebnis.aktenzeichen == ""
        assert "nachsehen" in ergebnis.meldung


class TestTrockenlauf:
    """Alles bis vor das Speichern -- und dann nicht.

    Damit lässt sich am **echten** DFBnet prüfen, ob die Selektoren noch
    passen, ohne ein Verfahren zu eröffnen. Das ist der einzige ehrliche Weg:
    ein Aktenzeichen ist dauerhaft, und Testakten löscht niemand.
    """

    def test_er_speichert_nicht(self, kontext: object, adresse: str) -> None:
        ergebnis = fall_anlegen(kontext, anlage(), start=adresse, trockenlauf=True)

        assert ergebnis.erfolg is True, ergebnis.meldung
        assert ergebnis.aktenzeichen == ""
        assert "Trockenlauf" in ergebnis.meldung

    def test_er_prueft_trotzdem_jeden_schritt(self, kontext: object, adresse: str) -> None:
        """Ein Trockenlauf, der am ersten Hindernis grün wäre, sagte nichts.
        Er geht denselben Weg und meldet dasselbe Scheitern."""
        with pytest.raises(FallanlageFehler, match="gehört zu Spiel 999999999"):
            fall_anlegen(kontext, anlage(), start=f"{adresse}?fall=fremd", trockenlauf=True)
