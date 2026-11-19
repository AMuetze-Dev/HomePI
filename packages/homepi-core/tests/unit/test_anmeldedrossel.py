"""Die Sperre gegen Durchprobieren - ohne Datenbank, in Millisekunden.

Solange das Gateway nur im LAN stand, war das kein Thema: Wer dort raten
wollte, sass schon im Haus. Seit die Anmeldung aus dem Internet erreichbar
ist, kann jeder es versuchen, so oft er will - und ein Passwort, das gegen
einen Nachbarn reicht, reicht nicht gegen ein Skript.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from homepi_core.auth import dienst
from homepi_core.auth.drossel import Anmeldedrossel

JETZT = datetime(2026, 11, 19, 20, 0, tzinfo=UTC)


def vor(minuten: float) -> datetime:
    return JETZT - timedelta(minutes=minuten)


class TestWartezeit:
    def test_ohne_fehlversuch_darf_man(self) -> None:
        assert dienst.wartezeit([], JETZT) == timedelta(0)

    def test_ein_paar_vertipper_sperren_nicht(self) -> None:
        """Vier Fehlversuche sind ein Mensch, der sein Passwort sucht."""
        fehler = [vor(4), vor(3), vor(2), vor(1)]

        assert dienst.wartezeit(fehler, JETZT) == timedelta(0)

    def test_der_fuenfte_fehlversuch_sperrt(self) -> None:
        fehler = [vor(5), vor(4), vor(3), vor(2), vor(1)]

        assert dienst.wartezeit(fehler, JETZT) > timedelta(0)

    def test_gesperrt_bis_der_aelteste_aus_dem_fenster_faellt(self) -> None:
        """Nicht pauschal eine Viertelstunde ab jetzt: Wer seit zehn Minuten
        nichts mehr versucht hat, wartet nur noch die restlichen fuenf."""
        fehler = [vor(10), vor(9), vor(8), vor(7), vor(6)]

        assert dienst.wartezeit(fehler, JETZT) == dienst.FEHLVERSUCH_FENSTER - timedelta(minutes=10)

    def test_alte_fehlversuche_zaehlen_nicht(self) -> None:
        fehler = [vor(60), vor(50), vor(40), vor(30), vor(1)]

        assert dienst.wartezeit(fehler, JETZT) == timedelta(0)

    def test_die_reihenfolge_der_eingabe_ist_gleich(self) -> None:
        geordnet = [vor(5), vor(4), vor(3), vor(2), vor(1)]

        assert dienst.wartezeit(list(reversed(geordnet)), JETZT) == dienst.wartezeit(
            geordnet, JETZT
        )


class TestAnmeldedrossel:
    def test_merkt_sich_fehlversuche_je_name(self) -> None:
        drossel = Anmeldedrossel()

        drossel.vermerke("aaron", vor(1))
        drossel.vermerke("aaron", vor(0))

        assert len(drossel.fehlversuche("aaron")) == 2
        assert drossel.fehlversuche("jessi") == []

    def test_gross_klein_und_leerzeichen_sind_derselbe_name(self) -> None:
        """Sonst probiert man "Aaron", "aaron" und " aaron " und hat
        dreimal so viele Versuche."""
        drossel = Anmeldedrossel()

        drossel.vermerke(" Aaron ", vor(1))

        assert len(drossel.fehlversuche("aaron")) == 1

    def test_vergisst_nach_erfolgreicher_anmeldung(self) -> None:
        drossel = Anmeldedrossel()
        drossel.vermerke("aaron", vor(1))

        drossel.vergiss("aaron")

        assert drossel.fehlversuche("aaron") == []

    def test_raeumt_alte_eintraege_weg(self) -> None:
        """Wer tausend erfundene Namen ausprobiert, soll damit nicht den
        Speicher fuellen - nach dem Fenster ist ein Eintrag nichts mehr wert."""
        drossel = Anmeldedrossel()
        for nummer in range(50):
            drossel.vermerke(f"erfunden{nummer}", vor(60))

        drossel.raeume_auf(JETZT)

        assert drossel.anzahl_namen == 0
