"""Wer was sieht -- ohne Datenbank."""

from __future__ import annotations

import uuid

import pytest

from homepi_staffelpilot import dienst

ICH = uuid.UUID("11111111-1111-1111-1111-111111111111")
ANDERER = uuid.UUID("22222222-2222-2222-2222-222222222222")


class TestDienstkonto:
    """Das Konto des Pruefdienstes ist benannt und nicht an der Rolle erkannt."""

    def test_das_benannte_konto_mit_verwalterrecht(self) -> None:
        assert dienst.ist_dienstkonto("pruefdienst", verwalter=True, dienstkonto="pruefdienst")

    def test_ein_anderer_verwalter_ist_es_nicht(self) -> None:
        assert not dienst.ist_dienstkonto("aaron", verwalter=True, dienstkonto="pruefdienst")

    def test_der_name_allein_reicht_nicht(self) -> None:
        assert not dienst.ist_dienstkonto("pruefdienst", verwalter=False, dienstkonto="pruefdienst")

    @pytest.mark.parametrize("unbenannt", ["", "   "])
    def test_ohne_angabe_ist_es_niemand(self, unbenannt: str) -> None:
        assert not dienst.ist_dienstkonto("", verwalter=True, dienstkonto=unbenannt)
        assert not dienst.ist_dienstkonto("pruefdienst", verwalter=True, dienstkonto=unbenannt)

    def test_gross_und_klein_zaehlt_nicht(self) -> None:
        assert dienst.ist_dienstkonto("pruefdienst", verwalter=True, dienstkonto=" Pruefdienst ")


class TestBlick:
    def test_ein_mensch_sieht_sich(self) -> None:
        blick = dienst.blick_fuer(ich=ICH, ist_dienst=False, konto=None)

        assert blick.konto == ICH
        assert not blick.dienst

    def test_ein_mensch_darf_sich_selbst_nennen(self) -> None:
        assert dienst.blick_fuer(ich=ICH, ist_dienst=False, konto=ICH).konto == ICH

    def test_ein_mensch_sieht_nicht_durch_fremde_augen(self) -> None:
        with pytest.raises(dienst.KontoFremd):
            dienst.blick_fuer(ich=ICH, ist_dienst=False, konto=ANDERER)

    def test_der_dienst_sieht_alles(self) -> None:
        blick = dienst.blick_fuer(ich=ICH, ist_dienst=True, konto=None)

        assert blick.konto is None
        assert blick.dienst

    def test_der_dienst_arbeitet_fuer_ein_konto(self) -> None:
        blick = dienst.blick_fuer(ich=ICH, ist_dienst=True, konto=ANDERER)

        assert blick.konto == ANDERER
        assert blick.dienst

    def test_was_einem_konto_gehoert_braucht_ein_konto(self) -> None:
        with pytest.raises(dienst.KontoFehlt):
            dienst.konto_von(dienst.Blick(konto=None, dienst=True))

        assert dienst.konto_von(dienst.Blick(konto=ICH)) == ICH


class TestName:
    def test_denselben_gibt_man_nicht_zweimal(self) -> None:
        with pytest.raises(dienst.StaffelVergeben, match="gibt es bereits"):
            dienst.name_frei("Stadtliga C", ["Stadtliga A", "Stadtliga C"])

    def test_ein_anderer_ist_frei(self) -> None:
        dienst.name_frei("Stadtliga B", ["Stadtliga A", "Stadtliga C"])


class TestFreigegeben:
    """Wessen Uebertragungen hinaus duerfen."""

    def test_wer_nichts_gesagt_hat_ist_angehalten(self) -> None:
        assert dienst.freigegebene({ICH: {}, ANDERER: {"verband": "SFV"}}) == set()

    def test_nur_wer_freigegeben_hat(self) -> None:
        roh = {
            ICH: {"uebertragung_pausiert": "False"},
            ANDERER: {"uebertragung_pausiert": "True"},
        }

        assert dienst.freigegebene(roh) == {ICH}
