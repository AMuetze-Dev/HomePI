"""HTTP-Schicht. Uebersetzt zwischen Anfrage und Fachlichkeit, sonst nichts."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, status
from homepi_core.deps import DbSitzung

from . import speicher
from .dienst import GeraetSicht, NichtSchaltbar, darf_geschaltet_werden, zusammenfassen
from .schemas import GeraetAendern, GeraetAnlegen, GeraetAusgabe, Zusammenfassung

router = APIRouter()


@router.get("/", summary="Alle Geräte")
async def liste(sitzung: DbSitzung) -> list[GeraetAusgabe]:
    return [GeraetAusgabe.model_validate(g) for g in await speicher.alle(sitzung)]


@router.get("/zusammenfassung", summary="Überblick für die Kachel")
async def uebersicht(sitzung: DbSitzung) -> Zusammenfassung:
    """Steht bewusst VOR /{geraet_id}: sonst versucht FastAPI, das Wort
    'zusammenfassung' als UUID zu lesen, und antwortet mit 422."""
    geraete = await speicher.alle(sitzung)
    return zusammenfassen(
        GeraetSicht(raum=g.raum, zustand=g.zustand, eingeschaltet=g.eingeschaltet) for g in geraete
    )


@router.get("/{geraet_id}", summary="Ein Gerät")
async def einzeln(geraet_id: uuid.UUID, sitzung: DbSitzung) -> GeraetAusgabe:
    return GeraetAusgabe.model_validate(await speicher.eines(sitzung, geraet_id))


@router.post("/", status_code=status.HTTP_201_CREATED, summary="Gerät anlegen")
async def anlegen(daten: GeraetAnlegen, sitzung: DbSitzung) -> GeraetAusgabe:
    return GeraetAusgabe.model_validate(await speicher.anlegen(sitzung, daten))


@router.patch("/{geraet_id}", summary="Gerät ein- oder ausschalten")
async def schalten(geraet_id: uuid.UUID, daten: GeraetAendern, sitzung: DbSitzung) -> GeraetAusgabe:
    geraet = await speicher.eines(sitzung, geraet_id)

    entscheidung = darf_geschaltet_werden(geraet.zustand)
    if not entscheidung.erlaubt:
        raise NichtSchaltbar(entscheidung.grund, geraet_id=str(geraet_id))

    geraet.eingeschaltet = daten.eingeschaltet
    await sitzung.flush()
    return GeraetAusgabe.model_validate(geraet)


@router.delete("/{geraet_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Gerät entfernen")
async def entfernen(geraet_id: uuid.UUID, sitzung: DbSitzung) -> None:
    await speicher.loeschen(sitzung, geraet_id)
