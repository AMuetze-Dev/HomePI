"""Aus einem Mannschaftsnamen lesen, welche Mannschaft eines Vereins es ist.

Uebernommen aus `D:/DevLibrary/StaffelPilot/src/rules/stammspieler.py` -- nur
die drei Stuecke, die der Uebersetzer braucht. Der Rest jener Datei zaehlt
Einsaetze ueber eine Saison und braucht dafuer einen Speicher, den dieser
Dienst nicht hat.

Wozu: ohne diese Rueckfallebene prueft die Wartefrist gar nicht mehr, sobald
in der Staffel keine hoeheren Mannschaften hinterlegt sind -- die Regel liefe
durch und faende nichts. Genau der stille Ausfall, den es hier nicht geben
darf.
"""

from __future__ import annotations

import re

# Matches trailing team numbers like "Dresdner SC 1898 3" or "1. FC Pirna 2."
# Limit to 1-3 digits so years (e.g. "Dresdner SC 1898") are not treated as team suffixes.
_SUFFIX_RE = re.compile(r"\s+(\d{1,3})\.?$")

# Roman numerals are not used by DFBnet but kept for robustness.
_ROMAN_SUFFIX_RE = re.compile(r"\s+([IVX]+)$", re.IGNORECASE)


def club_name_and_suffix(team_name: str) -> tuple[str, int | None]:
    """Return (club_base_name, team_suffix) for a DFBnet team name.

    The suffix is None for the first team, 2/3/... for reserve teams.
    """
    name = (team_name or "").strip()
    if not name:
        return ("", None)

    m = _SUFFIX_RE.search(name)
    if m:
        return (name[: m.start()].strip(), int(m.group(1)))

    m = _ROMAN_SUFFIX_RE.search(name)
    if m:
        roman = m.group(1).upper()
        value = {"I": 1, "II": 2, "III": 3, "IV": 4, "V": 5}.get(roman)
        if value:
            return (name[: m.start()].strip(), value)

    return (name, None)


def is_same_club(team_a: str, team_b: str) -> bool:
    """True if the two team names belong to the same club."""
    return club_name_and_suffix(team_a)[0] == club_name_and_suffix(team_b)[0]


def is_higher_class(
    team_name: str,
    current_team_name: str,
    team_logo_id: str = "",
    current_logo_id: str = "",
    current_team_suffix: int | None = None,
) -> bool:
    """True if team_name is a higher-class team of the same club.

    Uses DFBnet club logo IDs when available and falls back to name parsing.
    ``current_team_suffix`` overrides the suffix parsed from ``current_team_name``
    when the staffel config explicitly defines the own team number.
    """
    club_a, suffix_a = club_name_and_suffix(team_name)
    club_b, parsed_suffix_b = club_name_and_suffix(current_team_name)
    suffix_b = current_team_suffix if current_team_suffix is not None else parsed_suffix_b

    if team_logo_id and current_logo_id:
        if team_logo_id != current_logo_id:
            return False
        return _ranks_higher(suffix_a, suffix_b)

    # Fallback to name-based club detection.
    if club_a != club_b or not club_a:
        return False

    # Apply configured current-team suffix when the current team name has no
    # numeric suffix (e.g. "SV Loschwitz" explicitly configured as 1st team).
    if suffix_b is None:
        suffix_b = current_team_suffix

    return _ranks_higher(suffix_a, suffix_b)


def _ranks_higher(suffix_a: int | None, suffix_b: int | None) -> bool:
    """Whether team A plays in a higher class than team B, by team number.

    No suffix means the club's first team, which is the highest one. The two
    call sites used to carry their own copy of this ladder and only one of them
    guarded `suffix_b is None`, so a numbered team compared against an unnumbered
    one raised `'<' not supported between 'int' and 'NoneType'` — the rule then
    aborted and every affected match got a CRITICAL rule_error that blocked
    ticking it off.
    """
    if suffix_a is None:
        # A is the first team: higher than any numbered team, equal to another
        # unnumbered one.
        return suffix_b is not None
    if suffix_b is None:
        # B is the first team, A is numbered — A is lower, never higher.
        return False
    return suffix_a < suffix_b
