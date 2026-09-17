"""Die Anmeldung des Artefakts - ohne sie erscheint es nirgends.

Dazu die Frage, die bei diesem Artefakt schwerer wiegt als bei jedem anderen:
kommt wirklich nur ein Verwalter hinein?
"""

from __future__ import annotations

from homepi_core import Modul, Zugang
from homepi_core.auth import VERWALTUNG, Rolle


def test_modul_ist_korrekt_beschrieben(modul: Modul) -> None:
    assert modul.id == "verwaltung"
    assert modul.titel == "Verwaltung"
    assert modul.praefix == "/verwaltung"
    assert modul.version


def test_die_kennung_ist_die_aus_homepi_core(modul: Modul) -> None:
    """An dieser Zeichenkette hängt die Frage 'gibt es hier schon einen
    Verwalter?'. Stünde sie zweimal im Code, ginge sie irgendwann auseinander -
    und die Ersteinrichtung wäre plötzlich wieder offen."""
    assert modul.id == VERWALTUNG


def test_nur_ein_verwalter_kommt_hinein(modul: Modul) -> None:
    assert modul.zugang is Zugang.GESCHUETZT
    assert modul.mindestrolle is Rolle.VERWALTER

    assert not modul.sichtbar_fuer(None)
    assert not modul.sichtbar_fuer({VERWALTUNG: Rolle.NUTZER})
    assert modul.sichtbar_fuer({VERWALTUNG: Rolle.VERWALTER})


def test_ein_recht_auf_ein_anderes_artefakt_hilft_nicht(modul: Modul) -> None:
    assert not modul.sichtbar_fuer({"geraete": Rolle.VERWALTER})


def test_manifest_hat_die_felder_der_kachel(modul: Modul) -> None:
    eintrag = modul.manifest()

    assert eintrag["status"] == "bereit"
    assert eintrag["pfad"] == "/verwaltung"
    assert eintrag["beschreibung"]


def test_entry_point_zeigt_auf_dieses_modul() -> None:
    """Prueft die Verdrahtung in pyproject.toml - ein Tippfehler dort faellt
    sonst erst auf, wenn die Kachel im Betrieb fehlt."""
    from importlib.metadata import entry_points

    punkte = {p.name: p for p in entry_points(group="homepi.module")}

    assert "verwaltung" in punkte, "Artefakt ist nicht als homepi.module angemeldet"
    assert punkte["verwaltung"].load().id == "verwaltung"


def test_jeder_endpunkt_hat_eine_beschreibung(modul: Modul) -> None:
    """Ohne summary bleibt der Endpunkt in der generischen Ansicht namenlos."""
    ohne = [
        f"{methode.upper()} {route.path}"
        for route in modul.router.routes
        for methode in getattr(route, "methods", set()) - {"HEAD", "OPTIONS"}
        if not getattr(route, "summary", None)
    ]

    assert not ohne, f"ohne summary: {', '.join(ohne)}"
