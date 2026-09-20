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

import json
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


# ── Die Schnittstelle ─────────────────────────────────────────

#: Welche Mannschaften an diesem Spielbericht haengen.
ADRESSE_MANNSCHAFTEN = "https://www.dfbnet.org/sbo-mobile/v2/oauth/report/{kennung}/teams"

#: Die Aufstellung einer dieser Mannschaften.
ADRESSE_AUFSTELLUNG = "https://www.dfbnet.org/sbo-mobile/v2/oauth/team/{mannschaft}/line-up"


def json_lesen(rumpf: bytes) -> Any:
    """Die Antwort lesen -- notfalls in der Kodierung, die wirklich drinsteht.

    DFBnet sagt UTF-8 und schickt manchmal ISO-8859-1. Wer das nicht
    abfaengt, bekommt "Mueller" als "M?ller" -- und dann findet die Regel,
    die eine DFBnet-Warnung einem Spieler zuordnet, den Namen nicht mehr.
    """
    try:
        text = rumpf.decode("utf-8")
        if "\ufffd" not in text:  # das Ersatzzeichen
            return json.loads(text)
    except (UnicodeDecodeError, json.JSONDecodeError):
        pass
    return json.loads(rumpf.decode("latin-1"))


def fotos_sichtbar(lineup: dict[str, Any]) -> bool:
    """Ob wir die Fotos ueberhaupt sehen duerfen.

    Ohne diese Berechtigung liefert DFBnet fuer jeden Spieler `null`. Das als
    "Foto fehlt" zu melden hiesse, jeder Mannschaft eines anderen
    Staffelleiters saemtliche Fotos abzusprechen.
    """
    return lineup.get("authorizedToViewPlayerPhotos") is not False


def offizieller_aus_api(offizieller: dict[str, Any]) -> dict[str, Any]:
    """Ein Teamoffizieller. Seine Rollen stehen in `badges` -- so liest der
    Extraktor sie, und daran haengt die Regel zum Ordnungsdienst."""
    rollen = [t.get("name", "") for t in offizieller.get("types", []) if t.get("name")]
    return {
        "name": name_zusammensetzen(
            offizieller.get("firstName", ""), offizieller.get("lastName", "")
        ),
        "pass_number": "",
        "birthdate": "",
        "jersey_number": "",
        "is_goalkeeper": False,
        "is_captain": False,
        "badges": rollen,
        "photo_title": "",
        "is_official": True,
    }


def abschnitte_aus(lineup: dict[str, Any]) -> list[dict[str, Any]]:
    """Trainerbank, Startaufstellung, Ersatzbank -- in der Form, die der
    Extraktor erwartet.

    Die Ueberschriften sind nicht Zierde: der Extraktor entscheidet an ihnen,
    was Startelf und was Bank ist.
    """
    abschnitte: list[dict[str, Any]] = []

    offizielle = [
        offizieller_aus_api(o)
        for o in [
            *lineup.get("teamOfficials", []),
            *lineup.get("additionalBenchOfficials", []),
        ]
    ]
    if offizielle:
        abschnitte.append(
            {"title": f"Trainerbank ({len(offizielle)} Teamoffizielle)", "players": offizielle}
        )

    sichtbar = fotos_sichtbar(lineup)
    for schluessel, ueberschrift in (
        ("lineUpPlayers", "Startaufstellung"),
        ("reservePlayers", "Ersatzbank"),
    ):
        spieler = [spieler_aus_api(s, sichtbar) for s in lineup.get(schluessel, [])]
        if spieler:
            abschnitte.append(
                {"title": f"{ueberschrift} ({len(spieler)} Spieler)", "players": spieler}
            )
    return abschnitte


def mannschaft_aus_api(mannschaft: dict[str, Any], lineup: dict[str, Any]) -> dict[str, Any] | None:
    """Eine Mannschaft samt Aufstellung, wie der Extraktor sie nimmt.

    `None`, wenn die Mannschaft keine Kennung hat -- ohne sie laesst sich
    nichts zuordnen, und ein Kader am falschen Verein ist schlimmer als
    keiner.
    """
    kennung = mannschaft.get("id")
    if not kennung:
        return None
    return {
        "teamName": mannschaft.get("teamName", ""),
        "team_id": kennung,
        "club_logo_id": vereinswappen_aus_url(mannschaft.get("clubLogoUrl", "") or ""),
        "sections": abschnitte_aus(lineup),
    }


#: Die Einsaetze eines Spielers in dieser Saison.
ADRESSE_EINSAETZE = (
    "https://www.dfbnet.org/sbo-mobile/v2/oauth/team/{mannschaft}"
    "/player/{spieler}/appearance-statistic"
)


def einsaetze_aus_api(antwort: dict[str, Any]) -> dict[str, Any]:
    """Die Einsatzstatistik in unsere Felder.

    Daran haengt Paragraf 68: die Wartefrist nach einem Spiel oben, und die
    Stammspielergrenze. Beides rechnet ueber die Saison, und im Spielbericht
    steht davon nichts.

    Uebernommen aus `_enrich_with_appearances` der alten Anwendung. Wie schon
    bei der Aufstellung wird **nicht umgedeutet, nur uebernommen** -- was ein
    Einsatz bedeutet, steht in der Regel, die ihn liest.
    """
    einsaetze = antwort.get("appearances") or []
    return {
        "count": len(einsaetze),
        "minutes": antwort.get("overallPlayedMinutesNormalized", 0),
        "matches": [
            {
                "match_id": e.get("matchId", ""),
                "kickoff": e.get("kickoff", ""),
                "home_team": e.get("homeTeamName", ""),
                "away_team": e.get("awayTeamName", ""),
                "home_team_logo_id": vereinswappen_aus_url(e.get("homeTeamClubLogoUrl", "") or ""),
                "away_team_logo_id": vereinswappen_aus_url(e.get("awayTeamClubLogoUrl", "") or ""),
                "division": e.get("divisionName", ""),
                "competition": e.get("competitionTypeName", ""),
                "minutes": e.get("playedMinutesNormalized", 0),
                "match_day": e.get("matchDay"),
            }
            for e in einsaetze
        ],
    }


#: Was an einem Spieler steht, von dem wir die Einsaetze nicht kennen.
#:
#: Nicht `count: 0`, sondern gar nichts: eine 0 hiesse "hat diese Saison nicht
#: gespielt", und die Stammspielerregel schwiege daraufhin, als haette sie
#: geprueft. Der Uebersetzer laesst die Historie dann leer, und die Regeln
#: sagen selbst, dass sie nichts wissen.
OHNE_EINSAETZE: dict[str, Any] = {}
