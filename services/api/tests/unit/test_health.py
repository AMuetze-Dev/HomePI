"""Die Auswertungslogik - reine Funktion, keine Fixtures, Millisekunden."""

from __future__ import annotations

import pytest

from homepi_api.health import Status, evaluate


def test_alles_gesund_ist_ok() -> None:
    report = evaluate({"database": True, "redis": True})

    assert report.status is Status.OK
    assert report.http_status == 200


def test_essenzielle_abhaengigkeit_kaputt_ist_down() -> None:
    report = evaluate({"database": False, "redis": True})

    assert report.status is Status.DOWN
    assert report.http_status == 503


def test_nebensaechliches_kaputt_ist_degraded() -> None:
    """Ohne Redis kann die API weiterarbeiten, nur langsamer."""
    report = evaluate({"database": True, "redis": False})

    assert report.status is Status.DEGRADED
    # degraded meldet trotzdem 503, damit die Ueberwachung es sieht
    assert report.http_status == 503


def test_bericht_enthaelt_die_einzelpruefungen() -> None:
    checks = {"database": True, "redis": False}

    assert evaluate(checks).checks == checks


def test_leere_pruefung_ist_ein_programmierfehler() -> None:
    with pytest.raises(ValueError, match="mindestens eine"):
        evaluate({})


def test_bericht_ist_unveraenderlich() -> None:
    report = evaluate({"database": True})

    with pytest.raises(AttributeError):
        report.status = Status.DOWN  # type: ignore[misc]
