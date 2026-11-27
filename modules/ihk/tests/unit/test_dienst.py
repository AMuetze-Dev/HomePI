"""Der Rechenkern - rein, ohne Datenbank, in Millisekunden.

Er ist aus dem ExamManager V2 portiert und wird gegen dieselben echten
Altprüfungen geprüft wie dort (``altfaelle.json``, ohne Namen). Weicht hier
eine Zahl ab, rechnet HomePI anders als die Vorlage ``TEMPLATE.xlsm``.
"""

from __future__ import annotations

import json
import random
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest

from homepi_ihk import dienst
from homepi_ihk.dienst import (
    Bewertung,
    FgFrage,
    Mep,
    Teilnoten,
    Zeiten,
    aendere_bewertung,
    berechne_doku,
    berechne_gesamt,
    berechne_praesentation,
    bloecke,
    bogen_dateiname,
    korrekturbogen,
    mep_anwenden,
    note_fuer,
    notenbaender,
    pruefe_dokument,
    runde,
    zeit_schritt,
)
from homepi_ihk.katalog import KATALOG, NOTEN

ALTFAELLE: list[dict[str, Any]] = json.loads(
    (Path(__file__).parent / "altfaelle.json").read_text(encoding="utf-8")
)
MIT_DOKU = [f for f in ALTFAELLE if f["doku"]]
MIT_PRAESI = [f for f in ALTFAELLE if f["praesiTotal"] is not None]


# ── Katalog ──────────────────────────────────────────────────────────────────


def test_katalog_summiert_auf_100() -> None:
    assert sum(s.max for s in KATALOG.doku) == 100
    assert sum(s.max for s in KATALOG.praesentation) == 100


def test_notentabelle_hat_101_stufen_und_die_grenzfaelle() -> None:
    assert len(NOTEN.tabelle) == 101
    assert NOTEN.grenzfaelle == (91, 80, 66, 49, 29)
    assert note_fuer(100) == 1.0
    assert note_fuer(0) == 6.0
    assert note_fuer(None) is None


def test_maengel_zeile_ist_malus_und_zaehlt_nicht_gegen_das_maximum() -> None:
    umsetzung = next(s for s in KATALOG.doku if s.nr == "5")
    maengel = next(k for k in umsetzung.kinder if k.art == "malus")
    assert maengel.max == -2
    assert umsetzung.max == 20


def test_38_bewertbare_kriterien_in_der_dokumentation() -> None:
    assert len(KATALOG.doku_blaetter) == 38


def test_bloecke_folgen_den_verbundenen_zellen_der_vorlage() -> None:
    form = bloecke(KATALOG.doku[0])
    assert [b.id for b in form] == ["doku.1", "doku.1.1"]
    assert len(form[1].knoten) == 3

    konzept = next(s for s in KATALOG.doku if s.nr == "4")
    assert [b.id for b in bloecke(konzept)] == ["doku.4", "doku.4.1", "doku.4.2", "doku.4.3"]


def test_notenbaender_aus_der_tabelle() -> None:
    assert [(b.von, b.bis, b.note) for b in notenbaender()] == [
        (100, 92, 1),
        (91, 81, 2),
        (80, 67, 3),
        (66, 50, 4),
        (49, 30, 5),
        (29, 0, 6),
    ]


def test_runden_wie_excel_halb_weg_von_null() -> None:
    assert runde(2.5) == 3
    assert runde(-2.5) == -3
    assert runde(76.5) == 77
    assert runde(0.49) == 0


# ── Dokumentation ────────────────────────────────────────────────────────────


def test_es_gibt_ausgefuellte_altfaelle() -> None:
    assert len(MIT_DOKU) >= 4
    assert len(MIT_PRAESI) >= 1


@pytest.mark.parametrize("fall", MIT_DOKU, ids=lambda f: f["fall"])
def test_dokumentation_trifft_die_altfaelle(fall: dict[str, Any]) -> None:
    ergebnis = berechne_doku(fall["doku"])

    assert ergebnis.gesamt == fall["dokuTotal"]
    for sektion_id, erwartet in fall["dokuSections"].items():
        assert next(s for s in ergebnis.sektionen if s.id == sektion_id).wert == erwartet
    assert ergebnis.fehlend == []
    if fall["dokuNote"] is not None:
        assert ergebnis.note == fall["dokuNote"]


def test_dokumentation_ohne_gesamt_solange_eine_sektion_leer_ist() -> None:
    ergebnis = berechne_doku({"doku.1.1": 1})

    assert ergebnis.sektionen[0].wert == 1
    assert ergebnis.sektionen[0].vollstaendig is False
    assert ergebnis.sektionen[1].wert is None
    assert ergebnis.gesamt is None
    assert ergebnis.note is None
    assert len(ergebnis.fehlend) == 37


def test_grenzfall_wird_erkannt() -> None:
    voll: dict[str, int | None] = {b.id: b.max for b in KATALOG.doku_blaetter if b.art == "points"}
    voll["doku.5.5"] = 0
    # 100 - 9 = 91, ein Grenzfall der Vorlage
    abzug = 9
    for kennung, wert in list(voll.items()):
        weg = min(abzug, wert or 0)
        voll[kennung] = (wert or 0) - weg
        abzug -= weg
    ergebnis = berechne_doku(voll)
    assert ergebnis.gesamt == 91
    assert ergebnis.grenzfall is True


# ── Präsentation und Fachgespräch ────────────────────────────────────────────


@pytest.mark.parametrize("fall", MIT_PRAESI, ids=lambda f: f["fall"])
def test_praesentation_trifft_die_altfaelle(fall: dict[str, Any]) -> None:
    ergebnis = berechne_praesentation(fall["praesiScale"], fall["praesiScores"])

    assert ergebnis.gesamt == fall["praesiTotal"]
    if fall["praesiNote"] is not None:
        assert ergebnis.note == fall["praesiNote"]


def test_vorschlag_ist_max_mal_mittelwert_gerundet() -> None:
    # Aufbau und inhaltliche Struktur, max 10: 1 / 0,5 -> Mittelwert 0,75 -> 8
    ergebnis = berechne_praesentation({"praesi.1.1": 1, "praesi.1.2": 0.5}, {})
    assert ergebnis.sektionen[0].vorschlag == 8
    assert ergebnis.sektionen[0].wert is None
    assert "praesi.1" in ergebnis.fehlend


def test_manuelle_punktzahl_schlaegt_den_vorschlag() -> None:
    ergebnis = berechne_praesentation({"praesi.1.1": 1}, {"praesi.1": 7})
    assert ergebnis.sektionen[0].vorschlag == 10
    assert ergebnis.sektionen[0].wert == 7


# ── Gesamtergebnis ───────────────────────────────────────────────────────────

TEILNOTEN = Teilnoten(teil1=80, planen_softwareprodukt=70, algorithmen=60, wiso=90)


def test_mep_wichtet_schriftlich_doppelt() -> None:
    assert mep_anwenden(30, 40) == 33
    assert mep_anwenden(90, 40) == 73
    assert mep_anwenden(50, 50) == 50


def test_gesamt_nach_dem_schema_der_vorlage() -> None:
    ohne, mit = berechne_gesamt(TEILNOTEN, doku=65, praesentation=89)
    assert ohne.projekt == 77
    assert ohne.teil2 == 76
    assert ohne.gesamt == 77
    assert ohne.fehlend == []
    assert mit is None


def test_gesamt_mit_und_ohne_ergaenzungspruefung() -> None:
    teilnoten = Teilnoten(
        teil1=80,
        planen_softwareprodukt=70,
        algorithmen=60,
        wiso=90,
        mep=Mep(bereich="wiso", punkte=40),
    )
    ohne, mit = berechne_gesamt(teilnoten, doku=65, praesentation=89)
    assert ohne.gesamt == 77
    assert mit is not None
    wiso = next(b for b in mit.bereiche if b.id == "wiso")
    assert (wiso.schriftlich, wiso.muendlich, wiso.wert) == (90, 40, 73)
    assert mit.teil2 == 74
    assert mit.gesamt == 75


def test_kein_gesamt_solange_teilnoten_fehlen() -> None:
    teilnoten = Teilnoten(teil1=None, planen_softwareprodukt=70, algorithmen=60, wiso=None)
    ohne, _ = berechne_gesamt(teilnoten, doku=None, praesentation=89)
    assert ohne.gesamt is None
    assert ohne.projekt is None
    assert set(ohne.fehlend) == {"projekt", "wiso", "teil1"}


# ── Bewertung ändern ─────────────────────────────────────────────────────────


def test_punkte_setzen_und_wieder_loeschen() -> None:
    b = aendere_bewertung(Bewertung(), doku={"doku.1.1": 1})
    assert b.doku == {"doku.1.1": 1}

    b = aendere_bewertung(b, doku={"doku.1.1": None})
    assert b.doku == {}


def test_aenderung_laesst_das_uebrige_stehen() -> None:
    b = aendere_bewertung(Bewertung(), doku={"doku.1.1": 1}, notizen="leise")
    b = aendere_bewertung(b, doku={"doku.1.2": 1})
    assert b.doku == {"doku.1.1": 1, "doku.1.2": 1}
    assert b.notizen == "leise"


def test_unbekanntes_kriterium_wird_abgelehnt() -> None:
    with pytest.raises(dienst.KriteriumUnbekannt):
        aendere_bewertung(Bewertung(), doku={"doku.99": 1})


def test_gruppe_ist_nicht_bewertbar() -> None:
    with pytest.raises(dienst.KriteriumUnbekannt):
        aendere_bewertung(Bewertung(), doku={"doku.4.1": 1})


def test_punkte_ueber_dem_maximum_werden_abgelehnt() -> None:
    with pytest.raises(dienst.PunkteUnzulaessig, match="0 bis 1"):
        aendere_bewertung(Bewertung(), doku={"doku.1.1": 2})


def test_maengel_nur_von_minus_zwei_bis_null() -> None:
    assert aendere_bewertung(Bewertung(), doku={"doku.5.5": -2}).doku == {"doku.5.5": -2}
    with pytest.raises(dienst.PunkteUnzulaessig, match="-2 bis 0"):
        aendere_bewertung(Bewertung(), doku={"doku.5.5": 1})


def test_skala_nur_mit_den_fuenf_stufen() -> None:
    b = aendere_bewertung(Bewertung(), praesi_skala={"praesi.1.1": 0.75})
    assert b.praesi_skala == {"praesi.1.1": 0.75}
    with pytest.raises(dienst.PunkteUnzulaessig):
        aendere_bewertung(Bewertung(), praesi_skala={"praesi.1.1": 0.6})
    with pytest.raises(dienst.KriteriumUnbekannt):
        aendere_bewertung(Bewertung(), praesi_skala={"doku.1.1": 1})


def test_sektionspunkte_praesentation_bis_zum_maximum() -> None:
    b = aendere_bewertung(Bewertung(), praesi_punkte={"praesi.5": 45})
    assert b.praesi_punkte == {"praesi.5": 45}
    with pytest.raises(dienst.PunkteUnzulaessig):
        aendere_bewertung(Bewertung(), praesi_punkte={"praesi.1": 11})
    with pytest.raises(dienst.KriteriumUnbekannt):
        aendere_bewertung(Bewertung(), praesi_punkte={"praesi.1.1": 1})


def test_bemerkungen_nur_an_bloecken() -> None:
    b = aendere_bewertung(
        Bewertung(), doku_bemerkungen={"doku.4.1": "gut"}, praesi_bemerkungen={"praesi.2": "klar"}
    )
    assert b.doku_bemerkungen == {"doku.4.1": "gut"}
    assert b.praesi_bemerkungen == {"praesi.2": "klar"}
    # doku.4.1.1 liegt im Block doku.4.1 und hat keine eigene Bemerkung
    with pytest.raises(dienst.KriteriumUnbekannt):
        aendere_bewertung(Bewertung(), doku_bemerkungen={"doku.4.1.1": "x"})


def test_leere_bemerkung_entfernt_den_eintrag() -> None:
    b = aendere_bewertung(Bewertung(), doku_bemerkungen={"doku.1": "x"})
    assert aendere_bewertung(b, doku_bemerkungen={"doku.1": "  "}).doku_bemerkungen == {}


def test_bewertung_ueberlebt_den_weg_durch_json() -> None:
    b = aendere_bewertung(
        Bewertung(),
        doku={"doku.1.1": 1},
        praesi_skala={"praesi.1.1": 0.5},
        fg_fragen=[FgFrage("", "Warum?", 0.75, "q1")],
    )
    assert Bewertung.aus_dict(json.loads(json.dumps(b.als_dict()))) == b
    assert Bewertung.aus_dict({}) == Bewertung()


# ── Zeitmessung ──────────────────────────────────────────────────────────────

T0 = datetime(2026, 6, 18, 9, 0, tzinfo=UTC)


def test_zeitmessung_der_reihe_nach() -> None:
    z = zeit_schritt(Zeiten(), "praesentation_starten", T0)
    assert z.praesi_start == T0

    z = zeit_schritt(z, "fachgespraech_starten", T0 + timedelta(minutes=14))
    # Präsentation endet im selben Augenblick, in dem das Gespräch beginnt
    assert z.praesi_ende == z.fg_start == T0 + timedelta(minutes=14)

    z = zeit_schritt(z, "beenden", T0 + timedelta(minutes=31))
    assert z.fg_ende == T0 + timedelta(minutes=31)


@pytest.mark.parametrize(
    ("zeiten", "aktion"),
    [
        (Zeiten(), "fachgespraech_starten"),
        (Zeiten(), "beenden"),
        (Zeiten(praesi_start=T0), "praesentation_starten"),
        (Zeiten(praesi_start=T0), "beenden"),
        (Zeiten(praesi_start=T0, praesi_ende=T0, fg_start=T0, fg_ende=T0), "beenden"),
    ],
)
def test_unzulaessiger_zeitschritt(zeiten: Zeiten, aktion: str) -> None:
    with pytest.raises(dienst.ZeitschrittUnzulaessig):
        zeit_schritt(zeiten, aktion, T0)  # type: ignore[arg-type]


def test_zuruecksetzen_geht_immer() -> None:
    z = Zeiten(praesi_start=T0, praesi_ende=T0, fg_start=T0)
    assert zeit_schritt(z, "zuruecksetzen", T0) == Zeiten()


# ── Dokumente ────────────────────────────────────────────────────────────────


def test_pdf_wird_angenommen_und_der_name_bereinigt() -> None:
    assert pruefe_dokument("../ordner/Projekt Doku.pdf", b"%PDF-1.7\n...") == "Projekt Doku.pdf"


def test_name_ohne_endung_bekommt_pdf() -> None:
    assert pruefe_dokument("  ", b"%PDF-1.4") == "dokument.pdf"


def test_kein_pdf_wird_abgelehnt() -> None:
    with pytest.raises(dienst.KeinPdf):
        pruefe_dokument("bild.pdf", b"\x89PNG....")


def test_zu_grosses_dokument_wird_abgelehnt() -> None:
    with pytest.raises(dienst.DokumentZuGross):
        pruefe_dokument("a.pdf", b"%PDF" + b"0" * dienst.MAX_DOKUMENT_BYTES)


# ── Korrekturbogen ───────────────────────────────────────────────────────────


def test_bogen_dateiname() -> None:
    assert (
        bogen_dateiname("Müller, Anna-Lena", "2026-06-18")
        == "2026-06-18_Müller_Anna_Lena_Korrekturbogen.pdf"
    )


def test_korrekturbogen_spiegelt_die_vorlage() -> None:
    b = aendere_bewertung(
        Bewertung(),
        doku={"doku.1.1": 1, "doku.1.2": 1, "doku.4.1.1": 3},
        doku_bemerkungen={"doku.1": "Kopf", "doku.1.1": "Block", "doku.4.1": "Gruppe"},
        notizen="geheim",
    )
    bogen = korrekturbogen("Muster, Max", "123", "Korrektor K", b)

    assert bogen.name == "Muster, Max"
    kopf = next(z for z in bogen.zeilen if z.text == "1.  Form")
    assert (kopf.art, kopf.max, kopf.ist, kopf.bemerkung) == ("sektion", "5", "2", "Kopf")

    # Ein Block teilt sich eine Bemerkung über alle seine Zeilen
    erste = bogen.zeilen.index(next(z for z in bogen.zeilen if z.id == "doku.1.1"))
    assert bogen.zeilen[erste].bemerkung == "Block"
    assert bogen.zeilen[erste].spanne == 3
    assert bogen.zeilen[erste + 1].bemerkung is None

    gruppe = next(z for z in bogen.zeilen if z.id == "doku.4.1")
    assert (gruppe.art, gruppe.ist, gruppe.bemerkung) == ("gruppe", "3", "Gruppe")
    unter = next(z for z in bogen.zeilen if z.id == "doku.4.1.1")
    assert unter.einzug == 2

    assert bogen.zeilen[-1].art == "summe"
    assert bogen.zeilen[-1].ist == ""  # unvollständig: keine Summe
    assert [u.ist for u in bogen.uebertrag][:2] == ["2", ""]
    assert len(bogen.notenschluessel) == 6
    # Notizen gehören nie auf den Bogen
    assert all("geheim" not in (z.bemerkung or "") for z in bogen.zeilen)


# ── Notenrechner ─────────────────────────────────────────────────────────────


def test_notenstufe_nennt_note_und_was_zur_naechsten_fehlt() -> None:
    s = dienst.notenstufe(81)
    assert (s.punkte, s.note, s.ganze_note) == (81, 2.4, 2)
    # 92 ist die Untergrenze der 1
    assert (s.bessere_note, s.fehlen) == (1, 11)
    # 81 ist die Untergrenze der 2: ein Punkt weniger, und es ist eine 3
    assert s.puffer == 0


def test_notenstufe_erkennt_den_grenzfall() -> None:
    assert dienst.notenstufe(91).grenzfall is True
    assert dienst.notenstufe(91).fehlen == 1
    assert dienst.notenstufe(90).grenzfall is False


def test_notenstufe_an_den_enden() -> None:
    oben = dienst.notenstufe(100)
    assert (oben.ganze_note, oben.bessere_note, oben.fehlen) == (1, None, None)
    unten = dienst.notenstufe(0)
    assert (unten.ganze_note, unten.bessere_note, unten.fehlen) == (6, 5, 30)


def test_notenstufe_nur_von_0_bis_100() -> None:
    with pytest.raises(dienst.PunkteUnzulaessig):
        dienst.notenstufe(101)
    with pytest.raises(dienst.PunkteUnzulaessig):
        dienst.notenstufe(-1)


def test_fortschritt_zaehlt_bewertete_kriterien_und_sektionen() -> None:
    b = aendere_bewertung(
        Bewertung(), doku={"doku.1.1": 1, "doku.1.2": 1}, praesi_punkte={"praesi.1": 8}
    )
    f = dienst.fortschritt(b)
    assert (f.doku_bewertet, f.doku_kriterien) == (2, 38)
    assert (f.praesi_bewertet, f.praesi_sektionen) == (1, 5)


# ── Fachgespräch: gestellte Fragen statt fester Kriterien ────────────────────

FG = "praesi.5"


def _fg(ergebnis: dienst.TeilErgebnis) -> dienst.SektionErgebnis:
    return next(s for s in ergebnis.sektionen if s.id == FG)


def test_fachgespraech_hat_keine_festen_kriterien_sondern_fragen() -> None:
    sektion = next(s for s in KATALOG.praesentation if s.id == FG)
    assert sektion.fragen is True
    assert sektion.kinder == ()
    assert all(not b.id.startswith(FG + ".") for b in KATALOG.praesi_blaetter)


def test_vorschlag_im_fachgespraech_aus_dem_mittel_der_fragen() -> None:
    # 45 * (1 + 0,5 + 0,75) / 3 = 33,75 -> 34; unbewertete Fragen zählen nicht
    ergebnis = berechne_praesentation({}, {}, [1, 0.5, 0.75, None])
    assert _fg(ergebnis).vorschlag == 34
    assert _fg(ergebnis).vollstaendig is False


def test_fachgespraech_vollstaendig_wenn_jede_frage_und_die_punkte_da_sind() -> None:
    assert _fg(berechne_praesentation({}, {FG: 30}, [1, 0.5])).vollstaendig is True
    assert _fg(berechne_praesentation({}, {FG: 30}, [])).vollstaendig is False
    assert _fg(berechne_praesentation({}, {}, [])).vorschlag is None


def test_fragen_bekommen_eine_kennung_und_werden_ganz_ersetzt() -> None:
    nummern = iter(["a", "b"])
    b = aendere_bewertung(
        Bewertung(),
        fg_fragen=[FgFrage("", "  Was ist ein Index?  ", None, "q7"), FgFrage("", "Und REST?")],
        neue_id=lambda: next(nummern),
    )
    assert b.fg_fragen == (
        FgFrage("a", "Was ist ein Index?", None, "q7"),
        FgFrage("b", "Und REST?", None, None),
    )
    b = aendere_bewertung(b, fg_fragen=[FgFrage("b", "Und REST?", 0.5)])
    assert b.fg_fragen == (FgFrage("b", "Und REST?", 0.5, None),)
    assert aendere_bewertung(b, notizen="x").fg_fragen == b.fg_fragen


def test_frage_nur_mit_text_und_einer_stufe_der_skala() -> None:
    with pytest.raises(dienst.FrageUngueltig):
        aendere_bewertung(Bewertung(), fg_fragen=[FgFrage("", "   ")])
    with pytest.raises(dienst.FrageUngueltig):
        aendere_bewertung(Bewertung(), fg_fragen=[FgFrage("", "x" * 501)])
    with pytest.raises(dienst.PunkteUnzulaessig):
        aendere_bewertung(Bewertung(), fg_fragen=[FgFrage("", "Warum?", 0.6)])
    with pytest.raises(dienst.FrageUngueltig):
        aendere_bewertung(Bewertung(), fg_fragen=[FgFrage("", "F")] * 41)


def test_fachgespraech_kriterien_sind_nicht_mehr_bewertbar() -> None:
    with pytest.raises(dienst.KriteriumUnbekannt):
        aendere_bewertung(Bewertung(), praesi_skala={"praesi.5.1": 1})


def test_alte_bewertung_wird_beim_lesen_umgestellt() -> None:
    alt = {
        "praesi_skala": {"praesi.1.1": 1, "praesi.5.1": 0.5},
        "praesi_punkte": {"praesi.5": 30},
        "fragen": "Was ist ein Index?\n\n  Warum REST?  ",
    }
    b = Bewertung.aus_dict(alt)
    assert b.praesi_skala == {"praesi.1.1": 1}
    assert b.praesi_punkte == {"praesi.5": 30}
    assert [(f.text, f.wert) for f in b.fg_fragen] == [
        ("Was ist ein Index?", None),
        ("Warum REST?", None),
    ]
    assert len({f.id for f in b.fg_fragen}) == 2


def test_fortschritt_mit_fragen() -> None:
    b = aendere_bewertung(Bewertung(), praesi_punkte={FG: 30})
    assert dienst.fortschritt(b).praesi_bewertet == 1


# ── Fragensammlung ───────────────────────────────────────────────────────────


def test_frage_der_sammlung_wird_bereinigt() -> None:
    assert dienst.pruefe_frage("  Was ist ACID?  ", "  Datenbanken ") == (
        "Was ist ACID?",
        "Datenbanken",
    )
    with pytest.raises(dienst.FrageUngueltig):
        dienst.pruefe_frage("  ", "")
    with pytest.raises(dienst.FrageUngueltig):
        dienst.pruefe_frage("Was?", "x" * 61)


def test_stapel_eine_frage_je_zeile_ohne_doppelte() -> None:
    neu, doppelt = dienst.neue_fragen(
        ["Was ist ACID?"],
        "was ist  acid?\n\nWas ist REST?\n  Was ist REST?\nWarum Docker?\n",
    )
    assert neu == ["Was ist REST?", "Warum Docker?"]
    assert doppelt == 2


def test_stapel_lehnt_ueberlange_zeilen_ab() -> None:
    with pytest.raises(dienst.FrageUngueltig):
        dienst.neue_fragen([], "x" * 501)


@dataclass
class _F:
    id: str
    thema: str


SAMMLUNG = [_F("1", "Datenbanken"), _F("2", "Datenbanken"), _F("3", "Netzwerk")]


def test_ziehen_nach_thema_und_ohne_schon_gestellte() -> None:
    for saat in range(20):
        gezogen = dienst.ziehe_frage(
            SAMMLUNG, thema="Datenbanken", ohne={"1"}, zufall=random.Random(saat)
        )
        assert gezogen.id == "2"


def test_ziehen_ohne_thema_aus_allen() -> None:
    gezogen = {
        dienst.ziehe_frage(SAMMLUNG, thema=None, ohne=set(), zufall=random.Random(s)).id
        for s in range(50)
    }
    assert gezogen == {"1", "2", "3"}


def test_nichts_mehr_zu_ziehen() -> None:
    with pytest.raises(dienst.KeineFrageUebrig, match="Netzwerk"):
        dienst.ziehe_frage(SAMMLUNG, thema="Netzwerk", ohne={"3"}, zufall=random.Random(0))
    with pytest.raises(dienst.KeineFrageUebrig, match="noch keine"):
        dienst.ziehe_frage([], thema=None, ohne=set(), zufall=random.Random(0))
