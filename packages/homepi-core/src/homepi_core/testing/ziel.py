from __future__ import annotations

import os
import tomllib
from dataclasses import dataclass
from pathlib import Path

STANDARD_URL = "http://127.0.0.1:8000"
KONFIGDATEI = "homepi.toml"


@dataclass(frozen=True, slots=True)
class Ziel:
    name: str
    basis_url: str
    timeout: float = 5.0
    #: Bei selbst signierten Zertifikaten auf false setzen. Fuer den Pi mit
    #: Let's-Encrypt-Wildcard ist das nicht noetig - und sollte es auch nicht
    #: sein, sonst prueft der Test die TLS-Einrichtung nicht mit.
    tls_pruefen: bool = True

    @property
    def ist_lokal(self) -> bool:
        return "127.0.0.1" in self.basis_url or "localhost" in self.basis_url


def _konfig_finden(start: Path) -> Path | None:
    aktuell = start.resolve()
    while True:
        kandidat = aktuell / KONFIGDATEI
        if kandidat.is_file():
            return kandidat
        if aktuell == aktuell.parent:
            return None
        aktuell = aktuell.parent


def ziele_lesen(start: Path | None = None) -> dict[str, Ziel]:
    datei = _konfig_finden(start or Path.cwd())
    if datei is None:
        return {}

    daten = tomllib.loads(datei.read_text(encoding="utf-8"))
    roh = daten.get("ziele", {})
    if not isinstance(roh, dict):
        return {}

    ziele: dict[str, Ziel] = {}
    for name, eintrag in roh.items():
        if not isinstance(eintrag, dict) or "basis_url" not in eintrag:
            continue
        ziele[name] = Ziel(
            name=name,
            basis_url=str(eintrag["basis_url"]).rstrip("/"),
            timeout=float(eintrag.get("timeout", 5.0)),
            tls_pruefen=bool(eintrag.get("tls_pruefen", True)),
        )
    return ziele


def ziel_aus_umgebung(start: Path | None = None) -> Ziel:
    if url := os.environ.get("HOMEPI_BASIS_URL"):
        return Ziel(name="umgebung", basis_url=url.rstrip("/"))

    ziele = ziele_lesen(start)
    gewuenscht = os.environ.get("HOMEPI_ZIEL")

    if gewuenscht:
        if gewuenscht not in ziele:
            bekannt = ", ".join(sorted(ziele)) or "keine"
            raise RuntimeError(
                f"HOMEPI_ZIEL='{gewuenscht}' steht nicht in {KONFIGDATEI}. "
                f"Bekannte Ziele: {bekannt}"
            )
        return ziele[gewuenscht]

    if "standard" in ziele:
        return ziele["standard"]

    return Ziel(name="notnagel", basis_url=STANDARD_URL)
