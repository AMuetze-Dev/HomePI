"""Der Spielkatalog - die Texte, die die Eltern auf der Website lesen."""

from __future__ import annotations

import pytest

from homepi_kinderzimmer.spiele import PHASEN, SPIELE, spiel


def test_alle_besprochenen_spiele_stehen_im_katalog() -> None:
    assert [s.id for s in SPIELE] == [
        "licht-und-klang",
        "stimmen",
        "kuckuck",
        "tierlaute",
        "farben",
        "formen",
        "rituale",
        "hoerfiguren",
        "mengen",
        "echo",
        "gefuehle",
        "anlaute",
    ]


def test_die_nummern_laufen_lueckenlos() -> None:
    assert [s.nummer for s in SPIELE] == list(range(1, len(SPIELE) + 1))


@pytest.mark.parametrize("eintrag", SPIELE, ids=lambda s: s.id)
def test_jedes_spiel_erklaert_sich_vollstaendig(eintrag) -> None:
    """Wie es geht, was es foerdert, warum - ohne eines davon ist der Eintrag
    fuer die Eltern nur ein Name."""
    for feld in ("titel", "alter", "ablauf", "foerdert", "warum"):
        assert getattr(eintrag, feld).strip(), f"{eintrag.id}: {feld} fehlt"
    # Die Begruendung ist ein kleiner Absatz, kein Schlagwort.
    assert len(eintrag.warum) > 200, f"{eintrag.id}: Begruendung zu knapp"


@pytest.mark.parametrize("eintrag", SPIELE, ids=lambda s: s.id)
def test_die_texte_bleiben_lesbar(eintrag) -> None:
    """Einfache Sprache heisst auch: kurze Saetze. Ein Satz ueber 45 Woerter
    liest niemand, der nebenbei ein Baby haelt."""
    for feld in ("ablauf", "foerdert", "warum"):
        for satz in getattr(eintrag, feld).replace("!", ".").replace("?", ".").split(". "):
            assert len(satz.split()) <= 45, f"{eintrag.id}/{feld}: {satz[:60]}..."


def test_nur_phase_eins_ist_bereit() -> None:
    """Bereit heisst: die Firmware kann es. Das gilt bisher nur fuer Phase 1."""
    assert {s.id for s in SPIELE if s.bereit} == {"licht-und-klang", "stimmen"}
    assert all(s.phase == 1 for s in SPIELE if s.bereit)


def test_jede_phase_ist_beschrieben() -> None:
    assert {s.phase for s in SPIELE} == {p.nummer for p in PHASEN}
    assert all(p.titel and p.alter for p in PHASEN)


def test_spiel_nach_kennung() -> None:
    assert spiel("stimmen").titel == "Vertraute Stimmen"
    assert spiel("gibt-es-nicht") is None
