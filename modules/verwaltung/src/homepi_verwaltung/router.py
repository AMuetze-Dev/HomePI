"""Endpunkte der Verwaltung. Hängen unter ``/verwaltung``.

Der ganze Router ist ``Zugang.GESCHUETZT`` mit ``mindestrolle=VERWALTER`` -
die Prüfung hängt damit am Router und nicht an jedem einzelnen Endpunkt. Ein
Endpunkt, der hier später dazukommt, ist von selbst geschützt; das ist der
Grund für diese Bauweise.

Was hier trotzdem geprüft wird, sind die Regeln, die auch einen Verwalter
binden: niemand nimmt sich selbst die Verwaltung, und der letzte Verwalter
bleibt. Beides steht als reine Funktion in dienst.py.
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Request, status
from homepi_core.auth import AktuellerBenutzer, Benutzer, Rolle, darf_verwalten
from homepi_core.auth import speicher as kern
from homepi_core.auth.cookies import NAME as COOKIE
from homepi_core.auth.dienst import neues_startpasswort
from homepi_core.deps import DbSitzung, Kontext

from . import dienst, speicher
from .schemas import (
    ArtefaktAusgabe,
    BenutzerAenderung,
    BenutzerAusgabe,
    KontoAngelegt,
    NeuerBenutzer,
    PasswortGesetzt,
    PasswortSetzen,
    RechtSetzen,
    Ueberblick,
)

router = APIRouter()


def _ausgabe(benutzer: Benutzer) -> BenutzerAusgabe:
    """Feld für Feld. ``model_validate`` würde vom ORM-Objekt auch den
    Passwort-Hash mitnehmen."""
    rechte = kern.rechte_von(benutzer)
    return BenutzerAusgabe(
        id=benutzer.id,
        name=benutzer.name,
        anzeigename=benutzer.anzeigename,
        aktiv=benutzer.aktiv,
        rechte=dict(sorted(rechte.items())),
        angelegt=getattr(benutzer, "angelegt", None),
        verwalter=darf_verwalten(rechte),
        passwort_wechseln=benutzer.passwort_wechseln,
    )


async def _zaehlstand(sitzung: DbSitzung, ziel: Benutzer) -> tuple[int, bool]:
    """Wie viele Verwalter gibt es, und ist das Ziel einer davon?"""
    return (
        await kern.zaehle_verwalter(sitzung),
        await kern.ist_verwalter(sitzung, ziel.id),
    )


@router.get("/", summary="Überblick")
async def ueberblick(sitzung: DbSitzung, kontext: Kontext) -> Ueberblick:
    """Jedes Artefakt antwortet unter seinem Präfix.

    Daran erkennt der Rauchtest, dass ein Modul aus dem Manifest wirklich
    eingehängt ist - ein 404 hier hiesse: im Manifest genannt, aber nirgends
    angeschlossen.
    """
    konten = await speicher.alle(sitzung)
    return Ueberblick(
        konten=len(konten),
        verwalter=sum(1 for k in konten if darf_verwalten(kern.rechte_von(k))),
        gesperrt=sum(1 for k in konten if not k.aktiv),
        artefakte=len(kontext.module.module) if kontext.module else 0,
    )


# --- Benutzer --------------------------------------------------------------


@router.get("/benutzer", summary="Alle Konten")
async def liste(sitzung: DbSitzung) -> list[BenutzerAusgabe]:
    return [_ausgabe(b) for b in await speicher.alle(sitzung)]


@router.post("/benutzer", status_code=status.HTTP_201_CREATED, summary="Konto anlegen")
async def anlegen(daten: NeuerBenutzer, sitzung: DbSitzung) -> KontoAngelegt:
    """Name genügt. Ohne Passwort entsteht ein Startpasswort.

    Es steht **einmalig** in dieser Antwort - nicht in der Datenbank und in
    keiner weiteren Abfrage. Wer das Konto anlegt, gibt es weiter; der
    Benutzer ersetzt es beim ersten Anmelden.

    Ohne Rechte: was das Konto darf, wird danach einzeln vergeben - so steht
    die Entscheidung im Log und nicht in einer Voreinstellung.
    """
    start = daten.passwort or neues_startpasswort()
    benutzer = await kern.lege_benutzer_an(
        sitzung, daten.name, start, daten.anzeigename, wechsel_erzwingen=True
    )
    return KontoAngelegt(**_ausgabe(benutzer).model_dump(), startpasswort=start)


@router.get("/benutzer/{benutzer_id}", summary="Ein Konto")
async def einzeln(benutzer_id: uuid.UUID, sitzung: DbSitzung) -> BenutzerAusgabe:
    return _ausgabe(await speicher.finde(sitzung, benutzer_id))


@router.patch("/benutzer/{benutzer_id}", summary="Anzeigename oder Sperre ändern")
async def aendern(
    benutzer_id: uuid.UUID,
    daten: BenutzerAenderung,
    sitzung: DbSitzung,
    ich: AktuellerBenutzer,
) -> BenutzerAusgabe:
    ziel = await speicher.finde(sitzung, benutzer_id)

    if daten.anzeigename is not None:
        ziel.anzeigename = daten.anzeigename.strip() or ziel.name

    if daten.aktiv is not None and daten.aktiv != ziel.aktiv:
        anzahl, ist_verwalter = await _zaehlstand(sitzung, ziel)
        dienst.pruefe_sperren(
            eigene_id=ich.id,
            ziel_id=ziel.id,
            aktiv=daten.aktiv,
            anzahl_verwalter=anzahl,
            ziel_ist_verwalter=ist_verwalter,
        )
        await speicher.setze_aktiv(sitzung, ziel, daten.aktiv)

    await sitzung.flush()
    return _ausgabe(ziel)


@router.delete(
    "/benutzer/{benutzer_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Konto löschen",
)
async def loeschen(benutzer_id: uuid.UUID, sitzung: DbSitzung, ich: AktuellerBenutzer) -> None:
    ziel = await speicher.finde(sitzung, benutzer_id)
    anzahl, ist_verwalter = await _zaehlstand(sitzung, ziel)
    dienst.pruefe_loeschen(
        eigene_id=ich.id,
        ziel_id=ziel.id,
        anzahl_verwalter=anzahl,
        ziel_ist_verwalter=ist_verwalter,
    )
    await speicher.loesche(sitzung, ziel)


@router.put("/benutzer/{benutzer_id}/passwort", summary="Passwort zurücksetzen")
async def passwort(
    benutzer_id: uuid.UUID,
    daten: PasswortSetzen,
    request: Request,
    sitzung: DbSitzung,
    ich: AktuellerBenutzer,
) -> PasswortGesetzt:
    """Setzt ein neues Passwort. Ohne Angabe entsteht ein Startpasswort.

    Am **fremden** Konto ist das Ergebnis immer ein Startpasswort: es muss
    beim nächsten Anmelden ersetzt werden, denn ein Passwort, das ein
    Verwalter kennt, soll nicht das bleibende sein. Am eigenen Konto nicht -
    dort ist es schlicht das neue Passwort.

    Alle Sitzungen des Kontos enden dabei. Wer ein Passwort zurücksetzt, tut
    das meist, weil etwas schiefging.
    """
    ziel = await speicher.finde(sitzung, benutzer_id)
    fremd = ziel.id != ich.id
    start = daten.passwort or neues_startpasswort()

    await speicher.setze_passwort(
        sitzung,
        ziel,
        start,
        wechsel_erzwingen=fremd,
        laufendes_token=request.cookies.get(COOKIE),
    )

    # Ein selbst getipptes Passwort gibt der Verwalter nicht zurueck - er
    # kennt es. Zurueck kommt nur, was der Dienst erzeugt hat.
    return PasswortGesetzt(startpasswort=start if daten.passwort is None else None)


# --- Rechte ----------------------------------------------------------------


@router.put("/benutzer/{benutzer_id}/rechte/{artefakt}", summary="Rolle setzen")
async def recht_setzen(
    benutzer_id: uuid.UUID,
    artefakt: str,
    daten: RechtSetzen,
    sitzung: DbSitzung,
    ich: AktuellerBenutzer,
) -> BenutzerAusgabe:
    ziel = await speicher.finde(sitzung, benutzer_id)
    anzahl, ist_verwalter = await _zaehlstand(sitzung, ziel)
    dienst.pruefe_rollenwechsel(
        eigene_id=ich.id,
        ziel_id=ziel.id,
        artefakt=artefakt,
        neue_rolle=daten.rolle,
        anzahl_verwalter=anzahl,
        ziel_ist_verwalter=ist_verwalter,
    )

    await kern.setze_recht(sitzung, ziel.id, artefakt, daten.rolle)
    await sitzung.refresh(ziel)
    return _ausgabe(ziel)


@router.delete("/benutzer/{benutzer_id}/rechte/{artefakt}", summary="Rolle entziehen")
async def recht_entziehen(
    benutzer_id: uuid.UUID,
    artefakt: str,
    sitzung: DbSitzung,
    ich: AktuellerBenutzer,
) -> BenutzerAusgabe:
    ziel = await speicher.finde(sitzung, benutzer_id)
    anzahl, ist_verwalter = await _zaehlstand(sitzung, ziel)
    dienst.pruefe_rollenwechsel(
        eigene_id=ich.id,
        ziel_id=ziel.id,
        artefakt=artefakt,
        neue_rolle=None,
        anzahl_verwalter=anzahl,
        ziel_ist_verwalter=ist_verwalter,
    )

    await kern.entziehe_recht(sitzung, ziel.id, artefakt)
    await sitzung.refresh(ziel)
    return _ausgabe(ziel)


# --- Artefakte -------------------------------------------------------------


@router.get("/artefakte", summary="Wofür sich Rechte vergeben lassen")
async def artefakte(kontext: Kontext) -> list[ArtefaktAusgabe]:
    """Die Liste kommt aus dem laufenden Gateway, nicht aus einer Tabelle.

    Eine gepflegte Liste wäre genau dann falsch, wenn es darauf ankommt: nach
    einem Deploy, bei dem ein Artefakt dazugekommen ist.
    """
    register = kontext.module
    if register is None:
        return []

    return [ArtefaktAusgabe(id=m.id, titel=m.titel, zugang=m.zugang.value) for m in register.module]


__all__ = ["Rolle", "router"]
