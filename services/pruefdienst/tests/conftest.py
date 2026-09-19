"""Kein Test fasst den echten Regelordner an.

Die Vorgabe ist `/data/regeln` -- im Container ein Band, auf diesem Rechner
`D:/data/regeln`. Ein Testlauf, der dort die Vorlagen ausrollt, schreibt
ausserhalb des Projekts und nimmt beim naechsten Mal genau die Dateien, die er
selbst hinterlassen hat. Beides ist falsch, und das zweite faellt erst auf,
wenn ein Test gruen ist, der es nicht sein duerfte.
"""

from __future__ import annotations

from pathlib import Path

import pytest


@pytest.fixture(autouse=True)
def eigener_regelordner(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PRUEFDIENST_REGELN", str(tmp_path / "regeln"))

    # Der Zwischenspeicher ist prozessweit: ohne das Leeren sieht der naechste
    # Test die Regeln des vorigen -- aus einem Ordner, den es nicht mehr gibt.
    from homepi_pruefdienst import katalog

    katalog.zuruecksetzen()
