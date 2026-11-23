"""Der Regelsatz eines Staffelleiters: Schalter und Parameter je Regel.

Gespeichert wird nur, was von der Vorgabe abweicht. Leer heisst immer: die
Vorgabe gilt -- wie bei den Saetzen. Sonst hielte das erste Speichern den
heutigen Stand fest, und eine spaeter geaenderte Vorgabe kaeme bei niemandem
an, der einmal auf Speichern gedrueckt hat.
"""

from __future__ import annotations

import pytest

from homepi_staffelpilot import dienst
from homepi_staffelpilot.dienst import ParameterSicht, ParameterUngueltig

FRIST = ParameterSicht(schluessel="frist", art="uhrzeit", vorgabe="18:00")
KULANZ = ParameterSicht(schluessel="kulanz", art="stunden", vorgabe=0, kleinst=0, groesst=24)
NACH_ENDE = ParameterSicht(schluessel="nach_ende", art="minuten", vorgabe=60, kleinst=0)


class TestWertPruefen:
    @pytest.mark.parametrize(
        ("eingabe", "erwartet"),
        [("18:00", "18:00"), ("9:05", "09:05"), (" 23:59 ", "23:59"), ("00:00", "00:00")],
    )
    def test_eine_uhrzeit_wird_vereinheitlicht(self, eingabe: str, erwartet: str) -> None:
        assert dienst.wert_pruefen(FRIST, eingabe) == erwartet

    @pytest.mark.parametrize("eingabe", ["24:00", "18:60", "18 Uhr", "", 18, None])
    def test_keine_uhrzeit_wird_abgewiesen(self, eingabe: object) -> None:
        with pytest.raises(ParameterUngueltig, match="Uhrzeit"):
            dienst.wert_pruefen(FRIST, eingabe)

    def test_eine_zahl_innerhalb_der_grenzen(self) -> None:
        assert dienst.wert_pruefen(KULANZ, 6) == 6

    def test_eine_zahl_als_text_ist_auch_eine_zahl(self) -> None:
        """Ein Formularfeld liefert Text; die Oberflaeche soll das nicht wissen
        muessen."""
        assert dienst.wert_pruefen(KULANZ, "6") == 6

    @pytest.mark.parametrize("eingabe", [-1, 25])
    def test_ausserhalb_der_grenzen_sagt_die_grenzen(self, eingabe: int) -> None:
        with pytest.raises(ParameterUngueltig, match="zwischen 0 und 24"):
            dienst.wert_pruefen(KULANZ, eingabe)

    def test_nur_eine_untere_grenze(self) -> None:
        with pytest.raises(ParameterUngueltig, match="mindestens 0"):
            dienst.wert_pruefen(NACH_ENDE, -5)
        assert dienst.wert_pruefen(NACH_ENDE, 600) == 600

    def test_nur_eine_obere_grenze(self) -> None:
        bis_zehn = ParameterSicht(schluessel="x", art="zahl", vorgabe=1, groesst=10)
        with pytest.raises(ParameterUngueltig, match="höchstens 10"):
            dienst.wert_pruefen(bis_zehn, 11)

    @pytest.mark.parametrize("eingabe", ["sechs", True, 1.5, None, [6]])
    def test_keine_ganze_zahl_wird_abgewiesen(self, eingabe: object) -> None:
        """`True` ist in Python eine 1 -- als Kulanz waere das eine Stunde,
        die niemand eingegeben hat."""
        with pytest.raises(ParameterUngueltig, match="ganze Zahl"):
            dienst.wert_pruefen(KULANZ, eingabe)


class TestEigeneWerte:
    def test_nur_abweichungen_bleiben(self) -> None:
        werte = dienst.eigene_werte([FRIST, KULANZ], {"frist": "18:00", "kulanz": 6})
        assert werte == {"kulanz": 6}

    def test_leer_oder_none_heisst_vorgabe(self) -> None:
        assert dienst.eigene_werte([FRIST, KULANZ], {"frist": None, "kulanz": ""}) == {}

    def test_ein_unbekannter_parameter_wird_genannt(self) -> None:
        with pytest.raises(ParameterUngueltig, match="kennt keinen Wert „tag“"):
            dienst.eigene_werte([FRIST], {"tag": 1})

    def test_die_meldung_nennt_den_namen(self) -> None:
        benannt = ParameterSicht(
            schluessel="kulanz", name="Kulanz", art="stunden", vorgabe=0, kleinst=0, groesst=24
        )
        with pytest.raises(ParameterUngueltig, match=r"^Kulanz:"):
            dienst.eigene_werte([benannt], {"kulanz": 99})


class TestWirksam:
    def test_ohne_eigene_wahl_gilt_die_vorgabe(self) -> None:
        assert dienst.wirksam_aktiv(True, None) is True
        assert dienst.wirksam_aktiv(False, None) is False

    def test_die_eigene_wahl_gewinnt(self) -> None:
        assert dienst.wirksam_aktiv(True, False) is False
        assert dienst.wirksam_aktiv(False, True) is True

    def test_eine_wahl_gleich_der_vorgabe_wird_nicht_gespeichert(self) -> None:
        """Sonst bliebe die Regel aus, wenn die Vorgabe spaeter angeht."""
        assert dienst.eigene_wahl(True, True) is None
        assert dienst.eigene_wahl(True, False) is False
        assert dienst.eigene_wahl(False, True) is True

    def test_die_werte_fuellen_die_vorgaben_auf(self) -> None:
        assert dienst.wirksame_werte([FRIST, KULANZ], {"kulanz": 6}) == {
            "frist": "18:00",
            "kulanz": 6,
        }

    def test_ein_veralteter_wert_faellt_heraus(self) -> None:
        """Hat die Regel den Parameter nicht mehr, gilt er nicht mehr -- und
        ein ungueltig gewordener Wert faellt auf die Vorgabe zurueck, statt
        den Prueflauf abzubrechen."""
        assert dienst.wirksame_werte([KULANZ], {"weg": 1, "kulanz": 99}) == {"kulanz": 0}


class TestGueltigeWerte:
    """Was die Oberflaeche anzeigt, muss das sein, wonach geprueft wird."""

    def test_ein_gueltiger_bleibt(self) -> None:
        assert dienst.gueltige_werte([KULANZ], {"kulanz": 6}) == {"kulanz": 6}

    def test_ein_veralteter_faellt_heraus(self) -> None:
        """Sind die Grenzen enger geworden, prueft der Lauf mit der Vorgabe --
        und dann darf im Feld nicht mehr der alte Wert stehen."""
        assert dienst.gueltige_werte([KULANZ], {"kulanz": 99, "weg": 1}) == {}


class TestRegelsatz:
    def test_nur_was_aus_ist_und_was_werte_hat(self) -> None:
        aus, werte = dienst.regelsatz_aus(
            [("a", True), ("b", False), ("c", True)],
            {"c": [KULANZ]},
            {"a": (False, {}), "b": (True, {}), "c": (None, {"kulanz": 6})},
        )

        assert aus == ["a"]
        assert werte == {"c": {"kulanz": 6}}


class TestAngepasst:
    def test_unveraendert(self) -> None:
        assert dienst.ist_angepasst(None, {}, [KULANZ]) is False

    def test_ein_eigener_schalter(self) -> None:
        assert dienst.ist_angepasst(False, {}, [KULANZ]) is True

    def test_ein_eigener_wert(self) -> None:
        assert dienst.ist_angepasst(None, {"kulanz": 6}, [KULANZ]) is True

    def test_ein_veralteter_wert_zaehlt_nicht(self) -> None:
        assert dienst.ist_angepasst(None, {"kulanz": 99}, [KULANZ]) is False

    def test_ein_wert_ohne_parameter_zaehlt_nicht(self) -> None:
        assert dienst.ist_angepasst(None, {"weg": 1}, [KULANZ]) is False


class TestStaffelleitung:
    def test_eine_freie_staffel_laesst_sich_uebernehmen(self) -> None:
        dienst.uebernahme_pruefen(leiter=None, ich="a")

    def test_die_eigene_noch_einmal_ist_kein_fehler(self) -> None:
        dienst.uebernahme_pruefen(leiter="a", ich="a")

    def test_eine_fremde_nicht(self) -> None:
        with pytest.raises(dienst.StaffelGeleitet, match="Erika"):
            dienst.uebernahme_pruefen(leiter="b", ich="a", leiter_name="Erika")

    def test_abgeben_darf_der_leiter(self) -> None:
        dienst.abgabe_pruefen(leiter="a", ich="a", verwalter=False)

    def test_abgeben_darf_der_verwalter(self) -> None:
        """Sonst bliebe die Staffel eines Staffelleiters, der aufhoert, fuer
        immer bei ihm."""
        dienst.abgabe_pruefen(leiter="b", ich="a", verwalter=True)

    def test_sonst_niemand(self) -> None:
        with pytest.raises(dienst.StaffelGeleitet, match="nur, wer sie leitet"):
            dienst.abgabe_pruefen(leiter="b", ich="a", verwalter=False)
