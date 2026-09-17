"""HTTP-Schicht. Uebersetzt zwischen Anfrage und Fachlichkeit, sonst nichts.

Zur Reihenfolge der Routen: alle Pfade hier beginnen mit einem festen Wort
(`staffeln`, `spiele`, `befunde`, `import`, `zusammenfassung`). Es gibt keine
Route `/{id}` auf oberster Ebene - genau die waere der Fall, in dem FastAPI
`zusammenfassung` als UUID zu lesen versucht und mit 422 antwortet.
"""

from __future__ import annotations

import uuid
from dataclasses import asdict
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
    mannschaft_unsicher,
    sortiert,
    zusammenfassen,
)
from .modelle import Befund, Mannschaft, Vorgang
from .schemas import (
    BefundAusgabe,
    EinstellungenAusgabe,
    EinstellungenSetzen,
    EntscheidungSetzen,
    ImportAuftrag,
    ImportErgebnis,
    MannschaftAusgabe,
    MannschaftenSetzen,
    SpielAusgabe,
    SpielZeile,
    StaffelAendern,
    StaffelAnlegen,
    StaffelAusgabe,
    VorgangAendern,
    VorgangAnlegen,
    VorgangAusgabe,
    VorgangZeile,
    Zusammenfassung,
    ZustandSetzen,
)

router = APIRouter()


def _sicht(befund: Befund) -> BefundSicht:
    return BefundSicht(
        schwere=befund.schwere,
        entscheidung=befund.entscheidung,
        regel=befund.regel,
        titel=befund.titel,
        schluessel=str(befund.id),
    )


def _befund(befund: Befund, vorgang_id: uuid.UUID | None) -> BefundAusgabe:
    return BefundAusgabe(
        id=befund.id,
        regel=befund.regel,
        schwere=befund.schwere,  # type: ignore[arg-type]
        titel=befund.titel,
        text=befund.text,
        person=befund.person,
        mannschaft=befund.mannschaft,
        entscheidung=befund.entscheidung,  # type: ignore[arg-type]
        grund=befund.grund,
        weg=befund.weg,  # type: ignore[arg-type]
        vorgang_id=vorgang_id,
    )


def _mannschaft(m: Mannschaft) -> MannschaftAusgabe:
    return MannschaftAusgabe(
        id=m.id,
        name=m.name,
        verein=m.verein,
        nummer=m.nummer,
        ist_sg=m.ist_sg,
        hoehere=list(m.hoehere),
        bestaetigt=m.bestaetigt,
        unsicher=mannschaft_unsicher(m.ist_sg, m.bestaetigt),
    )


def _vorgang(v: Vorgang) -> VorgangAusgabe:
    return VorgangAusgabe.model_validate(v)


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
        vorgaenge_entwurf=await speicher.anzahl_entwuerfe(sitzung),
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
    # Ueber die Kennung und nicht ueber (regel, titel): zwei Spieler ohne Foto
    # in einem Spiel teilen sich beides.
    nach_schluessel = {str(b.id): b for b in bericht.befunde}
    zu_vorgang = await speicher.vorgaenge_zu_befunden(sitzung, [b.id for b in bericht.befunde])
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
            _befund(b := nach_schluessel[s.schluessel], zu_vorgang.get(b.id)) for s in geordnet
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
    gefunden = await speicher.entscheidung_setzen(sitzung, befund_id, daten.art, grund)
    vorhanden = await speicher.vorgang_zu_befund(sitzung, befund_id)
    return _befund(gefunden, vorhanden.id if vorhanden else None)


# ── Einstellungen ─────────────────────────────────────────────────────────


@router.get("/einstellungen", summary="Einstellungen dieser Installation")
async def einstellungen(sitzung: DbSitzung) -> EinstellungenAusgabe:
    werte = await speicher.einstellungen(sitzung)
    return EinstellungenAusgabe(**asdict(werte))


@router.put("/einstellungen", summary="Einstellungen ändern")
async def einstellungen_setzen(
    daten: EinstellungenSetzen, sitzung: DbSitzung
) -> EinstellungenAusgabe:
    """Nur die mitgeschickten Felder. Ausgelassene bleiben stehen."""
    werte = await speicher.einstellungen_setzen(sitzung, daten)
    return EinstellungenAusgabe(**asdict(werte))


# ── Mannschaften einer Staffel ────────────────────────────────────────────


@router.get("/staffeln/{staffel_id}/mannschaften", summary="Mannschaften einer Staffel")
async def mannschaften(staffel_id: uuid.UUID, sitzung: DbSitzung) -> list[MannschaftAusgabe]:
    return [_mannschaft(m) for m in await speicher.mannschaften(sitzung, staffel_id)]


@router.put("/staffeln/{staffel_id}/mannschaften", summary="Mannschaften einer Staffel setzen")
async def mannschaften_setzen(
    staffel_id: uuid.UUID, daten: MannschaftenSetzen, sitzung: DbSitzung
) -> list[MannschaftAusgabe]:
    """Die Meldung als Ganzes.

    Wer die hoeheren Mannschaften mitschickt, bestaetigt sie damit -- ein
    spaeteres Einspielen aus DFBnet ueberschreibt sie dann nicht mehr.
    """
    gesetzt = await speicher.mannschaften_setzen(sitzung, staffel_id, daten.mannschaften)
    return [_mannschaft(m) for m in gesetzt]


# ── Vorgänge: Mahnung und Sportgerichtsfall ───────────────────────────────


@router.get("/vorgaenge", summary="Alle Vorgänge")
async def vorgaenge(
    sitzung: DbSitzung,
    zustand: Annotated[str | None, Query(description="Nur dieser Zustand")] = None,
) -> list[VorgangZeile]:
    return [VorgangZeile.model_validate(v) for v in await speicher.vorgaenge(sitzung, zustand)]


@router.get("/vorgaenge/{vorgang_id}", summary="Ein Vorgang mit seinem Text")
async def vorgang(vorgang_id: uuid.UUID, sitzung: DbSitzung) -> VorgangAusgabe:
    return _vorgang(await speicher.vorgang(sitzung, vorgang_id))


@router.patch("/vorgaenge/{vorgang_id}", summary="Text oder Empfänger eines Vorgangs ändern")
async def vorgang_aendern(
    vorgang_id: uuid.UUID, daten: VorgangAendern, sitzung: DbSitzung
) -> VorgangAusgabe:
    felder = daten.model_dump(exclude_none=True)
    return _vorgang(await speicher.vorgang_aendern(sitzung, vorgang_id, felder))


@router.post("/vorgaenge/{vorgang_id}/zustand", summary="Vorgang weiterstellen")
async def vorgang_zustand(
    vorgang_id: uuid.UUID, daten: ZustandSetzen, sitzung: DbSitzung
) -> VorgangAusgabe:
    """'versandt' heisst: ein Mensch hat es abgeschickt.

    Dieses Programm verschickt nichts und hat auch keinen Weg dorthin. Der
    Zustand haelt fest, was ausserhalb passiert ist.
    """
    return _vorgang(await speicher.vorgang_zustand(sitzung, vorgang_id, daten.zustand))


@router.delete(
    "/vorgaenge/{vorgang_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Vorgang verwerfen",
)
async def vorgang_loeschen(vorgang_id: uuid.UUID, sitzung: DbSitzung) -> None:
    await speicher.vorgang_loeschen(sitzung, vorgang_id)


@router.post(
    "/befunde/{befund_id}/vorgang",
    status_code=status.HTTP_201_CREATED,
    summary="Aus einem Befund einen Entwurf machen",
)
async def vorgang_anlegen(
    befund_id: uuid.UUID, daten: VorgangAnlegen, sitzung: DbSitzung
) -> VorgangAusgabe:
    """Erzeugt den Entwurf aus der Vorlage -- und verschickt ihn nicht.

    Die Art ergibt sich aus dem Weg des Befundes; ein Befund ohne Weg bekommt
    keinen Vorgang. Der Text entsteht genau einmal: wer ihn danach umschreibt,
    behaelt seine Fassung.
    """
    return _vorgang(await speicher.vorgang_anlegen(sitzung, befund_id, daten))
