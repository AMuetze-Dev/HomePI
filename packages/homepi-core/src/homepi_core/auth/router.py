"""Endpunkte der Anmeldung. Haengen unter /auth."""

from __future__ import annotations

import math
from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Request, Response, status

from ..deps import DbSitzung, Einstellungen, Kontext
from . import cookies, speicher
from .deps import Sitzungsbenutzer
from .dienst import AnmeldungFehlgeschlagen, ZuVieleVersuche, pruefe_passwort, wartezeit
from .modelle import Benutzer
from .schemas import Anmeldung, BenutzerAusgabe, Darstellung, PasswortAendern

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
        passwort_wechseln=benutzer.passwort_wechseln,
    )


@router.post("/anmelden", summary="Anmelden")
async def anmelden(
    daten: Anmeldung,
    antwort: Response,
    sitzung: DbSitzung,
    einstellungen: Einstellungen,
    kontext: Kontext,
) -> BenutzerAusgabe:
    drossel = kontext.drossel
    jetzt = datetime.now(UTC)

    # VOR dem Passwort pruefen, nicht danach: Sonst verraet die Antwort auf
    # das richtige Passwort, dass es das richtige war - und die Sperre waere
    # nur eine Verzoegerung.
    if (warten := wartezeit(drossel.fehlversuche(daten.name), jetzt)) > timedelta(0):
        minuten = max(1, math.ceil(warten.total_seconds() / 60))
        raise ZuVieleVersuche(
            f"Zu viele Fehlversuche mit diesem Namen. Versuch es in {minuten} "
            f"{'Minute' if minuten == 1 else 'Minuten'} noch einmal.",
            warten_sekunden=math.ceil(warten.total_seconds()),
        )

    try:
        benutzer, token = await speicher.melde_an(sitzung, daten.name, daten.passwort)
    except AnmeldungFehlgeschlagen:
        # Auch fuer Namen, die es nicht gibt - sonst verriete die Sperre,
        # welche es gibt.
        drossel.vermerke(daten.name, jetzt)
        raise

    drossel.vergiss(daten.name)
    cookies.setze(antwort, token, einstellungen)
    return _ausgabe(benutzer)


@router.post("/abmelden", status_code=status.HTTP_204_NO_CONTENT, summary="Abmelden")
async def abmelden(request: Request, antwort: Response, sitzung: DbSitzung) -> None:
    if token := request.cookies.get(cookies.NAME):
        await speicher.melde_ab(sitzung, token)
    cookies.loesche(antwort)


@router.get("/ich", summary="Wer ist angemeldet")
async def ich(benutzer: Sitzungsbenutzer) -> BenutzerAusgabe:
    return _ausgabe(benutzer)


@router.post(
    "/passwort",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Eigenes Passwort ändern",
)
async def passwort_aendern(
    daten: PasswortAendern,
    benutzer: Sitzungsbenutzer,
    request: Request,
    sitzung: DbSitzung,
) -> None:
    """Das eigene Passwort.

    Geht auch dann, wenn noch der Wechsel aussteht - es ist ja genau der
    Schritt, der ihn beendet. Deshalb ``Sitzungsbenutzer`` und nicht
    ``AktuellerBenutzer``.
    """
    from . import passwoerter

    if not passwoerter.passwort_stimmt(benutzer.passwort_hash, daten.altes_passwort):
        raise AnmeldungFehlgeschlagen("Das alte Passwort stimmt nicht")

    pruefe_passwort(daten.neues_passwort, benutzer.name)
    benutzer.passwort_hash = passwoerter.hashe_passwort(daten.neues_passwort)
    benutzer.passwort_wechseln = False

    # Alle **anderen** Geraete abmelden. Wer sein Passwort aendert, tut das
    # haeufig genau deshalb - eine weiterlaufende fremde Sitzung waere dann
    # fatal. Die eigene bleibt: der Benutzer sitzt davor und hat sich gerade
    # ausgewiesen. Ihn hier hinauszuwerfen hiesse, ihn nach einem erzwungenen
    # Erstwechsel auf die Anmeldeseite zu schicken.
    await speicher.melde_andere_ab(sitzung, benutzer.id, request.cookies.get(cookies.NAME))


@router.get("/darstellung", summary="Darstellung dieses Kontos")
async def darstellung(benutzer: Sitzungsbenutzer, sitzung: DbSitzung) -> Darstellung | None:
    """``null``, solange das Konto keine gewaehlt hat.

    Nicht die Voreinstellung: Dann uebernimmt die Oberflaeche die Wahl, die
    im Browser schon steht, statt sie beim ersten Anmelden auf "System"
    zurueckzusetzen.

    ``Sitzungsbenutzer`` und nicht ``AktuellerBenutzer``: Wer mit dem
    Startpasswort ankommt, sitzt vor genau dieser Oberflaeche.
    """
    werte = await speicher.darstellung_von(sitzung, benutzer.id)
    return Darstellung.model_validate(werte) if werte is not None else None


@router.put("/darstellung", summary="Darstellung dieses Kontos setzen")
async def darstellung_setzen(
    daten: Darstellung, benutzer: Sitzungsbenutzer, sitzung: DbSitzung
) -> Darstellung:
    await speicher.setze_darstellung(sitzung, benutzer.id, daten.model_dump())
    return daten
