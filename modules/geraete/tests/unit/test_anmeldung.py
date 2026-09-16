"""Die Anmeldung selbst - ohne sie erscheint das Artefakt nirgends."""

from __future__ import annotations

from homepi_core import Modul


def test_modul_ist_korrekt_beschrieben(modul: Modul) -> None:
    assert modul.id == "geraete"
    assert modul.titel == "Geräte"
    assert modul.praefix == "/geraete"
    assert modul.version


def test_manifest_hat_die_felder_der_kachel(modul: Modul) -> None:
    eintrag = modul.manifest()

    assert eintrag["status"] == "bereit"
    assert eintrag["pfad"] == "/geraete"
    assert eintrag["beschreibung"]


def test_entry_point_zeigt_auf_dieses_modul() -> None:
    """Prueft die Verdrahtung in pyproject.toml - ein Tippfehler dort faellt
    sonst erst auf, wenn die Kachel im Betrieb fehlt."""
    from importlib.metadata import entry_points

    punkte = {p.name: p for p in entry_points(group="homepi.module")}

    assert "geraete" in punkte, "Artefakt ist nicht als homepi.module angemeldet"
    assert punkte["geraete"].load().id == "geraete"
