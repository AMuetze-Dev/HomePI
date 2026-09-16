from __future__ import annotations

import pytest
from pydantic import ValidationError

from homepi_geraete.schemas import GeraetAnlegen


def test_leerzeichen_werden_getrimmt() -> None:
    daten = GeraetAnlegen(name="  Stehlampe  ", raum=" Wohnzimmer ")

    assert daten.name == "Stehlampe"
    assert daten.raum == "Wohnzimmer"


def test_ein_name_aus_leerzeichen_ist_kein_name() -> None:
    """min_length allein wuerde '   ' durchlassen."""
    with pytest.raises(ValidationError):
        GeraetAnlegen(name="   ", raum="Küche")


def test_unbekannter_zustand_wird_abgelehnt() -> None:
    with pytest.raises(ValidationError):
        GeraetAnlegen(name="Lampe", raum="Küche", zustand="kaputt")  # type: ignore[arg-type]


def test_standardwerte() -> None:
    daten = GeraetAnlegen(name="Lampe", raum="Küche")

    assert daten.zustand == "bereit"
    assert daten.eingeschaltet is False


def test_zu_langer_name_wird_abgelehnt() -> None:
    with pytest.raises(ValidationError):
        GeraetAnlegen(name="x" * 101, raum="Küche")
