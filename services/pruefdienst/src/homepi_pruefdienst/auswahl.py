"""Einen Namen aus der Staffel gegen das treffen, was DFBnet anbietet.

Woertlich uebernommen aus
`D:/DevLibrary/StaffelPilot/src/automation/matching.py`, mit der Tabelle der
Mannschaftsarten aus `src/models/config.py`.

Hier passiert "Ue35 1. Stadtklasse wird nicht geprueft" -- und die Antwort war
ein Zeichenkettenvergleich, kein Playwright-Problem. Deshalb steht es rein
hier und nicht im Browser.
"""

from __future__ import annotations

import re
import unicodedata

#: Age band written into a name ("Ü35", "Ue 40"). Removing it turns a
#: Staffelleiter's name for a league into the Spielklasse DFBnet offers.
_AGE_BAND_RE = re.compile(r"\b[ÜüU]\s*e?\s*\d{2}\b|\bue\s*\d{2}\b", re.IGNORECASE)


def normalise(text: str) -> str:
    """Reduce a name to what is worth comparing.

    Folds case and umlauts, drops punctuation that DFBnet and the config
    disagree about ("3.Kreisliga (C)" vs "3. Kreisliga (C)") and collapses
    whitespace.
    """
    if not text:
        return ""
    lowered = unicodedata.normalize("NFKD", text.strip().lower())
    lowered = "".join(ch for ch in lowered if not unicodedata.combining(ch))
    for src, dst in (("ß", "ss"),):
        lowered = lowered.replace(src, dst)
    lowered = re.sub(r"[^\w\s]", " ", lowered)
    return re.sub(r"\s+", " ", lowered).strip()


def without_age_band(text: str) -> str:
    """ "1. Stadtklasse Ü35" -> "1. Stadtklasse"."""
    return re.sub(r"\s+", " ", _AGE_BAND_RE.sub("", text or "")).strip()


def expand_candidates(candidates: list[str]) -> list[str]:
    """Add the age-band-free form of each candidate, keeping the order.

    The band lives in the Mannschaftsart dropdown, so a Spielklasse candidate
    that still carries it can only match the shorter option.
    """
    out: list[str] = []
    for name in candidates:
        name = (name or "").strip()
        if not name or name in out:
            continue
        out.append(name)
        kurz = without_age_band(name)
        if kurz and kurz != name and kurz not in out:
            out.append(kurz)
    return out


#: DFBnet's "nothing selected" entries. Picking one clears the filter and the
#: search then returns every competition — the exact failure this module exists
#: to prevent, so they are never candidates for a match.
PLATZHALTER = frozenset({"keine auswahl", "bitte wahlen", "bitte auswahlen", "alle", ""})


def ist_platzhalter(option: str) -> bool:
    return normalise(option) in PLATZHALTER


def best_option(options: list[str], candidates: list[str], exact: bool = False) -> str | None:
    """Return the option to click, or None.

    Passes, in order:

    1. an exact match after normalisation,
    2. the candidate contained in an option ("Kreisliga" in "3. Kreisliga (C)"),
    3. an option contained in the candidate ("1. Stadtklasse" in
       "1. Stadtklasse Ü35") — only when exactly one option qualifies, so
       "1. Stadtklasse" can never silently win against "11. Stadtklasse".

    `exact` stops after the first pass; the Mannschaftsart uses it so that
    "Herren" cannot swallow "Herren Ü35".
    """
    normalised = [(option, normalise(option)) for option in options if not ist_platzhalter(option)]

    for name in candidates:
        ziel = normalise(name)
        if not ziel:
            continue
        for option, norm in normalised:
            if norm == ziel:
                return option

    if exact:
        return None

    # Both containment passes demand a unique hit. "Stadtklasse" sits inside
    # "1.", "2." and "11. Stadtklasse" alike, and picking the first of three is
    # how a check run ends up silently looking at the wrong league.
    for name in candidates:
        ziel = normalise(name)
        if not ziel:
            continue
        treffer = [option for option, norm in normalised if ziel in norm]
        if len(treffer) == 1:
            return treffer[0]

    for name in candidates:
        ziel = normalise(name)
        if not ziel:
            continue
        treffer = [option for option, norm in normalised if norm and norm in ziel]
        if len(treffer) == 1:
            return treffer[0]

    return None


#: Kandidaten fuer das Feld "Mannschaftsart", je Altersklasse.
#:
#: DFBnet benutzt denselben Spielklassennamen ("1.Kreisklasse") fuer Herren und
#: Ue35 -- die Spielklasse allein waehlt also den falschen Wettbewerb. Die
#: Mannschaftsart trennt sie. Mehrere Schreibweisen, weil die Beschriftung sich
#: zwischen Verbaenden unterscheidet; die erste, die im Feld auftaucht, gewinnt.
MANNSCHAFTSART_KANDIDATEN: dict[str, list[str]] = {
    "maenner": ["Herren"],
    "herren": ["Herren"],
    "frauen": ["Frauen"],
    "ue32": ["Herren Ü32", "Ü32", "Ü 32"],
    "ue35": ["Herren Ü35", "Ü35", "Ü 35", "Alte Herren"],
    "ue40": ["Herren Ü40", "Ü40", "Ü 40"],
}


def mannschaftsart_kandidaten(altersklasse: str) -> list[str]:
    """Die Texte, die fuer diese Altersklasse zu versuchen sind."""
    return MANNSCHAFTSART_KANDIDATEN.get((altersklasse or "").strip().lower(), [])
