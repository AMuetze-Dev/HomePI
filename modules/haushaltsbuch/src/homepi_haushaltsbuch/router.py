"""HTTP-Schicht. Uebersetzt zwischen Anfrage und Fachlichkeit, sonst nichts.

Lesen darf jeder mit einem Recht auf diesem Artefakt, aendern nur der
Verwalter. Das ist der Grund, warum die Freundin das Flussbild ansehen kann,
ohne dass ihr versehentlich eine Miete verrutscht.
"""

from __future__ import annotations

import datetime as dt
import uuid
from typing import Annotated

from fastapi import APIRouter, Query, status
from homepi_core.auth import Rolle, erfordert
from homepi_core.deps import DbSitzung

from . import dienst, speicher
from .schemas import (
    Flussbild,
    KategorieAendern,
    KategorieAnlegen,
    KategorieAusgabe,
    KontoAendern,
    KontoAnlegen,
    KontoAusgabe,
    PersonAendern,
    PersonAnlegen,
    PersonAusgabe,
    PostenAendern,
    PostenAnlegen,
    PostenAusgabe,
    Uebersicht,
    Zusammenfassung,
)

router = APIRouter()

#: Ein Leser sieht alles und aendert nichts.
NUR_VERWALTER = [erfordert("haushaltsbuch", Rolle.VERWALTER)]

Monat = Annotated[int | None, Query(ge=1, le=12, description="Vorgabe: der laufende Monat")]
Jahr = Annotated[int | None, Query(ge=2000, le=2100)]

#: Die ueblichen Schubladen. Angeboten, nicht erzwungen - wer anders denkt,
#: loescht sie und legt eigene an.
GRUNDGERUEST: tuple[tuple[str, bool], ...] = (
    ("Wohnen", False),
    ("Essen", False),
    ("Versicherungen", False),
    ("Mobilität", False),
    ("Konsum", False),
    ("Sparen", True),
    ("Investments", True),
)


def _zeitraum(jahr: int | None, monat: int | None) -> tuple[int, int]:
    heute = dt.date.today()
    return jahr or heute.year, monat or heute.month


# ------------------------------------------------------------ Auswertung


@router.get("/", summary="Monatsplan: wer zahlt was")
async def uebersicht(sitzung: DbSitzung, jahr: Jahr = None, monat: Monat = None) -> Uebersicht:
    """Steht vor allen anderen Pfaden und ist der Einstieg des Artefakts."""
    gewaehlt_jahr, gewaehlt_monat = _zeitraum(jahr, monat)
    personen, konten, kategorien, posten = await speicher.sichten(sitzung)
    return dienst.monatsplan(
        personen, konten, kategorien, posten, jahr=gewaehlt_jahr, monat=gewaehlt_monat
    )


@router.get("/zusammenfassung", summary="Überblick für die Kachel")
async def zusammenfassung(sitzung: DbSitzung) -> Zusammenfassung:
    jahr, monat = _zeitraum(None, None)
    personen, konten, kategorien, posten = await speicher.sichten(sitzung)
    plan = dienst.monatsplan(personen, konten, kategorien, posten, jahr=jahr, monat=monat)

    return Zusammenfassung(
        konten=len(konten),
        posten=len([p for p in posten if p.aktiv]),
        einnahmen=dienst.geld(sum((b.einnahmen for b in plan.personen), dienst.NULL)),
        ausgaben=dienst.geld(sum((b.ausgaben_gesamt for b in plan.personen), dienst.NULL)),
        rest=dienst.geld(sum((b.rest for b in plan.personen), dienst.NULL)),
        ruecklagen_summe=plan.ruecklagen_summe,
        faellig_im_monat=len(plan.faellig),
    )


@router.get("/flussbild", summary="Woher das Geld kommt und wohin es geht")
async def flussbild(sitzung: DbSitzung) -> Flussbild:
    personen, konten, kategorien, posten = await speicher.sichten(sitzung)
    return dienst.flussbild(personen, konten, kategorien, posten)


# --------------------------------------------------------------- Personen


@router.get("/personen", summary="Alle Personen")
async def personen(sitzung: DbSitzung) -> list[PersonAusgabe]:
    return [PersonAusgabe.model_validate(p) for p in await speicher.personen(sitzung)]


@router.post(
    "/personen",
    status_code=status.HTTP_201_CREATED,
    summary="Person anlegen",
    dependencies=NUR_VERWALTER,
)
async def person_anlegen(daten: PersonAnlegen, sitzung: DbSitzung) -> PersonAusgabe:
    return PersonAusgabe.model_validate(await speicher.person_anlegen(sitzung, daten))


@router.patch("/personen/{person_id}", summary="Person ändern", dependencies=NUR_VERWALTER)
async def person_aendern(
    person_id: uuid.UUID, daten: PersonAendern, sitzung: DbSitzung
) -> PersonAusgabe:
    return PersonAusgabe.model_validate(await speicher.person_aendern(sitzung, person_id, daten))


@router.delete(
    "/personen/{person_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Person entfernen",
    dependencies=NUR_VERWALTER,
)
async def person_entfernen(person_id: uuid.UUID, sitzung: DbSitzung) -> None:
    await speicher.person_loeschen(sitzung, person_id)


# ----------------------------------------------------------------- Konten


@router.get("/konten", summary="Alle Konten")
async def konten(sitzung: DbSitzung) -> list[KontoAusgabe]:
    return [KontoAusgabe.model_validate(k) for k in await speicher.konten(sitzung)]


@router.post(
    "/konten",
    status_code=status.HTTP_201_CREATED,
    summary="Konto anlegen",
    dependencies=NUR_VERWALTER,
)
async def konto_anlegen(daten: KontoAnlegen, sitzung: DbSitzung) -> KontoAusgabe:
    return KontoAusgabe.model_validate(await speicher.konto_anlegen(sitzung, daten))


@router.patch("/konten/{konto_id}", summary="Konto ändern", dependencies=NUR_VERWALTER)
async def konto_aendern(
    konto_id: uuid.UUID, daten: KontoAendern, sitzung: DbSitzung
) -> KontoAusgabe:
    return KontoAusgabe.model_validate(await speicher.konto_aendern(sitzung, konto_id, daten))


@router.delete(
    "/konten/{konto_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Konto entfernen",
    dependencies=NUR_VERWALTER,
)
async def konto_entfernen(konto_id: uuid.UUID, sitzung: DbSitzung) -> None:
    await speicher.konto_loeschen(sitzung, konto_id)


# ------------------------------------------------------------ Kategorien


@router.get("/kategorien", summary="Alle Kategorien")
async def kategorien(sitzung: DbSitzung) -> list[KategorieAusgabe]:
    return [KategorieAusgabe.model_validate(k) for k in await speicher.kategorien(sitzung)]


@router.post(
    "/kategorien",
    status_code=status.HTTP_201_CREATED,
    summary="Kategorie anlegen",
    dependencies=NUR_VERWALTER,
)
async def kategorie_anlegen(daten: KategorieAnlegen, sitzung: DbSitzung) -> KategorieAusgabe:
    return KategorieAusgabe.model_validate(await speicher.kategorie_anlegen(sitzung, daten))


@router.post(
    "/kategorien/grundgeruest",
    summary="Die üblichen Kategorien anlegen",
    dependencies=NUR_VERWALTER,
)
async def grundgeruest(sitzung: DbSitzung) -> list[KategorieAusgabe]:
    """Der erste Schritt in einem leeren Haushaltsbuch.

    Legt nur an, was fehlt. Zweimal aufgerufen passiert beim zweiten Mal
    nichts - ein Knopf, der beim Draufdruecken Dubletten erzeugt, wird nie
    wieder gedrueckt.
    """
    vorhanden = {k.name for k in await speicher.kategorien(sitzung)}
    for rang, (name, spart) in enumerate(GRUNDGERUEST):
        if name in vorhanden:
            continue
        await speicher.kategorie_anlegen(
            sitzung, KategorieAnlegen(name=name, zaehlt_als_sparen=spart, reihenfolge=rang)
        )
    return [KategorieAusgabe.model_validate(k) for k in await speicher.kategorien(sitzung)]


@router.patch("/kategorien/{kategorie_id}", summary="Kategorie ändern", dependencies=NUR_VERWALTER)
async def kategorie_aendern(
    kategorie_id: uuid.UUID, daten: KategorieAendern, sitzung: DbSitzung
) -> KategorieAusgabe:
    return KategorieAusgabe.model_validate(
        await speicher.kategorie_aendern(sitzung, kategorie_id, daten)
    )


@router.delete(
    "/kategorien/{kategorie_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Kategorie entfernen",
    dependencies=NUR_VERWALTER,
)
async def kategorie_entfernen(kategorie_id: uuid.UUID, sitzung: DbSitzung) -> None:
    await speicher.kategorie_loeschen(sitzung, kategorie_id)


# ----------------------------------------------------------------- Posten


@router.get("/posten", summary="Alle Posten")
async def posten(sitzung: DbSitzung) -> list[PostenAusgabe]:
    return [PostenAusgabe.model_validate(p) for p in await speicher.posten_alle(sitzung)]


@router.post(
    "/posten",
    status_code=status.HTTP_201_CREATED,
    summary="Posten anlegen",
    dependencies=NUR_VERWALTER,
)
async def posten_anlegen(daten: PostenAnlegen, sitzung: DbSitzung) -> PostenAusgabe:
    return PostenAusgabe.model_validate(await speicher.posten_anlegen(sitzung, daten))


@router.get("/posten/{posten_id}", summary="Ein Posten")
async def posten_eines(posten_id: uuid.UUID, sitzung: DbSitzung) -> PostenAusgabe:
    return PostenAusgabe.model_validate(await speicher.posten_eines(sitzung, posten_id))


@router.patch("/posten/{posten_id}", summary="Posten ändern", dependencies=NUR_VERWALTER)
async def posten_aendern(
    posten_id: uuid.UUID, daten: PostenAendern, sitzung: DbSitzung
) -> PostenAusgabe:
    return PostenAusgabe.model_validate(await speicher.posten_aendern(sitzung, posten_id, daten))


@router.delete(
    "/posten/{posten_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Posten entfernen",
    dependencies=NUR_VERWALTER,
)
async def posten_entfernen(posten_id: uuid.UUID, sitzung: DbSitzung) -> None:
    await speicher.posten_loeschen(sitzung, posten_id)
