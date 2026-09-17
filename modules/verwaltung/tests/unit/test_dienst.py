"""Die Regeln, die auch einen Verwalter binden.

Rein, ohne Datenbank, Millisekunden. Genau deshalb stehen sie in dienst.py und
nicht im Router: eine Regel, die einen Verwalter aussperren kann, muss sich
vollständig durchtesten lassen.
"""

from __future__ import annotations

import uuid

import pytest
from homepi_core.auth import VERWALTUNG, Rolle
from homepi_core.auth.dienst import LetzterVerwalter

from homepi_verwaltung.dienst import (
    SelbstSchutz,
    pruefe_loeschen,
    pruefe_nicht_selbst,
    pruefe_rollenwechsel,
    pruefe_sperren,
    sichtbare_rechte,
)

ICH = uuid.UUID("11111111-1111-4111-8111-111111111111")
ANDERE = uuid.UUID("22222222-2222-4222-8222-222222222222")


class TestNichtSelbst:
    def test_am_fremden_konto_ist_alles_erlaubt(self) -> None:
        pruefe_nicht_selbst(ICH, ANDERE, "Löschen")

    def test_am_eigenen_nicht(self) -> None:
        with pytest.raises(SelbstSchutz, match="eigenen Konto"):
            pruefe_nicht_selbst(ICH, ICH, "Löschen")


class TestRollenwechsel:
    def test_fremde_artefakte_sind_frei(self) -> None:
        """Nur die Verwaltung ist heikel. Wer sich selbst die Geräte entzieht,
        kann sie sich anschließend wiedergeben."""
        pruefe_rollenwechsel(
            eigene_id=ICH,
            ziel_id=ICH,
            artefakt="geraete",
            neue_rolle=None,
            anzahl_verwalter=1,
            ziel_ist_verwalter=True,
        )

    def test_niemand_nimmt_sich_selbst_die_verwaltung(self) -> None:
        """Er könnte es nicht zurücknehmen - und säße vor einer Oberfläche,
        die ihn nicht mehr hineinlässt."""
        with pytest.raises(SelbstSchutz):
            pruefe_rollenwechsel(
                eigene_id=ICH,
                ziel_id=ICH,
                artefakt=VERWALTUNG,
                neue_rolle=None,
                anzahl_verwalter=5,
                ziel_ist_verwalter=True,
            )

    def test_herabstufen_zaehlt_wie_entziehen(self) -> None:
        with pytest.raises(SelbstSchutz):
            pruefe_rollenwechsel(
                eigene_id=ICH,
                ziel_id=ICH,
                artefakt=VERWALTUNG,
                neue_rolle=Rolle.LESER,
                anzahl_verwalter=5,
                ziel_ist_verwalter=True,
            )

    def test_sich_selbst_verwalter_bleiben_ist_kein_wechsel(self) -> None:
        pruefe_rollenwechsel(
            eigene_id=ICH,
            ziel_id=ICH,
            artefakt=VERWALTUNG,
            neue_rolle=Rolle.VERWALTER,
            anzahl_verwalter=1,
            ziel_ist_verwalter=True,
        )

    def test_der_letzte_verwalter_bleibt(self) -> None:
        with pytest.raises(LetzterVerwalter, match="letzten Verwalter"):
            pruefe_rollenwechsel(
                eigene_id=ICH,
                ziel_id=ANDERE,
                artefakt=VERWALTUNG,
                neue_rolle=None,
                anzahl_verwalter=1,
                ziel_ist_verwalter=True,
            )

    def test_mit_zweitem_verwalter_geht_es(self) -> None:
        pruefe_rollenwechsel(
            eigene_id=ICH,
            ziel_id=ANDERE,
            artefakt=VERWALTUNG,
            neue_rolle=None,
            anzahl_verwalter=2,
            ziel_ist_verwalter=True,
        )

    def test_wer_gar_kein_verwalter_ist_faellt_nicht_darunter(self) -> None:
        # Sonst liesse sich einem Nicht-Verwalter nichts mehr entziehen,
        # sobald es nur noch einen Verwalter gibt.
        pruefe_rollenwechsel(
            eigene_id=ICH,
            ziel_id=ANDERE,
            artefakt=VERWALTUNG,
            neue_rolle=None,
            anzahl_verwalter=1,
            ziel_ist_verwalter=False,
        )

    def test_jemanden_zum_verwalter_machen_geht_immer(self) -> None:
        pruefe_rollenwechsel(
            eigene_id=ICH,
            ziel_id=ANDERE,
            artefakt=VERWALTUNG,
            neue_rolle=Rolle.VERWALTER,
            anzahl_verwalter=1,
            ziel_ist_verwalter=False,
        )


class TestLoeschen:
    def test_nicht_das_eigene(self) -> None:
        with pytest.raises(SelbstSchutz):
            pruefe_loeschen(eigene_id=ICH, ziel_id=ICH, anzahl_verwalter=5, ziel_ist_verwalter=True)

    def test_nicht_den_letzten_verwalter(self) -> None:
        with pytest.raises(LetzterVerwalter):
            pruefe_loeschen(
                eigene_id=ICH, ziel_id=ANDERE, anzahl_verwalter=1, ziel_ist_verwalter=True
            )

    def test_ein_gewoehnliches_konto_geht(self) -> None:
        pruefe_loeschen(eigene_id=ICH, ziel_id=ANDERE, anzahl_verwalter=1, ziel_ist_verwalter=False)


class TestSperren:
    def test_entsperren_ist_immer_harmlos(self) -> None:
        pruefe_sperren(
            eigene_id=ICH,
            ziel_id=ICH,
            aktiv=True,
            anzahl_verwalter=1,
            ziel_ist_verwalter=True,
        )

    def test_sich_selbst_sperren_geht_nicht(self) -> None:
        with pytest.raises(SelbstSchutz):
            pruefe_sperren(
                eigene_id=ICH,
                ziel_id=ICH,
                aktiv=False,
                anzahl_verwalter=5,
                ziel_ist_verwalter=True,
            )

    def test_den_letzten_verwalter_sperren_geht_nicht(self) -> None:
        """Sonst liesse sich die Einrichtung wieder oeffnen, indem man den
        letzten Verwalter stilllegt."""
        with pytest.raises(LetzterVerwalter):
            pruefe_sperren(
                eigene_id=ICH,
                ziel_id=ANDERE,
                aktiv=False,
                anzahl_verwalter=1,
                ziel_ist_verwalter=True,
            )


def test_sichtbare_rechte_sind_alphabetisch() -> None:
    rechte = {"staffelpilot": Rolle.NUTZER, "geraete": Rolle.LESER}

    assert list(sichtbare_rechte(rechte)) == ["geraete", "staffelpilot"]
    assert sichtbare_rechte(rechte)["geraete"] == "leser"
