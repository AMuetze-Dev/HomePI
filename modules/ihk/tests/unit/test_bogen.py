"""Der Korrekturbogen als PDF - ohne Datenbank, nur Bytes."""

from __future__ import annotations

from homepi_ihk.bogen import latin1, pdf_aus
from homepi_ihk.dienst import Bewertung, aendere_bewertung, korrekturbogen


def _text(pdf: bytes) -> str:
    return pdf.decode("latin-1")


def test_erzeugt_ein_pdf_mit_name_und_bemerkung() -> None:
    bewertung = aendere_bewertung(
        Bewertung(), doku={"doku.1.1": 1}, doku_bemerkungen={"doku.1": "Saubere Gliederung"}
    )
    pdf = pdf_aus(
        korrekturbogen("Muster, Max", "4711", "K. Orrektor", bewertung), komprimiert=False
    )

    assert pdf.startswith(b"%PDF")
    inhalt = _text(pdf)
    assert "Muster, Max" in inhalt
    assert "4711" in inhalt
    assert "K. Orrektor" in inhalt
    assert "Saubere Gliederung" in inhalt
    assert "Korrekturbogen Projektarbeit" in inhalt


def test_umlaute_und_typografische_zeichen_brechen_nicht() -> None:
    bewertung = aendere_bewertung(
        Bewertung(), doku_bemerkungen={"doku.1": "„Schön“ \u2013 aber zu lang … ✓"}
    )
    pdf = pdf_aus(korrekturbogen("Özdemir, Jürgen", "", "", bewertung), komprimiert=False)
    assert pdf.startswith(b"%PDF")


def test_latin1_ersetzt_was_die_standardschrift_nicht_kennt() -> None:
    assert latin1("„Schön“ \u2013 gut … ✓") == '"Schön" - gut ... ?'
