"""Hilfen für den Umgang mit externen Programmen. Nur Standardbibliothek."""

from __future__ import annotations

import shutil
import subprocess
import sys
from dataclasses import dataclass


class CliFehler(RuntimeError):
    """Ein Problem, das der Benutzer beheben kann - kein Stacktrace nötig."""


@dataclass(frozen=True)
class Ergebnis:
    code: int
    ausgabe: str
    fehler: str

    @property
    def erfolg(self) -> bool:
        return self.code == 0


def lauf(*befehl: str, cwd: str | None = None, pflicht: bool = True) -> Ergebnis:
    if shutil.which(befehl[0]) is None:
        raise CliFehler(f"'{befehl[0]}' ist nicht installiert oder nicht im PATH.")

    fertig = subprocess.run(
        befehl,
        cwd=cwd,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    ergebnis = Ergebnis(fertig.returncode, fertig.stdout.strip(), fertig.stderr.strip())

    if pflicht and not ergebnis.erfolg:
        raise CliFehler(
            f"'{' '.join(befehl)}' ist fehlgeschlagen (Code {ergebnis.code}):\n"
            f"{ergebnis.fehler or ergebnis.ausgabe}"
        )
    return ergebnis


def durchreichen(*befehl: str, cwd: str | None = None) -> int:
    """Ausgabe direkt ans Terminal - für lang laufende Befehle wie 'gh run watch',
    bei denen man den Fortschritt sehen will."""
    if shutil.which(befehl[0]) is None:
        raise CliFehler(f"'{befehl[0]}' ist nicht installiert oder nicht im PATH.")
    return subprocess.call(befehl, cwd=cwd)


# --- Ausgabe ---------------------------------------------------------------

_FARBEN = sys.stdout.isatty()


def _farbe(text: str, code: str) -> str:
    return f"\033[{code}m{text}\033[0m" if _FARBEN else text


def schritt(text: str) -> None:
    print(_farbe(f"==> {text}", "1;36"))


def hinweis(text: str) -> None:
    print(f"    {text}")


def warnung(text: str) -> None:
    print(_farbe(f"    ! {text}", "1;33"))


def erfolg(text: str) -> None:
    print(_farbe(f"    + {text}", "1;32"))


def fehler(text: str) -> None:
    print(_farbe(f"FEHLER: {text}", "1;31"), file=sys.stderr)
