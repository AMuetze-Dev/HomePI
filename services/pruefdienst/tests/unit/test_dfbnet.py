"""Der echte Leser — an den Stellen, die ohne Browser prüfbar sind.

`dfbnet.py` fährt sonst einen Browser und ist deshalb von der Abdeckung
ausgenommen. Zwei Dinge lassen sich trotzdem festhalten, und beide haben beim
ersten echten Lauf gegen DFBnet Geld gekostet:

1. **Ohne Spielverlauf gibt es keinen Bericht.** Im Verlaufsreiter stehen die
   elektronischen Bestätigungen. Fehlt er, meldet die Regelprüfung für jede
   Mannschaft eine fehlende Bestätigung — beim ersten Lauf waren das 48
   erfundene Befunde auf 24 Spielen.
2. **Die Kennung der Schnittstelle ist eine andere als die der Trefferliste.**
   Der Bericht wird als `report/<kennung>` verlinkt und öffnet sich als
   `report-details/<andere kennung>`. Mit der ersten antwortet die
   Aufstellungsschnittstelle 404, und der Kader bleibt leer.

Der Rest — Selektoren, Wartezeiten, das Fenster — zeigt sich erst am echten
DFBnet. Dafür gibt es keinen Ersatz, und diese Datei tut nicht so.
"""

from __future__ import annotations

from typing import Any

import pytest

from homepi_pruefdienst import dienst
from homepi_pruefdienst.dfbnet import DfbnetLeser


class FalscheSeite:
    """Gerade so viel Seite, wie `bericht()` anfasst."""

    def __init__(self, verlauf_kommt: bool = True, treffer: int = 1) -> None:
        self.verlauf_kommt = verlauf_kommt
        self.treffer = treffer
        self.geschlossen = False
        self.url = "https://www.dfbnet.org/sbo-mobile/v2/#/match-report/report-details/NEU/info"
        self.context = self

    # -- als Trefferliste ------------------------------------------------
    def locator(self, _auswahl: str) -> Any:
        return self

    @property
    def first(self) -> Any:
        return self

    def count(self) -> int:
        return self.treffer

    def nth(self, _nummer: int) -> Any:
        return self

    def click(self, **_egal: Any) -> None:
        return None

    def expect_popup(self, **_egal: Any) -> Any:
        seite = self

        class Fenster:
            def __enter__(self) -> Any:
                return self

            def __exit__(self, *_egal: Any) -> None:
                return None

            @property
            def value(self) -> Any:
                return seite

        return Fenster()

    # -- als geoeffneter Bericht ----------------------------------------
    def set_default_timeout(self, _ms: int) -> None:
        return None

    def wait_for_load_state(self, *_egal: Any, **_auch: Any) -> None:
        return None

    def wait_for_timeout(self, _ms: int) -> None:
        return None

    def content(self) -> str:
        return "<html><body><mr-report-info></mr-report-info></body></html>"

    def close(self) -> None:
        self.geschlossen = True

    # -- als Schnittstelle ----------------------------------------------
    @property
    def request(self) -> Any:
        return self

    def get(self, _adresse: str, **_egal: Any) -> Any:
        class Antwort:
            status = 500

        return Antwort()


@pytest.fixture
def leser() -> DfbnetLeser:
    return DfbnetLeser()


class TestOhneSpielverlauf:
    def test_kommt_kein_bericht(self, leser: DfbnetLeser, monkeypatch: pytest.MonkeyPatch) -> None:
        """Lieber "nicht gelesen" als zwei erfundene fehlende Bestätigungen."""
        seite = FalscheSeite()
        leser._seite = seite
        monkeypatch.setattr("homepi_pruefdienst.dfbnet._warten_auf", lambda *a, **k: True)
        monkeypatch.setattr(DfbnetLeser, "_verlauf", lambda self, popup, kennung: "")

        assert leser.bericht("M-1") is None

    def test_und_das_fenster_geht_trotzdem_zu(
        self, leser: DfbnetLeser, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Achtzig Berichte hinterlassen sonst achtzig offene Fenster."""
        seite = FalscheSeite()
        leser._seite = seite
        monkeypatch.setattr("homepi_pruefdienst.dfbnet._warten_auf", lambda *a, **k: True)
        monkeypatch.setattr(DfbnetLeser, "_verlauf", lambda self, popup, kennung: "")

        leser.bericht("M-1")

        assert seite.geschlossen is True


class TestOhneVerweis:
    def test_ein_spiel_ohne_verweis_wird_nicht_geraten(self, leser: DfbnetLeser) -> None:
        leser._seite = FalscheSeite(treffer=0)

        assert leser.bericht("M-1") is None


class TestOhneAnmeldung:
    def test_erst_anmelden_dann_lesen(self, leser: DfbnetLeser) -> None:
        with pytest.raises(RuntimeError):
            leser.bericht("M-1")

        with pytest.raises(RuntimeError):
            leser.spiele(dienst.Staffelkennung(name="Stadtliga C"), None, None)  # type: ignore[arg-type]


class TestKennungDerSchnittstelle:
    def test_die_adresse_des_geoeffneten_berichts_zaehlt(self) -> None:
        """`report-details` — mit der Kennung aus der Trefferliste antwortet
        die Aufstellungsschnittstelle 404."""
        url = "https://www.dfbnet.org/sbo-mobile/v2/#/match-report/report-details/ABC123/info"

        assert dienst.kennung_aus_href(url) == "ABC123"

    def test_und_die_der_trefferliste_auch(self) -> None:
        assert dienst.kennung_aus_href("/match-report/report/XYZ789?dmg_company=DFBNET") == "XYZ789"
