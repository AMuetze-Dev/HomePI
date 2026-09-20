"""Die Prüferfreigabe — an einer nachgebauten Seite.

Die Selektoren zeigen sich erst am echten DFBnet; dafür gibt es keinen Ersatz.
Was sich hier prüfen lässt, ist die Frage, die teurer ist: **wann gilt eine
Freigabe als erledigt?**

Der eine Ausgang, den es nie geben darf, ist „erledigt", während in DFBnet
noch „Schiedsrichterfreigabe" steht. Der Staffelleiter glaubte dann, die
Freigabe sei passiert, und sieht nie wieder hin.
"""

from __future__ import annotations

from typing import Any

import pytest

from homepi_pruefdienst import freigabe


class FalscheSeite:
    """So viel Seite, wie die Freigabe anfasst.

    `status` ist eine Liste: der erste Eintrag gilt vor dem Klick, die
    weiteren nach jedem Neuladen. So lässt sich beschreiben, was DFBnet nach
    einer Freigabe wirklich tut — und was es tut, wenn sie nicht ankam.
    """

    def __init__(
        self,
        status: list[str],
        knoepfe: tuple[str, ...] = ("Prüferfreigabe",),
        gesperrt: bool = False,
        dialog: bool = True,
    ) -> None:
        self._status = status
        self._knoepfe = knoepfe
        self._gesperrt = gesperrt
        self._dialog = dialog
        self.geklickt: list[str] = []
        self.neu_geladen = 0

    # -- Seite ----------------------------------------------------------
    def wait_for_timeout(self, _ms: int) -> None:
        return None

    def reload(self, **_egal: Any) -> None:
        self.neu_geladen += 1
        if len(self._status) > 1:
            self._status.pop(0)

    def evaluate(self, _js: str) -> str:
        return self._status[0]

    @property
    def mouse(self) -> Any:
        class Maus:
            def wheel(self, *_egal: Any) -> None:
                return None

        return Maus()

    # -- Locators -------------------------------------------------------
    def locator(self, auswahl: str) -> Any:
        if auswahl == freigabe.SPIELVERLAUF_TAB:
            return _Knopf(self, "Spielverlauf")
        if auswahl == freigabe.DIALOG_CONTAINER:
            return _Dialog(self, vorhanden=self._dialog)
        return _Auswahl(self)


class _Auswahl:
    def __init__(self, seite: FalscheSeite) -> None:
        self.seite = seite

    def filter(self, has_text: Any = None, **_egal: Any) -> Any:
        treffer = [k for k in self.seite._knoepfe if has_text.match(k)]
        return _Knopf(self.seite, treffer[0] if treffer else "", da=bool(treffer))


class _Knopf:
    def __init__(self, seite: FalscheSeite, name: str, da: bool = True) -> None:
        self.seite = seite
        self.name = name
        self.da = da

    def count(self) -> int:
        return 1 if self.da else 0

    @property
    def first(self) -> Any:
        return self

    def is_visible(self) -> bool:
        return self.da

    def get_attribute(self, _name: str) -> str:
        return "btn disabled" if self.seite._gesperrt else "btn"

    def click(self, **_egal: Any) -> None:
        self.seite.geklickt.append(self.name)

    def locator(self, _auswahl: str) -> Any:
        return _Auswahl(self.seite)

    def wait_for(self, **_egal: Any) -> None:
        if not self.da:
            raise TimeoutError("nicht da")


class _Dialog:
    def __init__(self, seite: FalscheSeite, vorhanden: bool) -> None:
        self.seite = seite
        self.vorhanden = vorhanden

    def filter(self, **_egal: Any) -> Any:
        return self

    @property
    def first(self) -> Any:
        return self

    def wait_for(self, **_egal: Any) -> None:
        if not self.vorhanden:
            raise TimeoutError("kein Dialog")

    def locator(self, _auswahl: str) -> Any:
        return _DialogKnopf(self.seite)


class _DialogKnopf:
    def __init__(self, seite: FalscheSeite) -> None:
        self.seite = seite

    def filter(self, **_egal: Any) -> Any:
        return self

    @property
    def first(self) -> Any:
        return self

    def click(self, **_egal: Any) -> None:
        self.seite.geklickt.append("OK")


class TestSchonFreigegeben:
    def test_wer_schon_freigegeben_ist_wird_nicht_noch_einmal_geklickt(self) -> None:
        """Der Staffelleiter kann es von Hand getan haben. Das ist kein
        Fehlschlag."""
        seite = FalscheSeite(["Prüferfreigabe"])

        ergebnis = freigabe.pruferfreigabe(seite, "M-1")

        assert ergebnis.erfolg is True
        assert ergebnis.schon_erledigt is True
        assert seite.geklickt == []


class TestFreigeben:
    def test_der_uebliche_weg(self) -> None:
        seite = FalscheSeite(["Schiedsrichterfreigabe", "Prüferfreigabe"])

        ergebnis = freigabe.pruferfreigabe(seite, "M-1")

        assert ergebnis.erfolg is True
        assert "Prüferfreigabe" in seite.geklickt
        assert "OK" in seite.geklickt

    def test_der_dialog_gehoert_dazu(self) -> None:
        """Ohne den Klick auf OK passiert bei DFBnet gar nichts."""
        seite = FalscheSeite(["Schiedsrichterfreigabe", "Prüferfreigabe"])

        freigabe.pruferfreigabe(seite, "M-1")

        assert seite.geklickt.index("Prüferfreigabe") < seite.geklickt.index("OK")

    def test_der_status_wird_zurueckgelesen(self) -> None:
        """Ein Klick, der keine Ausnahme wirft, ist kein Beweis."""
        seite = FalscheSeite(["Schiedsrichterfreigabe", "Prüferfreigabe"])

        freigabe.pruferfreigabe(seite, "M-1")

        assert seite.neu_geladen >= 1


class TestWennEsNichtKlappt:
    def test_ein_gesperrter_knopf_ist_eine_antwort_und_kein_absturz(self) -> None:
        seite = FalscheSeite(["Schiedsrichterfreigabe"], gesperrt=True)

        ergebnis = freigabe.pruferfreigabe(seite, "M-1")

        assert ergebnis.erfolg is False
        assert "gesperrt" in ergebnis.meldung

    def test_ohne_knopf_wird_es_laut(self) -> None:
        seite = FalscheSeite(["Schiedsrichterfreigabe"], knoepfe=())

        with pytest.raises(freigabe.FreigabeFehler):
            freigabe.pruferfreigabe(seite, "M-1")

    def test_ein_status_der_sich_nicht_aendert_ist_ein_fehlschlag(self) -> None:
        """Das ist der Ausgang, den es nie geben darf: „erledigt", während
        DFBnet noch auf Schiedsrichterfreigabe steht."""
        seite = FalscheSeite(["Schiedsrichterfreigabe"])

        with pytest.raises(freigabe.FreigabeFehler) as fehler:
            freigabe.pruferfreigabe(seite, "M-1")

        assert "Schiedsrichterfreigabe" in str(fehler.value)

    def test_ein_fehlender_dialog_steht_in_der_meldung(self) -> None:
        seite = FalscheSeite(["Schiedsrichterfreigabe"], dialog=False)

        with pytest.raises(freigabe.FreigabeFehler) as fehler:
            freigabe.pruferfreigabe(seite, "M-1")

        assert "Bestätigungsdialog" in str(fehler.value)

    def test_und_wer_zurueckgenommen_hat_ist_schon_fertig(self) -> None:
        """Steht „Freigabe zurücknehmen" da und der Status passt, war die
        Freigabe schon erteilt."""
        seite = FalscheSeite(
            ["Prüferfreigabe", "Prüferfreigabe"], knoepfe=("Freigabe zurücknehmen",)
        )

        ergebnis = freigabe.pruferfreigabe(seite, "M-1")

        assert ergebnis.erfolg is True
        assert ergebnis.schon_erledigt is True
