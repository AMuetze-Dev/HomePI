"""Endpunkte der Anmeldung. Haengen unter /auth."""

from __future__ import annotations

from fastapi import APIRouter, Request, Response, status

from ..deps import DbSitzung, Einstellungen
from . import cookies, speicher
from .deps import AktuellerBenutzer
from .dienst import AnmeldungFehlgeschlagen, pruefe_passwort
from .modelle import Benutzer
from .schemas import Anmeldung, BenutzerAusgabe, PasswortAendern

router = APIRouter(tags=["anmeldung"])


def _ausgabe(benutzer: Benutzer) -> BenutzerAusgabe:
    """Ausdruecklich Feld fuer Feld.

    model_validate wuerde 'rechte' vom ORM-Objekt lesen und dort eine
    list[Recht] finden, wo ein dict erwartet wird - und das Modell haette
    ueberdies jedes weitere Feld mitgenommen, auch den Passwort-Hash.
    """
    return BenutzerAusgabe(
        id=benutzer.id,
        name=benutzer.name,
        anzeigename=benutzer.anzeigename,
        rechte=speicher.rechte_von(benutzer),
    )


@router.post("/anmelden", summary="Anmelden")
async def anmelden(
    daten: Anmeldung,
    antwort: Response,
    sitzung: DbSitzung,
    einstellungen: Einstellungen,
) -> BenutzerAusgabe:
    benutzer, token = await speicher.melde_an(sitzung, daten.name, daten.passwort)
    cookies.setze(antwort, token, einstellungen)
    return _ausgabe(benutzer)


@router.post("/abmelden", status_code=status.HTTP_204_NO_CONTENT, summary="Abmelden")
async def abmelden(request: Request, antwort: Response, sitzung: DbSitzung) -> None:
    if token := request.cookies.get(cookies.NAME):
        await speicher.melde_ab(sitzung, token)
    cookies.loesche(antwort)


@router.get("/ich", summary="Wer ist angemeldet")
async def ich(benutzer: AktuellerBenutzer) -> BenutzerAusgabe:
    return _ausgabe(benutzer)


@router.post(
    "/passwort",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Eigenes Passwort ändern",
)
async def passwort_aendern(
    daten: PasswortAendern,
    benutzer: AktuellerBenutzer,
    antwort: Response,
    sitzung: DbSitzung,
) -> None:
    from . import passwoerter

    if not passwoerter.passwort_stimmt(benutzer.passwort_hash, daten.altes_passwort):
        raise AnmeldungFehlgeschlagen("Das alte Passwort stimmt nicht")

    pruefe_passwort(daten.neues_passwort, benutzer.name)
    benutzer.passwort_hash = passwoerter.hashe_passwort(daten.neues_passwort)

    # Alle Geraete abmelden. Wer das Passwort aendert, tut das haeufig genau
    # deshalb - eine weiterlaufende fremde Sitzung waere dann fatal.
    await speicher.melde_ueberall_ab(sitzung, benutzer.id)
    cookies.loesche(antwort)
