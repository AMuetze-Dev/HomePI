"""HTTP-Schicht. Uebersetzt zwischen Anfrage und Fachlichkeit, sonst nichts.

Zwei Arten von Aufrufern, zwei Router:

- ``eltern``: alles ausser /geraet. Lesen braucht ``leser``, Aendern
  ``nutzer``, Geraete verwalten ``verwalter``.
- ``geraet_router``: /geraet/... fuer den ESP32, angemeldet per Token.

Das Modul steht auf ``Zugang.SELBST``, weil das Geraet kein Konto hat. Die
Pruefung haengt deshalb an den beiden Routern statt am Modul -
``tests/unit/test_anmeldung.py`` verlangt sie an jeder Route.
"""

from __future__ import annotations

import datetime as dt
import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request, Response, status
from homepi_core.auth import Rolle, erfordert
from homepi_core.deps import DbSitzung
from sqlalchemy.ext.asyncio import AsyncSession

from . import dienst, speicher
from .geraet import AktuellesGeraet, aktuelles_geraet
from .modelle import Geraet
from .schemas import (
    AufnahmeAendern,
    AufnahmeArt,
    AufnahmeAusgabe,
    Einstellungen,
    EreignisAusgabe,
    EreignisseAntwort,
    EreignisseEingang,
    FigurAusgabe,
    FigurEingabe,
    GeraetAnlegen,
    GeraetAusgabe,
    GeraetMitToken,
    Manifest,
    PhaseAusgabe,
    SpielAusgabe,
    TagebuchAusgabe,
    TagebuchEingabe,
    Uebersicht,
    UnbekannteFigur,
)
from .spiele import PHASEN, SPIELE

ID = "kinderzimmer"
SCHREIBEN = [erfordert(ID, Rolle.NUTZER)]
VERWALTEN = [erfordert(ID, Rolle.VERWALTER)]

#: So weit zurueck sucht "Figur anlernen" nach aufgelegten, unbekannten Tags.
ANLERNFENSTER = dt.timedelta(days=7)

#: Groesser wird keine erlaubte Aufnahme: 30 s * 22050 Hz * 2 Byte + Kopf.
HOECHSTE_UPLOADGROESSE = 1_400_000

router = APIRouter()
eltern = APIRouter(dependencies=[erfordert(ID, Rolle.LESER)])
geraet_router = APIRouter(prefix="/geraet", dependencies=[Depends(aktuelles_geraet)])


async def _manifest(sitzung: AsyncSession) -> Manifest:
    return dienst.baue_manifest(
        await speicher.einstellungen(sitzung),
        await speicher.figuren(sitzung),
        await speicher.aufnahmen(sitzung),
    )


def _geraet_ausgabe(geraet: Geraet, stand: str) -> GeraetAusgabe:
    return GeraetAusgabe(
        id=geraet.id,
        name=geraet.name,
        zuletzt_gesehen=geraet.zuletzt_gesehen,
        firmware=geraet.firmware,
        stand_aktuell=dienst.stand_aktuell(geraet.stand, stand),
        angelegt=geraet.angelegt,
    )


# --- Uebersicht und Spiele -----------------------------------------------------


@eltern.get("/", summary="Spiele, Phasen und Stand")
async def uebersicht(sitzung: DbSitzung) -> Uebersicht:
    einstellungen = await speicher.einstellungen(sitzung)
    aktiv = set(einstellungen.spiele_aktiv)
    return Uebersicht(
        phasen=[PhaseAusgabe(nummer=p.nummer, titel=p.titel, alter=p.alter) for p in PHASEN],
        spiele=[
            SpielAusgabe(
                id=s.id,
                nummer=s.nummer,
                phase=s.phase,
                titel=s.titel,
                alter=s.alter,
                ablauf=s.ablauf,
                foerdert=s.foerdert,
                warum=s.warum,
                bereit=s.bereit,
                aktiv=s.id in aktiv,
            )
            for s in SPIELE
        ],
        stand=(await _manifest(sitzung)).stand,
        zahlen=await speicher.zahlen(sitzung),
    )


@eltern.get("/einstellungen", summary="Einstellungen des Geräts")
async def einstellungen_lesen(sitzung: DbSitzung) -> Einstellungen:
    return await speicher.einstellungen(sitzung)


@eltern.put("/einstellungen", summary="Einstellungen ändern", dependencies=SCHREIBEN)
async def einstellungen_aendern(werte: Einstellungen, sitzung: DbSitzung) -> Einstellungen:
    dienst.pruefe_spielauswahl(werte)
    vorhanden = {a.id for a in await speicher.aufnahmen(sitzung)}
    dienst.pruefe_aufnahmen_vorhanden((k.klang for k in werte.knoepfe), vorhanden)
    await speicher.speichere_einstellungen(sitzung, werte)
    return werte


# --- Aufnahmen -----------------------------------------------------------------


@eltern.get("/aufnahmen", summary="Alle Aufnahmen")
async def aufnahmen(sitzung: DbSitzung) -> list[AufnahmeAusgabe]:
    return await speicher.aufnahmen(sitzung)


@eltern.post(
    "/aufnahmen",
    status_code=status.HTTP_201_CREATED,
    summary="Aufnahme hochladen (WAV, mono, 16 Bit, 22050 Hz)",
    dependencies=SCHREIBEN,
)
async def aufnahme_hochladen(
    request: Request,
    sitzung: DbSitzung,
    titel: Annotated[str, Query(min_length=1, max_length=80)],
    art: AufnahmeArt = "stimme",
) -> AufnahmeAusgabe:
    daten = await request.body()
    if len(daten) > HOECHSTE_UPLOADGROESSE:
        raise dienst.AufnahmeUngueltig("Die Datei ist zu groß für eine Aufnahme.")
    info = dienst.pruefe_wav(daten)
    sauber = AufnahmeAendern(titel=titel, art=art)
    return await speicher.lege_aufnahme_an(sitzung, sauber.titel, sauber.art, daten, info)


@eltern.get(
    "/aufnahmen/{aufnahme_id}/datei",
    summary="Aufnahme anhören",
    response_class=Response,
)
async def aufnahme_datei(aufnahme_id: uuid.UUID, sitzung: DbSitzung) -> Response:
    daten, sha = await speicher.aufnahme_daten(sitzung, aufnahme_id)
    return Response(content=daten, media_type="audio/wav", headers={"ETag": f'"{sha}"'})


@eltern.put("/aufnahmen/{aufnahme_id}", summary="Aufnahme umbenennen", dependencies=SCHREIBEN)
async def aufnahme_aendern(
    aufnahme_id: uuid.UUID, werte: AufnahmeAendern, sitzung: DbSitzung
) -> AufnahmeAusgabe:
    return await speicher.aendere_aufnahme(sitzung, aufnahme_id, werte)


@eltern.delete(
    "/aufnahmen/{aufnahme_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Aufnahme löschen",
    dependencies=SCHREIBEN,
)
async def aufnahme_loeschen(aufnahme_id: uuid.UUID, sitzung: DbSitzung) -> None:
    knoepfe = (await speicher.einstellungen(sitzung)).knoepfe
    dienst.pruefe_loeschbar(aufnahme_id, await speicher.figuren(sitzung), knoepfe)
    await speicher.loesche_aufnahme(sitzung, aufnahme_id)


# --- Figuren -------------------------------------------------------------------


@eltern.get("/figuren", summary="Alle Figuren")
async def figuren(sitzung: DbSitzung) -> list[FigurAusgabe]:
    return await speicher.figuren(sitzung)


@eltern.get("/figuren/unbekannt", summary="Aufgelegte Tags, die noch keine Figur sind")
async def figuren_unbekannt(sitzung: DbSitzung) -> list[UnbekannteFigur]:
    seit = dt.datetime.now(dt.UTC) - ANLERNFENSTER
    bekannte = {f.uid for f in await speicher.figuren(sitzung)}
    gesehen = await speicher.gesehene_uids(sitzung, seit)
    return [
        UnbekannteFigur(uid=uid, zuletzt=wann)
        for uid, wann in dienst.unbekannte_figuren(gesehen, bekannte)
    ]


async def _pruefe_figur(werte: FigurEingabe, sitzung: AsyncSession) -> None:
    vorhanden = {a.id for a in await speicher.aufnahmen(sitzung)}
    dienst.pruefe_aufnahmen_vorhanden((werte.stimme, werte.klang), vorhanden)


@eltern.post(
    "/figuren",
    status_code=status.HTTP_201_CREATED,
    summary="Figur anlegen",
    dependencies=SCHREIBEN,
)
async def figur_anlegen(werte: FigurEingabe, sitzung: DbSitzung) -> FigurAusgabe:
    await _pruefe_figur(werte, sitzung)
    return await speicher.lege_figur_an(sitzung, werte)


@eltern.put("/figuren/{figur_id}", summary="Figur ändern", dependencies=SCHREIBEN)
async def figur_aendern(
    figur_id: uuid.UUID, werte: FigurEingabe, sitzung: DbSitzung
) -> FigurAusgabe:
    await _pruefe_figur(werte, sitzung)
    return await speicher.aendere_figur(sitzung, figur_id, werte)


@eltern.delete(
    "/figuren/{figur_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Figur löschen",
    dependencies=SCHREIBEN,
)
async def figur_loeschen(figur_id: uuid.UUID, sitzung: DbSitzung) -> None:
    await speicher.loesche_figur(sitzung, figur_id)


# --- Geraete -------------------------------------------------------------------


@eltern.get("/geraete", summary="Angemeldete Geräte")
async def geraete(sitzung: DbSitzung) -> list[GeraetAusgabe]:
    stand = (await _manifest(sitzung)).stand
    return [_geraet_ausgabe(g, stand) for g in await speicher.geraete(sitzung)]


def _mit_token(geraet: Geraet, stand: str, token: str) -> GeraetMitToken:
    return GeraetMitToken(**_geraet_ausgabe(geraet, stand).model_dump(), token=token)


@eltern.post(
    "/geraete",
    status_code=status.HTTP_201_CREATED,
    summary="Gerät anlegen (das Token steht nur in dieser Antwort)",
    dependencies=VERWALTEN,
)
async def geraet_anlegen(werte: GeraetAnlegen, sitzung: DbSitzung) -> GeraetMitToken:
    token, hashwert = dienst.neues_token()
    geraet = await speicher.lege_geraet_an(sitzung, werte.name, hashwert)
    return _mit_token(geraet, (await _manifest(sitzung)).stand, token)


@eltern.post(
    "/geraete/{geraet_id}/token",
    summary="Neues Token ausstellen (das alte gilt danach nicht mehr)",
    dependencies=VERWALTEN,
)
async def geraet_neues_token(geraet_id: uuid.UUID, sitzung: DbSitzung) -> GeraetMitToken:
    token, hashwert = dienst.neues_token()
    geraet = await speicher.setze_token(sitzung, geraet_id, hashwert)
    return _mit_token(geraet, (await _manifest(sitzung)).stand, token)


@eltern.delete(
    "/geraete/{geraet_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Gerät entfernen",
    dependencies=VERWALTEN,
)
async def geraet_loeschen(geraet_id: uuid.UUID, sitzung: DbSitzung) -> None:
    await speicher.loesche_geraet(sitzung, geraet_id)


# --- Protokoll und Tagebuch ----------------------------------------------------


@eltern.get("/protokoll", summary="Was am Gerät passiert ist, neueste zuerst")
async def protokoll(
    sitzung: DbSitzung, anzahl: Annotated[int, Query(ge=1, le=500)] = 100
) -> list[EreignisAusgabe]:
    namen = {f.uid: f.name for f in await speicher.figuren(sitzung)}
    return [
        EreignisAusgabe(
            id=e.id,
            geraet=geraet_name,
            art=e.art,  # type: ignore[arg-type]
            text=dienst.beschreibe(
                e.art, knopf=e.knopf, uid=e.uid, spiel=e.spiel, figurennamen=namen
            ),
            zeitpunkt=e.zeitpunkt,
            empfangen=e.empfangen,
        )
        for e, geraet_name in await speicher.ereignisse(sitzung, anzahl)
    ]


@eltern.get("/tagebuch", summary="Tagebuch, neueste zuerst")
async def tagebuch(sitzung: DbSitzung) -> list[TagebuchAusgabe]:
    return [TagebuchAusgabe.model_validate(e) for e in await speicher.tagebuch(sitzung)]


@eltern.post(
    "/tagebuch",
    status_code=status.HTTP_201_CREATED,
    summary="Tagebucheintrag schreiben",
    dependencies=SCHREIBEN,
)
async def tagebuch_schreiben(werte: TagebuchEingabe, sitzung: DbSitzung) -> TagebuchAusgabe:
    return TagebuchAusgabe.model_validate(await speicher.lege_tagebuch_an(sitzung, werte))


@eltern.delete(
    "/tagebuch/{eintrag_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Tagebucheintrag löschen",
    dependencies=SCHREIBEN,
)
async def tagebuch_loeschen(eintrag_id: uuid.UUID, sitzung: DbSitzung) -> None:
    await speicher.loesche_tagebuch(sitzung, eintrag_id)


# --- Geraeteschnittstelle ------------------------------------------------------


@geraet_router.get("/stand", summary="Gerät: Manifest mit Einstellungen, Figuren, Dateien")
async def geraet_stand(geraet: AktuellesGeraet, sitzung: DbSitzung) -> Manifest:
    # Den Stand traegt das Geraet erst nach dem Abgleich ein, mit dem
    # Ereignis "abgleich" - hier hat es ihn nur abgeholt.
    speicher.melde(geraet, dt.datetime.now(dt.UTC), firmware=None, stand=None)
    return await _manifest(sitzung)


@geraet_router.get(
    "/dateien/{aufnahme_id}",
    summary="Gerät: eine Aufnahme als WAV",
    response_class=Response,
)
async def geraet_datei(
    aufnahme_id: uuid.UUID, geraet: AktuellesGeraet, sitzung: DbSitzung
) -> Response:
    daten, sha = await speicher.aufnahme_daten(sitzung, aufnahme_id)
    return Response(content=daten, media_type="audio/wav", headers={"ETag": f'"{sha}"'})


@geraet_router.post("/ereignisse", summary="Gerät: Ereignisse melden, live oder nachgereicht")
async def geraet_ereignisse(
    sendung: EreignisseEingang, geraet: AktuellesGeraet, sitzung: DbSitzung
) -> EreignisseAntwort:
    empfangen = dt.datetime.now(dt.UTC)
    zeilen = [
        {
            "geraet_id": geraet.id,
            "start": sendung.start if e.start is None else e.start,
            "nr": e.nr,
            "art": e.art,
            "knopf": e.knopf,
            "uid": e.uid,
            "spiel": e.spiel,
            "zeitpunkt": dienst.zeitpunkt(
                e, start=sendung.start, jetzt_ms=sendung.jetzt_ms, empfangen=empfangen
            ),
            "empfangen": empfangen,
        }
        for e in sendung.ereignisse
    ]
    neu = await speicher.speichere_ereignisse(sitzung, zeilen)
    speicher.melde(geraet, empfangen, firmware=sendung.firmware, stand=sendung.stand)
    return EreignisseAntwort(
        neu=neu,
        doppelt=len(zeilen) - neu,
        stand=(await _manifest(sitzung)).stand,
    )


# Feste Pfade zuerst: /geraet/... steht vor allem, was die Elternseite
# parametrisiert.
router.include_router(geraet_router)
router.include_router(eltern)
