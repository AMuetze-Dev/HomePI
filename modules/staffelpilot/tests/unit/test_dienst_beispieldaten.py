"""Erfundene Spiele gehören nicht zwischen echte.

Der Prüfdienst bringt eine Attrappe mit, die zu jeder Staffel Spiele erfindet.
Zum Durchklicken ist sie unverzichtbar; zwischen einunddreißig echten Spielen
ist sie ein Spiel, aus dem eine Mahnung an einen Verein entstehen kann, den
niemand geprüft hat.

Deshalb hier die härtere Zusicherung: **aus heißt aus.** Nicht "wird
ausgefiltert", nicht "wird markiert" — der ganze Lauf wird abgewiesen, mit
einem Satz, der sagt, welcher Schalter fehlt.
"""

from __future__ import annotations

import pytest

from homepi_staffelpilot import dienst


def test_eine_dfbnet_kennung_ist_kein_beispiel() -> None:
    assert not dienst.ist_beispiel("031DHM03G4000000VS5489BUVUR5FS5A")


def test_die_attrappe_benennt_sich_selbst() -> None:
    assert dienst.ist_beispiel("DEMO-aa67-1")


def test_ohne_schalter_wird_der_lauf_abgewiesen() -> None:
    with pytest.raises(dienst.BeispieldatenNichtErlaubt) as fehler:
        dienst.beispieldaten_pruefen(["031DHM03", "DEMO-aa67-1"], erlaubt=False)

    assert "DEMO-aa67-1" in str(fehler.value)
    assert fehler.value.status == 409


def test_der_fehler_sagt_was_zu_tun_ist() -> None:
    """Eine Meldung, die nur „nicht erlaubt" sagt, kostet eine Stunde Suchen."""
    with pytest.raises(dienst.BeispieldatenNichtErlaubt) as fehler:
        dienst.beispieldaten_pruefen(["DEMO-x-1"], erlaubt=False)

    text = str(fehler.value)
    assert "Prüfdienst" in text
    assert "Beispieldaten annehmen" in text


def test_viele_erfundene_spiele_machen_die_meldung_nicht_unlesbar() -> None:
    with pytest.raises(dienst.BeispieldatenNichtErlaubt) as fehler:
        dienst.beispieldaten_pruefen([f"DEMO-x-{n}" for n in range(20)], erlaubt=False)

    assert "20 erfundene Spiele" in str(fehler.value)


def test_ein_echter_lauf_kommt_durch() -> None:
    dienst.beispieldaten_pruefen(["031DHM03", "031DHM04"], erlaubt=False)


def test_mit_schalter_kommt_die_attrappe_durch() -> None:
    """Wer durchklicken will, schaltet es ein — einmal, bewusst."""
    dienst.beispieldaten_pruefen(["DEMO-aa67-1"], erlaubt=True)


def test_der_schalter_ist_aus() -> None:
    """Die Voreinstellung ist die ganze Zusicherung.

    Stünde sie auf an, wäre dieses Modul eine Dokumentation und keine Sperre.
    """
    assert dienst.Einstellungen().beispieldaten is False


def test_der_praefix_ist_der_des_pruefdienstes() -> None:
    """Dieselbe Zeichenkette steht in zwei Diensten.

    Ändert sie dort, kommt ein erfundenes Spiel durch — und dieser Test ist
    die Stelle, an der das auffällt. `leser.BeispielLeser` baut die Kennung
    als f"DEMO-{kurz}-{nummer}".
    """
    assert dienst.BEISPIEL_PRAEFIX == "DEMO-"
