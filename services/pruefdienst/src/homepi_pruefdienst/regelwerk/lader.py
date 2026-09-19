"""Regeldateien laden und ausführen.

Die Dateien liegen in `config/regeln/` — beim Staffelleiter, nicht im
Programm. Sie überleben ein Update der .exe, und sie zu ändern heißt nicht,
StaffelPilot zu ändern.

Zwei Entscheidungen prägen alles hier:

**Der Namensraum wird gestellt, nicht importiert.** Eine Regeldatei beginnt
nicht mit sechs `from …`-Zeilen. `regel`, `melde`, `ANZAHL` und die
Datumshilfen sind einfach da. Ein Linter versteht das nicht — eine
Konfigurationsdatei ist aber auch kein Modul, und der Preis ist eine Warnung im
Editor gegen sechs Zeilen Zeremonie in jeder Datei.

**Ein Fehler legt genau eine Regel still, laut.** Eine kaputte Regel liefert je
Spiel den Befund „Regel X ist fehlerhaft", alle anderen laufen weiter. Der
Gegenentwurf — stillschweigend überspringen — ist genau das Versagen, gegen das
dieses Programm existiert: eine Prüfung, die nicht mehr prüft und nichts sagt.
"""

from __future__ import annotations

import logging
import sys
import traceback
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from pathlib import Path

from .dekorator import Registry, Sammler
from .ordner import regelordner
from .spiel import datum_lesen

logger = logging.getLogger(__name__)


def _vorlagenordner() -> Path:
    """Wo die mitgelieferten Regeln liegen — im Quellbaum wie in der .exe.

    In der gepackten Anwendung liegen sie unter `sys._MEIPASS`, weil sie über
    `datas` mitgeliefert werden und nicht im Code-Archiv stehen. Findet der
    Lader sie nicht, rollt er nichts aus, lädt keine Regel und prüft nichts —
    lautlos. Deshalb werden beide Orte gesucht.
    """
    neben_dem_modul = Path(__file__).resolve().parent / "vorlagen"
    if neben_dem_modul.is_dir():
        return neben_dem_modul
    gepackt = getattr(sys, "_MEIPASS", "")
    if gepackt:
        im_bundle = Path(gepackt) / "src" / "rules" / "regelwerk" / "vorlagen"
        if im_bundle.is_dir():
            return im_bundle
    return neben_dem_modul


#: Die mitgelieferten Regeln. Werden nach `config/regeln/` kopiert, wenn dort
#: noch nichts liegt — danach gehören sie ihm und werden nie überschrieben.
VORLAGEN = _vorlagenordner()


@dataclass
class Befund:
    """Was eine Regel gemeldet hat."""

    regel: str
    nachricht: str
    person: str = ""
    mannschaft: str = ""
    details: dict = field(default_factory=dict)


@dataclass
class Ladung:
    """Das Ergebnis eines Ladevorgangs."""

    registry: Registry = field(default_factory=Registry)
    #: Dateien, die sich nicht laden ließen: Pfad → Fehlertext.
    fehler: dict[str, str] = field(default_factory=dict)
    ordner: Path | None = None

    @property
    def anzahl(self) -> int:
        return len(self.registry)


def _hilfsmittel(sammler: Sammler) -> dict:
    """Was in einer Regeldatei ohne Import zur Verfügung steht."""
    return {
        "regel": sammler.dekorator(),
        # Vokabeln, die sich in einer Regel lesen wie im Regeltext.
        "ANZAHL": len,
        "SUMME": sum,
        "IRGENDEINER": any,
        "ALLE": all,
        "SORTIERT": sorted,
        "datum_lesen": datum_lesen,
        "date": date,
        "datetime": datetime,
        "timedelta": timedelta,
    }


def _laden(pfad: Path, ladung: Ladung) -> None:
    sammler = Sammler(quelle=pfad.name)
    namensraum = _hilfsmittel(sammler)
    namensraum["__file__"] = str(pfad)
    namensraum["__name__"] = f"regeln.{pfad.stem}"
    try:
        code = compile(pfad.read_text(encoding="utf-8"), str(pfad), "exec")
        exec(code, namensraum)
    except Exception as fehler:
        ladung.fehler[pfad.name] = f"{type(fehler).__name__}: {fehler}"
        logger.exception("Regeldatei %s ließ sich nicht laden", pfad.name)
        return
    for regel in sammler.regeln:
        ladung.registry.hinzufuegen(regel)


def vorlagen_ausrollen(ziel: Path | None = None) -> list[str]:
    """Die mitgelieferten Regeln einmalig hinterlegen. Nie überschreiben.

    Was der Staffelleiter angepasst hat, bleibt — auch wenn eine neue Version
    von StaffelPilot die Vorlage geändert hat. Eine Aktualisierung, die eine
    von Hand geschärfte Regel zurücksetzt, ist schlimmer als eine veraltete
    Vorlage, weil sie nichts sagt.
    """
    ziel = ziel or regelordner()
    ziel.mkdir(parents=True, exist_ok=True)
    neu: list[str] = []
    if not VORLAGEN.is_dir():
        return neu
    for vorlage in sorted(VORLAGEN.glob("*.py")):
        ablage = ziel / vorlage.name
        if ablage.exists():
            continue
        ablage.write_text(vorlage.read_text(encoding="utf-8"), encoding="utf-8")
        neu.append(vorlage.name)
    if neu:
        logger.info("Regelvorlagen angelegt: %s", ", ".join(neu))
    return neu


def laden(ordner: Path | None = None, *, ausrollen: bool = True) -> Ladung:
    """Alle Regeldateien eines Ordners laden.

    Nach Dateinamen sortiert, damit die Reihenfolge nachvollziehbar ist: `10_`
    vor `20_`, und eine `90_eigene.py` kann am Ende gezielt etwas ersetzen.
    """
    ordner = ordner or regelordner()
    if ausrollen:
        vorlagen_ausrollen(ordner)

    ladung = Ladung(ordner=ordner)
    if not ordner.is_dir():
        logger.warning("Kein Regelordner unter %s", ordner)
        return ladung

    for pfad in sorted(ordner.glob("*.py")):
        if pfad.name.startswith("_"):
            continue
        _laden(pfad, ladung)

    logger.info(
        "%d Regel(n) aus %s geladen, %d Datei(en) fehlerhaft",
        ladung.anzahl,
        ordner,
        len(ladung.fehler),
    )
    return ladung


def ausfuehren(regel, spiel) -> tuple[list[Befund], str]:
    """Eine Regel auf ein Spiel anwenden.

    Gibt die Befunde und — falls die Regel gestolpert ist — den Fehlertext
    zurück. Der Aufrufer entscheidet, was daraus wird; hier wird nichts
    verschluckt und nichts geworfen.
    """
    befunde: list[Befund] = []

    def melde(nachricht: str, *, person: str = "", mannschaft: str = "", **details) -> None:
        befunde.append(
            Befund(
                regel=regel.id,
                nachricht=str(nachricht),
                person=str(person or ""),
                mannschaft=str(mannschaft or ""),
                details=details,
            )
        )

    try:
        regel.funktion(spiel, melde)
    except Exception as fehler:
        logger.exception("Regel %s ist gestolpert", regel.name)
        zeile = ""
        for rahmen in traceback.extract_tb(fehler.__traceback__):
            if rahmen.filename.endswith(regel.quelle):
                zeile = f" (Zeile {rahmen.lineno})"
        return befunde, f"{type(fehler).__name__}: {fehler}{zeile}"

    return befunde, ""
