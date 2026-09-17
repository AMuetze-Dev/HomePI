"""HTTP-Schicht. Uebersetzt zwischen Anfrage und Fachlichkeit, sonst nichts.

Zur Reihenfolge der Routen: alle Pfade hier beginnen mit einem festen Wort
(`staffeln`, `spiele`, `befunde`, `import`, `zusammenfassung`). Es gibt keine
Route `/{id}` auf oberster Ebene - genau die waere der Fall, in dem FastAPI
`zusammenfassung` als UUID zu lesen versucht und mit 422 antwortet.
"""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Query, status
from homepi_core.deps import DbSitzung

from . import speicher
from .dienst import (
    BefundSicht,
    NochOffeneBefunde,
    SpielSicht,
    darf_abgehakt_werden,
    entscheidung_pruefen,
    sortiert,
    zusammenfassen,
)
from .schemas import (
    BefundAusgabe,
    EntscheidungSetzen,
    ImportAuftrag,
    ImportErgebnis,
    SpielAusgabe,
    SpielZeile,
    StaffelAendern,
    StaffelAnlegen,
    StaffelAusgabe,
    Zusammenfassung,
)

router = APIRouter()


def _sicht(befund: object) -> BefundSicht:
    return BefundSicht(
        schwere=befund.schwere,  # type: ignore[attr-defined]
        entscheidung=befund.entscheidung,  # type: ignore[attr-defined]
        regel=befund.regel,  # type: ignore[attr-defined]
        titel=befund.titel,  # type: ignore[attr-defined]
    )


# ── Warteschlange und Kachel ──────────────────────────────────────────────


@router.get("/", summary="Warteschlange der Spielberichte")
async def warteschlange(
    sitzung: DbSitzung,
    staffel_id: Annotated[uuid.UUID | None, Query(description="Nur diese Staffel")] = None,
) -> list[SpielZeile]:
    berichte = await speicher.spiele(sitzung, staffel_id)
    return [
        SpielZeile(
            id=b.id,
            dfbnet_id=b.dfbnet_id,
            datum=b.datum,
            heim=b.heim,
            gast=b.gast,
            ergebnis=b.ergebnis,
            abgehakt=b.abgehakt,
            offene_befunde=sum(1 for x in b.befunde if x.entscheidung == "offen"),
            kritische_befunde=sum(
                1 for x in b.befunde if x.schwere == "kritisch" and x.entscheidung == "offen"
            ),
        )
        for b in berichte
    ]


@router.get("/zusammenfassung", summary="Überblick für die Kachel")
async def uebersicht(sitzung: DbSitzung) -> Zusammenfassung:
    berichte = await speicher.spiele(sitzung)
    return zusammenfassen(
        (SpielSicht(abgehakt=b.abgehakt, befunde=[_sicht(x) for x in b.befunde]) for b in berichte),
        staffeln_aktiv=await speicher.anzahl_aktiver_staffeln(sitzung),
    )


# ── Staffeln ──────────────────────────────────────────────────────────────


@router.get("/staffeln", summary="Alle Staffeln")
async def staffeln(sitzung: DbSitzung) -> list[StaffelAusgabe]:
    return [StaffelAusgabe.model_validate(s) for s in await speicher.staffeln(sitzung)]


@router.post("/staffeln", status_code=status.HTTP_201_CREATED, summary="Staffel anlegen")
async def staffel_anlegen(daten: StaffelAnlegen, sitzung: DbSitzung) -> StaffelAusgabe:
    return StaffelAusgabe.model_validate(await speicher.staffel_anlegen(sitzung, daten))


@router.patch("/staffeln/{staffel_id}", summary="Staffel aktiv oder inaktiv setzen")
async def staffel_umschalten(
    staffel_id: uuid.UUID, daten: StaffelAendern, sitzung: DbSitzung
) -> StaffelAusgabe:
    gefunden = await speicher.staffel(sitzung, staffel_id)
    gefunden.aktiv = daten.aktiv
    return StaffelAusgabe.model_validate(gefunden)


@router.delete(
    "/staffeln/{staffel_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Staffel mit allen Spielberichten entfernen",
)
async def staffel_entfernen(staffel_id: uuid.UUID, sitzung: DbSitzung) -> None:
    await speicher.staffel_loeschen(sitzung, staffel_id)


# ── Einspielen ────────────────────────────────────────────────────────────


@router.post("/import", summary="Geprüfte Spielberichte einspielen")
async def einspielen(auftrag: ImportAuftrag, sitzung: DbSitzung) -> ImportErgebnis:
    """Der Weg, auf dem Daten hereinkommen.

    Die DFBnet-Automation laeuft als eigener Dienst (docs/06-artefakte.md) und
    schiebt hier herein. Dass sie das noch nicht tut, aendert an diesem
    Endpunkt nichts - er ist die Naht, an der sie spaeter ansetzt.
    """
    angelegt, aktualisiert, befunde = await speicher.einspielen(sitzung, auftrag)
    return ImportErgebnis(angelegt=angelegt, aktualisiert=aktualisiert, befunde=befunde)


# ── Ein Spielbericht ──────────────────────────────────────────────────────


@router.get("/spiele/{spiel_id}", summary="Ein Spielbericht mit seinen Befunden")
async def spiel(spiel_id: uuid.UUID, sitzung: DbSitzung) -> SpielAusgabe:
    bericht = await speicher.spiel(sitzung, spiel_id)
    geordnet = sortiert([_sicht(b) for b in bericht.befunde])
    # Die Reihenfolge kommt aus der Fachlichkeit, die Daten aus der Tabelle.
    nach_schluessel = {(b.regel, b.titel): b for b in bericht.befunde}
    return SpielAusgabe(
        id=bericht.id,
        staffel_id=bericht.staffel_id,
        dfbnet_id=bericht.dfbnet_id,
        datum=bericht.datum,
        heim=bericht.heim,
        gast=bericht.gast,
        ergebnis=bericht.ergebnis,
        abgehakt=bericht.abgehakt,
        abgehakt_am=bericht.abgehakt_am,
        befunde=[
            BefundAusgabe.model_validate(nach_schluessel[(s.regel, s.titel)]) for s in geordnet
        ],
    )


@router.post("/spiele/{spiel_id}/haken", summary="Spielbericht abhaken")
async def abhaken(spiel_id: uuid.UUID, sitzung: DbSitzung) -> SpielAusgabe:
    """Die eine Zusage des Artefakts: abgehakt wird erst, wenn zu jedem Befund
    eine Entscheidung vorliegt."""
    bericht = await speicher.spiel(sitzung, spiel_id)

    entscheidung = darf_abgehakt_werden([_sicht(b) for b in bericht.befunde])
    if not entscheidung.erlaubt:
        raise NochOffeneBefunde(
            entscheidung.grund, spiel_id=str(spiel_id), offen=entscheidung.offen
        )

    await speicher.haken_setzen(sitzung, spiel_id, True)
    return await spiel(spiel_id, sitzung)


@router.delete("/spiele/{spiel_id}/haken", summary="Haken wieder entfernen")
async def haken_entfernen(spiel_id: uuid.UUID, sitzung: DbSitzung) -> SpielAusgabe:
    await speicher.haken_setzen(sitzung, spiel_id, False)
    return await spiel(spiel_id, sitzung)


# ── Ein Befund ────────────────────────────────────────────────────────────


@router.post("/befunde/{befund_id}/entscheidung", summary="Befund entscheiden")
async def entscheiden(
    befund_id: uuid.UUID, daten: EntscheidungSetzen, sitzung: DbSitzung
) -> BefundAusgabe:
    grund = entscheidung_pruefen(daten.art, daten.grund)
    return BefundAusgabe.model_validate(
        await speicher.entscheidung_setzen(sitzung, befund_id, daten.art, grund)
    )
