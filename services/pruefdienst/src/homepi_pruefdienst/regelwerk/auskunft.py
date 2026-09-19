"""Was eine Regel über das einzelne Spiel hinaus erfahren darf.

§ 58 rechnet über die Saison: die 5. Verwarnung, der Rhythmus 5–10–15 nach
jeder verwirkten Sperre, die Trennung zwischen Pokal und übrigen
Pflichtspielen. Nichts davon steht im Spielbericht.

Zwei Entscheidungen halten das beherrschbar:

**Nur lesen.** Die Schnittstelle hat kein einziges schreibendes Verfahren. Eine
Regeldatei, die schreiben könnte, machte die Reihenfolge der Regeln zu einem
Teil des Ergebnisses — und niemand würde merken, wann sie es tut.

**`None` heißt „weiß ich nicht", nicht „null".** Ohne Datenbank oder ohne
Passnummer gibt es keine Zahl. Eine 0 wäre eine Behauptung — „diese Person hat
keine Verwarnungen" —, und eine Regel, die daraufhin schweigt, sähe aus, als
hätte sie geprüft.
"""

from __future__ import annotations

from datetime import date


class Auskunft:
    """Die Schnittstelle. Absichtlich winzig und ohne Schreibweg."""

    def verwarnungen(self, pass_nr: str, wettbewerb: str, seit: date | None = None) -> int | None:
        """Verwarnungen dieser Person in diesem Wettbewerb, oder `None`."""
        return None

    def letzte_sperre(self, pass_nr: str, wettbewerb: str) -> date | None:
        """Wann zuletzt eine Sperre verwirkt wurde, oder `None`."""
        return None
