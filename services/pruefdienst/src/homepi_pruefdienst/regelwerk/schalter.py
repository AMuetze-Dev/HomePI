"""Welche Regeln abgeschaltet sind.

Gespeichert in `config/regeln/abgeschaltet.yaml`, **nicht** in der Regeldatei
selbst. Die gehört dem Staffelleiter; ein Programm, das darin herumschreibt,
zerstört früher oder später eine Anpassung — und sei es nur die Formatierung.

Eine abgeschaltete Regel ist nicht dasselbe wie eine gelöschte. Sie bleibt in
der Übersicht sichtbar, grau, mit dem Datum der Abschaltung. Der Prüflauf nennt
ihre Zahl im Protokoll. Der Gegenentwurf — eine Regel verschwindet einfach —
ist genau der stille Ausfall, gegen den dieses Programm gebaut ist.
"""

from __future__ import annotations

import logging
from datetime import date
from pathlib import Path

import yaml

from .ordner import regelordner

logger = logging.getLogger(__name__)

DATEINAME = "abgeschaltet.yaml"

KOPF = """# Abgeschaltete Regeln
#
# Von StaffelPilot geschrieben, wenn Sie in der Regelübersicht einen Schalter
# umlegen. Kann auch von Hand bearbeitet werden — je Zeile eine Regelkennung.
#
# Eine abgeschaltete Regel bleibt in der Übersicht sichtbar und wird im
# Prüfprotokoll mitgezählt. Sie prüft nur nichts mehr.
"""


def datei() -> Path:
    return regelordner() / DATEINAME


def laden(pfad: Path | None = None) -> dict[str, str]:
    """Kennung → Datum der Abschaltung. Leeres Ergebnis bei jedem Problem."""
    pfad = pfad or datei()
    if not pfad.is_file():
        return {}
    try:
        daten = yaml.safe_load(pfad.read_text(encoding="utf-8")) or {}
    except yaml.YAMLError:
        logger.exception("abgeschaltet.yaml nicht lesbar — alle Regeln bleiben an")
        return {}
    if isinstance(daten, list):
        # Von Hand geschrieben, ohne Datum. Auch das ist gültig.
        return {str(k): "" for k in daten if k}
    if not isinstance(daten, dict):
        return {}
    return {str(k): str(v or "") for k, v in daten.items() if k}


def speichern(abgeschaltet: dict[str, str], pfad: Path | None = None) -> None:
    pfad = pfad or datei()
    pfad.parent.mkdir(parents=True, exist_ok=True)
    text = KOPF
    if abgeschaltet:
        text += yaml.safe_dump(
            dict(sorted(abgeschaltet.items())), allow_unicode=True, sort_keys=False
        )
    else:
        text += "{}\n"
    pfad.write_text(text, encoding="utf-8")


def umschalten(kennung: str, aktiv: bool, pfad: Path | None = None) -> dict[str, str]:
    """Eine Regel an- oder abschalten. Gibt den neuen Stand zurück."""
    stand = laden(pfad)
    if aktiv:
        stand.pop(kennung, None)
    else:
        stand[kennung] = date.today().isoformat()
    speichern(stand, pfad)
    logger.info("Regel %s %s", kennung, "eingeschaltet" if aktiv else "abgeschaltet")
    return stand
