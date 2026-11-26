"""HTTP-Schicht. Übersetzt zwischen Anfrage und Fachlichkeit, sonst nichts.

- summary= bei jedem Endpunkt: die generische Ansicht im Frontend zeigt ihn
- feste Pfade VOR parametrisierten, sonst liest FastAPI das Wort als UUID
- Fehler über eigene ServiceError-Klassen, nie HTTPException
- Rückgabetypen annotieren, sonst fehlt das OpenAPI-Schema
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Annotated, Any
from urllib.parse import quote

from fastapi import APIRouter, Query, Request, Response, status
from homepi_core.deps import DbSitzung
from sqlalchemy.ext.asyncio import AsyncSession

from . import dienst, speicher
from .bogen import pdf_aus
from .dienst import Bewertung, Mep, Teilnoten, Zeiten
from .katalog import KATALOG, NOTEN, Knoten, Sektion
from .modelle import Pruefling, Pruefungstag
from .schemas import (
    Auswertung,
    BereichAusgabe,
    BewertungAendern,
    BewertungAusgabe,
    BlockAusgabe,
    DokumentArt,
    DokumentAusgabe,
    GesamtErgebnisAusgabe,
    KatalogAusgabe,
    KnotenAusgabe,
    NotenbandAusgabe,
    PrueflingAendern,
    PrueflingAnlegen,
    PrueflingDetail,
    PrueflingKurz,
    SektionAusgabe,
    Status,
    TagAendern,
    TagAnlegen,
    TagAusgabe,
    TagDetail,
    TeilErgebnisAusgabe,
    TeilnotenEingabe,
    ZeitAktion,
    ZeitenAusgabe,
)

router = APIRouter()


# ── Übersetzung zwischen Tabelle und Rechenkern ──────────────────────────────


def _teilnoten(roh: dict[str, Any]) -> Teilnoten:
    mep = roh.get("mep")
    return Teilnoten(
        teil1=roh.get("teil1"),
        planen_softwareprodukt=roh.get("planen_softwareprodukt"),
        algorithmen=roh.get("algorithmen"),
        wiso=roh.get("wiso"),
        mep=Mep(bereich=mep["bereich"], punkte=mep["punkte"]) if mep else None,
    )


def _zeiten(p: Pruefling) -> Zeiten:
    return Zeiten(p.praesi_start, p.praesi_ende, p.fg_start, p.fg_ende)


def _tag(tag: Pruefungstag, anzahl: int = 0) -> TagAusgabe:
    return TagAusgabe(
        id=tag.id,
        datum=tag.datum,
        ort=tag.ort,
        korrektor=tag.korrektor,
        anzahl_prueflinge=anzahl,
    )


def _auswertung(bewertung: Bewertung, teilnoten: Teilnoten) -> Auswertung:
    doku = dienst.berechne_doku(bewertung.doku)
    praesi = dienst.berechne_praesentation(bewertung.praesi_skala, bewertung.praesi_punkte)
    ohne, mit = dienst.berechne_gesamt(teilnoten, doku.gesamt, praesi.gesamt)
    return Auswertung(
        doku=TeilErgebnisAusgabe.model_validate(doku),
        praesentation=TeilErgebnisAusgabe.model_validate(praesi),
        gesamt_ohne_mep=GesamtErgebnisAusgabe.model_validate(ohne),
        gesamt_mit_mep=GesamtErgebnisAusgabe.model_validate(mit) if mit else None,
    )


async def _detail(sitzung: AsyncSession, p: Pruefling) -> PrueflingDetail:
    tag = await speicher.tag(sitzung, p.tag_id)
    anzahl = await speicher.anzahl_prueflinge(sitzung, p.tag_id)
    bewertung = Bewertung.aus_dict(p.bewertung)
    teilnoten = _teilnoten(p.teilnoten)
    return PrueflingDetail(
        id=p.id,
        tag=_tag(tag, anzahl),
        reihenfolge=p.reihenfolge,
        name=p.name,
        ident=p.ident,
        korrekturart=p.korrekturart,  # type: ignore[arg-type]
        status=Status(**p.status),
        bewertung=BewertungAusgabe.model_validate(bewertung),
        teilnoten=TeilnotenEingabe.model_validate(teilnoten),
        zeiten=ZeitenAusgabe.model_validate(_zeiten(p)),
        dokumente=[
            DokumentAusgabe.model_validate(d) for d in await speicher.dokumente_von(sitzung, p.id)
        ],
        auswertung=_auswertung(bewertung, teilnoten),
        jetzt=datetime.now(UTC),
    )


def _kurz(p: Pruefling) -> PrueflingKurz:
    bewertung = Bewertung.aus_dict(p.bewertung)
    doku = dienst.berechne_doku(bewertung.doku)
    praesi = dienst.berechne_praesentation(bewertung.praesi_skala, bewertung.praesi_punkte)
    return PrueflingKurz(
        id=p.id,
        reihenfolge=p.reihenfolge,
        name=p.name,
        ident=p.ident,
        korrekturart=p.korrekturart,  # type: ignore[arg-type]
        status=Status(**p.status),
        doku_punkte=doku.gesamt,
        doku_note=doku.note,
        praesi_punkte=praesi.gesamt,
        praesi_note=praesi.note,
    )


def _knoten(k: Knoten) -> KnotenAusgabe:
    return KnotenAusgabe(
        id=k.id,
        label=k.label,
        art=k.art,
        max=k.max,
        hinweis=k.hinweis,
        kinder=[_knoten(c) for c in k.kinder],
    )


def _sektion(s: Sektion) -> SektionAusgabe:
    return SektionAusgabe(
        id=s.id,
        nr=s.nr,
        label=s.label,
        max=s.max,
        kinder=[_knoten(k) for k in s.kinder],
        bloecke=[BlockAusgabe(id=b.id, knoten=[k.id for k in b.knoten]) for b in dienst.bloecke(s)],
    )


def _pdf(daten: bytes, dateiname: str, art: str) -> Response:
    # filename* für Umlaute (RFC 6266), filename als ASCII-Rückfall.
    ascii_name = dateiname.encode("ascii", "replace").decode().replace("?", "_").replace('"', "")
    return Response(
        content=daten,
        media_type="application/pdf",
        headers={
            "Content-Disposition": (
                f"{art}; filename=\"{ascii_name}\"; filename*=UTF-8''{quote(dateiname)}"
            )
        },
    )


# ── Übersicht und Katalog ────────────────────────────────────────────────────


@router.get("/", summary="Prüfungstage")
async def uebersicht(sitzung: DbSitzung) -> list[TagAusgabe]:
    return [_tag(t, n) for t, n in await speicher.tage_mit_anzahl(sitzung)]


@router.get("/katalog", summary="Kriterienkatalog und Notenschlüssel")
async def katalog() -> KatalogAusgabe:
    g = KATALOG.gesamt
    return KatalogAusgabe(
        doku=[_sektion(s) for s in KATALOG.doku],
        praesentation=[_sektion(s) for s in KATALOG.praesentation],
        skala=list(NOTEN.skala),
        korrekturarten=list(NOTEN.korrekturarten),  # type: ignore[arg-type]
        notenbaender=[NotenbandAusgabe.model_validate(b) for b in dienst.notenbaender()],
        teil1_label=g.teil1_label,
        bereiche=[BereichAusgabe(id=b.id, label=b.label) for b in g.bereiche],  # type: ignore[arg-type]
        projekt_label=g.projekt_label,
        praesi_grenze_min=KATALOG.praesi_grenze_min,
        gesamt_grenze_min=KATALOG.gesamt_grenze_min,
    )


# ── Prüfungstage ─────────────────────────────────────────────────────────────


@router.post("/tage", status_code=status.HTTP_201_CREATED, summary="Prüfungstag anlegen")
async def tag_anlegen(daten: TagAnlegen, sitzung: DbSitzung) -> TagAusgabe:
    return _tag(await speicher.tag_anlegen(sitzung, daten.model_dump()))


@router.get("/tage/{tag_id}", summary="Prüfungstag mit Prüflingen")
async def tag_lesen(tag_id: uuid.UUID, sitzung: DbSitzung) -> TagDetail:
    tag = await speicher.tag(sitzung, tag_id)
    prueflinge = await speicher.prueflinge_von(sitzung, tag_id)
    return TagDetail(tag=_tag(tag, len(prueflinge)), prueflinge=[_kurz(p) for p in prueflinge])


@router.patch("/tage/{tag_id}", summary="Prüfungstag ändern")
async def tag_aendern(tag_id: uuid.UUID, daten: TagAendern, sitzung: DbSitzung) -> TagAusgabe:
    tag = await speicher.tag(sitzung, tag_id)
    for feld, wert in daten.model_dump(exclude_none=True).items():
        setattr(tag, feld, wert)
    await speicher.speichern(sitzung, tag)
    return _tag(tag, await speicher.anzahl_prueflinge(sitzung, tag_id))


@router.delete(
    "/tage/{tag_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Prüfungstag mit allen Prüflingen entfernen",
)
async def tag_entfernen(tag_id: uuid.UUID, sitzung: DbSitzung) -> None:
    await speicher.tag_loeschen(sitzung, tag_id)


@router.post(
    "/tage/{tag_id}/prueflinge",
    status_code=status.HTTP_201_CREATED,
    summary="Prüfling anlegen",
)
async def pruefling_anlegen(
    tag_id: uuid.UUID, daten: PrueflingAnlegen, sitzung: DbSitzung
) -> PrueflingDetail:
    await speicher.tag(sitzung, tag_id)
    p = await speicher.pruefling_anlegen(sitzung, tag_id, daten.name)
    return await _detail(sitzung, p)


# ── Prüflinge ────────────────────────────────────────────────────────────────


@router.get("/prueflinge/{pruefling_id}", summary="Prüfling mit Bewertung und Auswertung")
async def pruefling_lesen(pruefling_id: uuid.UUID, sitzung: DbSitzung) -> PrueflingDetail:
    return await _detail(sitzung, await speicher.pruefling(sitzung, pruefling_id))


@router.patch("/prueflinge/{pruefling_id}", summary="Stammdaten und Status ändern")
async def pruefling_aendern(
    pruefling_id: uuid.UUID, daten: PrueflingAendern, sitzung: DbSitzung
) -> PrueflingDetail:
    p = await speicher.pruefling(sitzung, pruefling_id)
    felder = daten.model_dump(exclude_none=True, exclude={"status"})
    for feld, wert in felder.items():
        setattr(p, feld, wert)
    if daten.status is not None:
        p.status = {**p.status, **daten.status.model_dump(exclude_none=True)}
    await speicher.speichern(sitzung, p)
    return await _detail(sitzung, p)


@router.delete(
    "/prueflinge/{pruefling_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Prüfling mit Bewertung und Dokumenten entfernen",
)
async def pruefling_entfernen(pruefling_id: uuid.UUID, sitzung: DbSitzung) -> None:
    await speicher.pruefling_loeschen(sitzung, pruefling_id)


@router.patch("/prueflinge/{pruefling_id}/bewertung", summary="Bewertung ändern")
async def bewertung_aendern(
    pruefling_id: uuid.UUID, daten: BewertungAendern, sitzung: DbSitzung
) -> PrueflingDetail:
    p = await speicher.pruefling(sitzung, pruefling_id)
    neu = dienst.aendere_bewertung(Bewertung.aus_dict(p.bewertung), **daten.model_dump())
    p.bewertung = neu.als_dict()
    await speicher.speichern(sitzung, p)
    return await _detail(sitzung, p)


@router.put("/prueflinge/{pruefling_id}/teilnoten", summary="Teilnoten setzen")
async def teilnoten_setzen(
    pruefling_id: uuid.UUID, daten: TeilnotenEingabe, sitzung: DbSitzung
) -> PrueflingDetail:
    p = await speicher.pruefling(sitzung, pruefling_id)
    p.teilnoten = daten.model_dump()
    await speicher.speichern(sitzung, p)
    return await _detail(sitzung, p)


@router.post("/prueflinge/{pruefling_id}/zeit", summary="Zeitmessung weiterschalten")
async def zeit(pruefling_id: uuid.UUID, daten: ZeitAktion, sitzung: DbSitzung) -> PrueflingDetail:
    p = await speicher.pruefling(sitzung, pruefling_id)
    neu = dienst.zeit_schritt(_zeiten(p), daten.aktion, datetime.now(UTC))
    p.praesi_start, p.praesi_ende = neu.praesi_start, neu.praesi_ende
    p.fg_start, p.fg_ende = neu.fg_start, neu.fg_ende
    await speicher.speichern(sitzung, p)
    return await _detail(sitzung, p)


@router.get("/prueflinge/{pruefling_id}/korrekturbogen", summary="Korrekturbogen als PDF")
async def korrekturbogen(pruefling_id: uuid.UUID, sitzung: DbSitzung) -> Response:
    p = await speicher.pruefling(sitzung, pruefling_id)
    tag = await speicher.tag(sitzung, p.tag_id)
    bogen = dienst.korrekturbogen(p.name, p.ident, tag.korrektor, Bewertung.aus_dict(p.bewertung))
    name = dienst.bogen_dateiname(p.name, tag.datum.isoformat())
    return _pdf(pdf_aus(bogen), name, "attachment")


# ── Dokumente ────────────────────────────────────────────────────────────────


@router.post(
    "/prueflinge/{pruefling_id}/dokumente",
    status_code=status.HTTP_201_CREATED,
    summary="Dokumentation als PDF hochladen (Rohdaten im Körper)",
)
async def dokument_hochladen(
    pruefling_id: uuid.UUID,
    art: Annotated[DokumentArt, Query()],
    dateiname: Annotated[str, Query(max_length=300)],
    anfrage: Request,
    sitzung: DbSitzung,
) -> DokumentAusgabe:
    await speicher.pruefling(sitzung, pruefling_id)
    daten = await anfrage.body()
    name = dienst.pruefe_dokument(dateiname, daten)
    dokument = await speicher.dokument_anlegen(sitzung, pruefling_id, art, name, daten)
    return DokumentAusgabe.model_validate(dokument)


@router.get("/prueflinge/{pruefling_id}/dokumente/{dokument_id}", summary="Dokument als PDF")
async def dokument_lesen(
    pruefling_id: uuid.UUID, dokument_id: uuid.UUID, sitzung: DbSitzung
) -> Response:
    dokument = await speicher.dokument_mit_daten(sitzung, pruefling_id, dokument_id)
    return _pdf(dokument.daten, dokument.dateiname, "inline")


@router.delete(
    "/prueflinge/{pruefling_id}/dokumente/{dokument_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Dokument entfernen",
)
async def dokument_entfernen(
    pruefling_id: uuid.UUID, dokument_id: uuid.UUID, sitzung: DbSitzung
) -> None:
    await speicher.dokument_loeschen(sitzung, pruefling_id, dokument_id)
