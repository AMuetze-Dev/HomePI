"""Die Anmeldung selbst - ohne sie erscheint das Artefakt nirgends."""

from __future__ import annotations

from homepi_core import Modul, Zugang
from homepi_core.auth import Rolle


def test_modul_ist_korrekt_beschrieben(modul: Modul) -> None:
    assert modul.id == "geraete"
    assert modul.titel == "Geräte"
    assert modul.praefix == "/geraete"
    assert modul.version


def test_die_geraete_im_haus_sind_nicht_oeffentlich(modul: Modul) -> None:
    """Wer kein Recht 'geraete' hat, soll das Artefakt nicht einmal im
    Manifest sehen. Waere es oeffentlich, laege das Haus auf jeder Seite offen,
    die dieses Gateway ausliefert."""
    assert modul.zugang is Zugang.GESCHUETZT
    assert not modul.sichtbar_fuer(None)
    assert not modul.sichtbar_fuer({"staffelpilot": Rolle.VERWALTER})
    assert modul.sichtbar_fuer({"geraete": Rolle.LESER})


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
