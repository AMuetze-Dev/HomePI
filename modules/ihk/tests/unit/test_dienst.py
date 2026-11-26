"""Der Rechenkern - rein, ohne Datenbank, in Millisekunden.

Er ist aus dem ExamManager V2 portiert und wird gegen dieselben echten
Altprüfungen geprüft wie dort (``altfaelle.json``, ohne Namen). Weicht hier
eine Zahl ab, rechnet HomePI anders als die Vorlage ``TEMPLATE.xlsm``.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest

from homepi_ihk import dienst
from homepi_ihk.dienst import (
    Bewertung,
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
        Bewertung(), doku={"doku.1.1": 1}, praesi_skala={"praesi.1.1": 0.5}, fragen="Warum?"
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
