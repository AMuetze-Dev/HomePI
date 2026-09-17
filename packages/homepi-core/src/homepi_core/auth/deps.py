"""Dependencies fuer Endpunkte, die eine Anmeldung voraussetzen.

from homepi_core.auth import AktuellerBenutzer, erfordert

@router.get("/")
async def liste(benutzer: AktuellerBenutzer) -> list[X]: ...

@router.delete("/{id}", dependencies=[erfordert("staffelpilot", Rolle.VERWALTER)])
async def entfernen(...) -> None: ...
"""

from __future__ import annotations

from typing import Annotated, cast

from fastapi import Depends, Request, Response
from fastapi.params import Depends as Abhaengigkeit

from ..deps import DbSitzung, hole_einstellungen
from . import cookies, speicher
from .dienst import (
    NichtAngemeldet,
    PasswortWechselNoetig,
    Rolle,
    ZugriffVerweigert,
    darf,
    pruefe_sitzung,
)
from .modelle import Benutzer


async def hole_sitzungsbenutzer(
    request: Request, antwort: Response, sitzung: DbSitzung
) -> Benutzer:
    """Wer ist angemeldet - ohne die Frage, ob er schon loslegen darf.

    Nur fuer die Endpunkte unter ``/auth``: 'wer bin ich', 'abmelden' und der
    Passwortwechsel selbst muessen auch dann gehen, wenn genau dieser Wechsel
    noch aussteht. Alles andere nimmt ``hole_benutzer``.
    """
    token = request.cookies.get(cookies.NAME)
    if not token:
        raise NichtAngemeldet("Für diese Seite ist eine Anmeldung nötig")

    eintrag = await speicher.finde_sitzung(sitzung, token)
    if eintrag is None:
        # Cookie ist da, Sitzung nicht - meist abgemeldet oder aufgeraeumt.
        cookies.loesche(antwort)
        raise NichtAngemeldet("Die Sitzung ist nicht mehr gültig")

    pruefung = pruefe_sitzung(eintrag.laeuft_ab)
    if not pruefung.gueltig:
        cookies.loesche(antwort)
        raise NichtAngemeldet(pruefung.grund)

    if pruefung.verlaengern:
        await speicher.verlaengere(sitzung, eintrag)
        cookies.setze(antwort, token, hole_einstellungen(request))

    if not eintrag.benutzer.aktiv:
        raise NichtAngemeldet("Dieses Konto ist deaktiviert")

    return eintrag.benutzer


Sitzungsbenutzer = Annotated[Benutzer, Depends(hole_sitzungsbenutzer)]


async def hole_benutzer(benutzer: Sitzungsbenutzer) -> Benutzer:
    """Wer ist angemeldet und darf loslegen?

    Die Pruefung auf einen ausstehenden Passwortwechsel sitzt hier und nicht in
    einzelnen Endpunkten: hierueber kommt **jedes** Artefakt an seinen
    Benutzer, auch eines, das seine Rechte selbst prueft. Eine Maske im
    Frontend waere keine Sicherung, sondern nur eine Bitte.
    """
    if benutzer.passwort_wechseln:
        raise PasswortWechselNoetig(
            "Dieses Konto benutzt noch das vergebene Startpasswort. Wähle erst ein eigenes."
        )
    return benutzer


AktuellerBenutzer = Annotated[Benutzer, Depends(hole_benutzer)]


async def hole_benutzer_optional(
    request: Request, antwort: Response, sitzung: DbSitzung
) -> Benutzer | None:
    """Wie ``hole_benutzer``, wirft aber nicht.

    Fuer Endpunkte, die beiden antworten muessen - allen voran ``GET /module``:
    ein nicht angemeldeter Besucher soll die oeffentlichen Artefakte sehen und
    keinen 401 bekommen.
    """
    if not request.cookies.get(cookies.NAME):
        # Der haeufigste Fall. Ohne diese Abkuerzung fragte jeder anonyme
        # Aufruf die Datenbank nach einer Sitzung, die es nicht geben kann.
        return None
    try:
        return await hole_benutzer(await hole_sitzungsbenutzer(request, antwort, sitzung))
    except (NichtAngemeldet, PasswortWechselNoetig):
        # Bis zum Passwortwechsel sieht dieses Konto so viel wie ein Besucher:
        # die oeffentlichen Artefakte. An die anderen kaeme es ohnehin nicht.
        return None


MoeglicherBenutzer = Annotated[Benutzer | None, Depends(hole_benutzer_optional)]


def erfordert(artefakt: str, rolle: Rolle) -> Abhaengigkeit:
    """Prueft die Rolle fuer genau dieses Artefakt.

    Es gibt keinen globalen Administrator: wer StaffelPilot verwaltet, hat
    damit keinerlei Zugriff auf die Geraete im Haus.
    """

    async def pruefer(benutzer: AktuellerBenutzer) -> None:
        if not darf(speicher.rechte_von(benutzer), artefakt, rolle):
            raise ZugriffVerweigert(
                f"Für '{artefakt}' fehlt die Rolle '{rolle.value}'",
                artefakt=artefakt,
                benoetigt=rolle.value,
            )

    # FastAPIs Depends ist als Any typisiert; der konkrete Rueckgabetyp ist
    # fastapi.params.Depends.
    return cast(Abhaengigkeit, Depends(pruefer))
