"""Die Ersteinrichtung: das erste Konto, das verwalten darf.

Zwei Bedingungen, und beide prüft **das Backend** bei jedem Aufruf:

1. Es gibt noch keinen Verwalter.
2. Der Aufrufer legt das Einrichtungstoken vor, das beim Start im Log stand.

Warum beides und nicht nur die erste: wer als Erster an die frisch ausgerollte
Adresse kommt, würde sonst die Installation übernehmen. Im Heimnetz ist das
schon unschön; hinter einem öffentlichen Reverse Proxy wäre es das Ende. Das
Token steht im Log des Dienstes - lesen kann es also nur, wer Zugriff auf die
Maschine hat. Damit gilt dieselbe Bedingung wie für ``homepi benutzer anlegen``,
nur bequemer.

Dass die Oberfläche die Maske nicht anzeigt, ist **keine** Sicherung. Wer
``/einrichtung`` von Hand aufruft oder direkt gegen die API spricht, landet
trotzdem hier - und hier wird geprüft.
"""

from __future__ import annotations

from fastapi import APIRouter, Response

from ..deps import DbSitzung, Einstellungen
from . import cookies, speicher
from .dienst import (
    VERWALTUNG,
    EinrichtungNichtNoetig,
    EinrichtungTokenFalsch,
    Rolle,
)
from .schemas import BenutzerAusgabe, Einrichtung, Einrichtungsstand

router = APIRouter(tags=["einrichtung"])


@router.get("/einrichtung", summary="Ist die Ersteinrichtung noch offen?")
async def stand(sitzung: DbSitzung) -> Einrichtungsstand:
    """Nur ein Ja oder Nein, und bewusst ohne Anmeldung.

    Die Oberfläche muss beim ersten Aufruf entscheiden, ob sie die Maske oder
    die Anmeldung zeigt. Mehr als 'hier ist noch niemand' verrät die Antwort
    nicht - und das sieht ohnehin jeder, der die Anmeldeseite aufruft.
    """
    return Einrichtungsstand(noetig=await speicher.einrichtung_noetig(sitzung))


@router.post("/einrichtung", summary="Ersten Verwalter anlegen")
async def einrichten(
    daten: Einrichtung,
    antwort: Response,
    sitzung: DbSitzung,
    einstellungen: Einstellungen,
) -> BenutzerAusgabe:
    """Legt den ersten Verwalter an und meldet ihn gleich an.

    Reihenfolge ist Absicht: erst die Frage, ob überhaupt noch eingerichtet
    werden darf, dann das Token. Wäre es andersherum, verriete die Antwortzeit
    bei falschem Token, ob die Einrichtung noch offen ist.
    """
    if not await speicher.einrichtung_noetig(sitzung):
        raise EinrichtungNichtNoetig(
            "Diese Installation hat bereits einen Verwalter. Weitere Konten "
            "legt er in der Verwaltung an."
        )

    if not await speicher.einrichtungstoken_stimmt(sitzung, daten.token):
        raise EinrichtungTokenFalsch(
            "Das Einrichtungstoken stimmt nicht. Es steht im Log des Gateways, "
            "gleich nach dem Start."
        )

    benutzer = await speicher.lege_benutzer_an(
        sitzung, daten.name, daten.passwort, daten.anzeigename
    )
    await speicher.setze_recht(sitzung, benutzer.id, VERWALTUNG, Rolle.VERWALTER)
    await speicher.schliesse_einrichtung(sitzung)

    _, token = await speicher.melde_an(sitzung, benutzer.name, daten.passwort)
    cookies.setze(antwort, token, einstellungen)

    return BenutzerAusgabe(
        id=benutzer.id,
        name=benutzer.name,
        anzeigename=benutzer.anzeigename,
        rechte={VERWALTUNG: Rolle.VERWALTER},
    )
