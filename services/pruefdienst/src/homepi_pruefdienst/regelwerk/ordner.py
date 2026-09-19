"""Wo die Regeln des Staffelleiters liegen.

Eine eigene, winzige Datei, damit `lader` und `schalter` sich nicht
gegenseitig importieren muessen.

In der alten Anwendung war das ein Ordner neben der .exe. Hier ist es ein
Pfad aus der Umgebung: im Container ein Band (Volume), das den Neustart und
das naechste Abbild ueberlebt. Ohne ihn waeren die angepassten Regeln nach
jedem `docker compose up --build` wieder die Vorlagen.
"""

from __future__ import annotations

import os
from pathlib import Path

#: Woher der Pfad kommt.
UMGEBUNG = "PRUEFDIENST_REGELN"

#: Wo er im Container liegt, wenn nichts gesagt wird.
VORGABE = "/data/regeln"


def regelordner() -> Path:
    return Path(os.environ.get(UMGEBUNG) or VORGABE)
