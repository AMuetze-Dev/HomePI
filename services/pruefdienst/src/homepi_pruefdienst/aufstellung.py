"""Die Aufstellung, wie DFBnet sie über seine Schnittstelle liefert.

**Aus dem HTML des Spielberichts kommt sie nicht.** Die Seite nennt die beiden
Mannschaftsnamen und sonst nichts; wer Spieler, Geburtsdaten, Spielrecht und
Fotos braucht, fragt die Aufstellungsschnittstelle. Genau davon hängen die
Regeln ab, die etwas wert sind — Spielerfoto, Spielrecht, Stammspieler,
Altersklasse.

Hier steht nur die **Übersetzung** von deren JSON in unsere Felder, und die ist
rein: gleiche Eingabe, gleicher Ausgang, kein Netz. Übernommen aus
`D:/DevLibrary/StaffelPilot/src/automation/match_report_loader.py`.

Die Felder werden **nicht umgedeutet, nur übernommen**. Was `eligibleForTeam`
bedeutet, steht in der Regel, die es liest, und nicht hier.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

#: Unterscheidet "das Feld war nicht in der Antwort" von "das Feld war null".
#: Das erste ist Unwissen, das zweite ein fehlendes Foto — und ein Unwissen,
#: das als Verstoß gemeldet wird, schickt einen Verein wegen nichts los.
_NICHT_DA = object()


def name_zusammensetzen(vorname: str, nachname: str) -> str:
    """'Müller, Max' — so steht er im Spielbericht und auf jedem Schreiben."""
    teile = [t for t in (nachname, vorname) if t]
    return ", ".join(teile)


def datum_deutsch(iso: str) -> str:
    """'2008-03-14' → '14.03.2008'. Was nicht lesbar ist, bleibt stehen.

    Ein unlesbares Datum zu verwerfen hieße, still ein Geburtsdatum zu
    verlieren — und die Altersregeln schweigen dann, statt zu melden.
    """
    if not iso:
        return ""
    try:
        return datetime.fromisoformat(iso.replace("Z", "+00:00")).strftime("%d.%m.%Y")
    except ValueError:
        return iso


def foto_aus_api(spieler: dict[str, Any], fotos_sichtbar: bool) -> tuple[str, str]:
    """Zustand und Stand des Spielerfotos, § 67 (2) und (3) SpO SFV.

    DFBnet liefert je Spieler `playerPhoto`: entweder ein Objekt mit
    `timestamp`, oder `null`. Der Zeitstempel ist der einzige Anhaltspunkt für
    das Alter des Fotos — im Spielbericht selbst steht er nirgends.

    `fotos_sichtbar` kommt aus `authorizedToViewPlayerPhotos`. Ist das falsch,
    sagt `null` nichts über das Foto aus, sondern etwas über die eigene
    Berechtigung — und dann schweigen wir.

    Drei Zustände mit Absicht: `""` heißt *nicht bekannt* und darf nie wie
    `"fehlt"` aussehen.
    """
    if not fotos_sichtbar:
        return "", ""
    foto = spieler.get("playerPhoto", _NICHT_DA)
    if foto is _NICHT_DA:
        return "", ""
    if not foto:
        return "fehlt", ""
    return "vorhanden", str(foto.get("timestamp") or "")


def spieler_aus_api(spieler: dict[str, Any], fotos_sichtbar: bool = True) -> dict[str, Any]:
    """Ein Spieler der Aufstellungsantwort in unsere Felder."""
    nationalitaet = (spieler.get("nationality") or {}).get("shortName", "")
    abzeichen = [nationalitaet] if nationalitaet else []
    stand = (spieler.get("playerStatusShort") or {}).get("shortName", "")
    if stand and stand not in abzeichen:
        abzeichen.append(stand)

    foto_zustand, foto_stand = foto_aus_api(spieler, fotos_sichtbar)
    return {
        "name": name_zusammensetzen(spieler.get("firstName", ""), spieler.get("lastName", "")),
        "pass_number": spieler.get("playerIdCardNumber", ""),
        "birthdate": datum_deutsch(spieler.get("dateOfBirth", "")),
        "jersey_number": str(spieler.get("jerseyNumber", "")),
        "is_goalkeeper": bool(spieler.get("goalkeeper")),
        "is_captain": bool(spieler.get("captain")),
        "badges": abzeichen,
        "photo_title": "",
        "photo_state": foto_zustand,
        "photo_timestamp": foto_stand,
        # Spielrecht: nicht umgedeutet, nur uebernommen.
        "eligible_for_team": spieler.get("eligibleForTeam"),
        "eligible_for_club": spieler.get("eligibleForClub"),
        "no_championship_eligibility": spieler.get("noChampionshipEligibility"),
        "championship_from": spieler.get("championshipEligibilityFrom") or "",
        "competitive_from": spieler.get("beginDateForCompetitiveMatches") or "",
        "guest_eligibility": spieler.get("guestEligibility"),
        "second_eligibility": spieler.get("secondEligibility"),
        "suspension_note": spieler.get("suspensionLineUpError") or "",
        "player_id": spieler.get("playerId", ""),
    }


def vereinswappen_aus_url(url: str) -> str:
    """Die Kennung aus der Wappen-Adresse. Leer, wenn keine drin ist."""
    if not url or "id=" not in url:
        return ""
    return url.split("id=", 1)[1].split("&", 1)[0]
