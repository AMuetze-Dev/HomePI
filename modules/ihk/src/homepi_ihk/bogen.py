"""Setzt einen ``Bogen`` aus dem Rechenkern als PDF.

Keine Entscheidung, keine Datenbank: Was auf dem Bogen steht, legt
``dienst.korrekturbogen`` fest, hier wird es nur gezeichnet. Das Layout folgt
dem Druckbereich der Vorlage (A1:L80) und dem Ausdruck des ExamManager V2.

Die Standardschrift Helvetica braucht keine eingebettete Schriftdatei, kennt
aber nur Latin-1. Deutsche Umlaute sind darin, typografische Anführungszeichen
und Gedankenstriche nicht - ``latin1`` ersetzt sie, statt dass der Ausdruck an
einer Bemerkung scheitert.
"""

from __future__ import annotations

from fpdf import FPDF
from fpdf.enums import TableBordersLayout, TextEmphasis
from fpdf.fonts import FontFace

from .dienst import Bogen

_ERSATZ = {
    "\u201e": '"',
    "\u201c": '"',
    "\u201d": '"',
    "\u201a": "'",
    "\u2018": "'",
    "\u2019": "'",
    "\u2013": "-",
    "\u2014": "-",
    "\u2026": "...",
    "\u2022": "-",
    "\u00a0": " ",
}

_RAND = 30
_BREITE = 595.28 - 2 * _RAND
_FETT = FontFace(emphasis="BOLD")
_GRUPPE = FontFace(emphasis="BI")
# Bemerkungen stehen immer schlicht, auch in einer fetten Sektionszeile.
_BEMERKUNG = FontFace(emphasis=TextEmphasis.NONE, size_pt=6.5)


def latin1(text: str) -> str:
    for zeichen, ersatz in _ERSATZ.items():
        text = text.replace(zeichen, ersatz)
    return text.encode("latin-1", "replace").decode("latin-1")


class _Pdf(FPDF):
    def normalize_text(self, text: str) -> str:
        return super().normalize_text(latin1(text))


def _kopf(pdf: FPDF, bogen: Bogen) -> None:
    pdf.set_font("Helvetica", "B", 10)
    oben = pdf.get_y()
    for zeile in ("Abschlussprüfung Fachinformatiker", "Anwendungsentwicklung"):
        pdf.cell(300, 12, zeile, new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", "", 7)
    pdf.cell(300, 11, "Korrekturbogen Projektarbeit", new_x="LMARGIN", new_y="NEXT")
    pdf.cell(300, 9, "Prüfungsteil A - Sommer / Winter", new_x="LMARGIN", new_y="NEXT")
    unten = pdf.get_y()

    rechts = _RAND + _BREITE - 220
    pdf.set_xy(rechts, oben)
    pdf.set_font("Helvetica", "B", 7)
    pdf.cell(220, 9, "Vertraulich", new_x="LEFT", new_y="NEXT")
    pdf.set_font("Helvetica", "", 7)
    pdf.cell(220, 9, "Nur für den Prüfungsausschuss bestimmt!", new_x="LEFT", new_y="NEXT")
    pdf.set_y(pdf.get_y() + 10)
    pdf.set_x(rechts)
    pdf.cell(220, 9, f"Name des Korrektors:   {bogen.korrektor}", new_x="LEFT", new_y="NEXT")
    pdf.line(rechts, pdf.get_y(), rechts + 220, pdf.get_y())
    pdf.set_y(max(unten, pdf.get_y()) + 10)


def _kriterien(pdf: FPDF, bogen: Bogen) -> None:
    with pdf.table(
        col_widths=(_BREITE - 270, 40, 40, 190),
        text_align=("LEFT", "CENTER", "CENTER", "LEFT"),
        line_height=9,
        padding=2,
        first_row_as_headings=False,
        borders_layout=TableBordersLayout.ALL,
    ) as tabelle:
        reihe = tabelle.row()
        reihe.cell(bogen.name, style=_FETT)
        reihe.cell(bogen.ident, colspan=3, align="C")

        reihe = tabelle.row(style=_FETT)
        reihe.cell("Bewertungskriterien")
        reihe.cell("Maximale\nPunkte")
        reihe.cell("Erreichte\nPunkte")
        reihe.cell("Bemerkungen Prüfungsausschuss / Korrektur")

        tabelle.row(style=_FETT).cell("Projektdokumentation", colspan=4)

        for zeile in bogen.zeilen:
            stil = {"sektion": _FETT, "summe": _FETT, "gruppe": _GRUPPE}.get(zeile.art)
            reihe = tabelle.row(style=stil)
            einzug = "    " * zeile.einzug
            reihe.cell(einzug + zeile.text, align="R" if zeile.art == "summe" else None)
            reihe.cell(zeile.max)
            reihe.cell(zeile.ist)
            if zeile.bemerkung is not None:
                reihe.cell(zeile.bemerkung, rowspan=zeile.spanne, style=_BEMERKUNG)


def _uebertrag_und_unterschrift(pdf: FPDF, bogen: Bogen) -> None:
    # Übertrag, Notenschlüssel und Unterschriften bleiben beisammen.
    if pdf.get_y() + 190 > pdf.h - pdf.b_margin:
        pdf.add_page()
    oben = pdf.get_y() + 12
    pdf.set_y(oben)

    with pdf.table(
        width=230,
        col_widths=(162, 34, 34),
        text_align=("LEFT", "CENTER", "CENTER"),
        align="LEFT",
        line_height=9,
        padding=2,
        first_row_as_headings=False,
    ) as tabelle:
        reihe = tabelle.row(style=_FETT)
        for text in ("Punkteübertrag", "MAX", "IST"):
            reihe.cell(text)
        for posten in bogen.uebertrag:
            reihe = tabelle.row()
            for text in (posten.text, posten.max, posten.ist):
                reihe.cell(text)
        reihe = tabelle.row(style=_FETT)
        reihe.cell("SUMME:", align="R")
        reihe.cell("100")
        reihe.cell(bogen.summe)
    unten = pdf.get_y()

    pdf.set_y(oben)
    linker_rand = pdf.l_margin
    pdf.set_left_margin(_RAND + 270)
    with pdf.table(
        width=120,
        col_widths=(74, 46),
        text_align=("CENTER", "CENTER"),
        align="LEFT",
        line_height=9,
        padding=2,
        first_row_as_headings=False,
    ) as tabelle:
        reihe = tabelle.row(style=_FETT)
        reihe.cell("Punkte")
        reihe.cell("entspricht")
        for band in bogen.notenschluessel:
            reihe = tabelle.row()
            reihe.cell(f"{band.von} - {band.bis}")
            reihe.cell(str(band.note))
    pdf.set_left_margin(linker_rand)

    linie = max(unten, pdf.get_y()) + 34
    for index in range(4):
        x = _RAND + index * 140
        pdf.line(x, linie, x + 110, linie)
        pdf.set_xy(x, linie + 3)
        pdf.cell(110, 9, "Ort, Datum" if index == 0 else "Unterschrift")


def pdf_aus(bogen: Bogen, *, komprimiert: bool = True) -> bytes:
    pdf = _Pdf(unit="pt", format="A4")
    pdf.set_compression(komprimiert)
    pdf.set_margins(_RAND, 28, _RAND)
    pdf.set_auto_page_break(True, margin=24)
    pdf.set_title(latin1(f"Korrekturbogen {bogen.name}"))
    pdf.add_page()
    pdf.set_font("Helvetica", "", 7)
    pdf.set_draw_color(128, 128, 128)
    pdf.set_line_width(0.5)

    _kopf(pdf, bogen)
    _kriterien(pdf, bogen)
    _uebertrag_und_unterschrift(pdf, bogen)
    return bytes(pdf.output())
