"""Die Brücke zwischen den anpassbaren Regeln und dem Rest des Dienstes.

Die Regeldateien liefern `Befund`e in der Sprache der Spielordnung; hier
werden sie zu `regeln.Violation` — derselben Form, die auch die eingebauten
Regeln liefern. Damit gibt es eine Übersetzung und nicht zwei.

Übernommen aus `D:/DevLibrary/StaffelPilot/src/rules/regelbruecke.py`.

Der Ladevorgang passiert **einmal je Prüflauf**, nicht je Spiel: achtzig
Spiele würden sonst achtzigmal dieselben Dateien übersetzen. Der
Zwischenspeicher merkt sich die Änderungszeiten, damit eine geänderte Regel
trotzdem ohne Neustart greift — wer eine Regel anpasst, will sie im nächsten
Lauf sehen und nicht morgen.
"""

from __future__ import annotations

import logging
import threading
from collections.abc import Collection
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from . import regelwerk
from .bericht import MatchReport
from .regeln import Severity, Violation, als_befund
from .regelwerk import Ladung, ausfuehren, laden, schalter, uebersetzen

logger = logging.getLogger(__name__)

#: Die Schwere-Namen der Regeldateien auf die der übrigen Prüfung.
SCHWERE_ZU_SEVERITY = {
    "hinweis": Severity.INFO,
    "warnung": Severity.WARNING,
    "kritisch": Severity.CRITICAL,
}

_sperre = threading.Lock()
_zwischenspeicher: tuple[tuple[Any, ...], Ladung] | None = None


@dataclass
class Staffelangabe:
    """Was die Regeln über die Staffel wissen müssen.

    Genau die Felder, die `regelwerk.Staffel` liest. Ein eigener kleiner Typ
    und nicht das Schema des Artefakts: die Regeln sollen nicht davon
    abhängen, wie eine Staffel über HTTP aussieht.
    """

    name: str = ""
    #: "maenner", "frauen", "ue32", "ue35", "ue40"
    altersklasse: str = ""
    saison: str = ""
    #: 0 heißt *nicht bekannt*. Die Regel `spieltage_unbekannt` sagt das dann
    #: selbst — stillschweigend zu rechnen wäre die schlechtere Hälfte.
    spieltage: int = 0
    hoehere_mannschaften: tuple[str, ...] = field(default_factory=tuple)


def _fingerabdruck(ordner: Path) -> tuple[Any, ...]:
    """Name und Änderungszeit jeder Regeldatei.

    Reicht für „hat sich etwas geändert" und kostet einen Verzeichniszugriff
    statt eines Neuladens.
    """
    if not ordner.is_dir():
        return ()
    return tuple(sorted((p.name, p.stat().st_mtime_ns) for p in ordner.glob("*.py")))


def regeln(ordner: Path | None = None, *, neu_laden: bool = False) -> Ladung:
    """Die geladenen Regeln, aus dem Zwischenspeicher wenn unverändert.

    Der Schlüssel ist Ordner **und** Fingerabdruck. Nur der Fingerabdruck
    reichte nicht: zwei verschiedene, beide noch leere Ordner haben denselben
    (nämlich keinen), und dann bekam der zweite die Regeln des ersten — also
    keine.
    """
    global _zwischenspeicher

    ordner = ordner or regelwerk.regelordner()
    with _sperre:
        schluessel = (str(ordner), _fingerabdruck(ordner))
        if not neu_laden and _zwischenspeicher and _zwischenspeicher[0] == schluessel:
            return _zwischenspeicher[1]
        ladung = laden(ordner)
        _zwischenspeicher = ((str(ordner), _fingerabdruck(ordner)), ladung)
        return ladung


def zuruecksetzen() -> None:
    """Zwischenspeicher leeren. Für Tests und nach dem Ändern einer Regel."""
    global _zwischenspeicher
    with _sperre:
        _zwischenspeicher = None


def _fehlerbefund(name: str, text: str, quelle: str) -> Violation:
    """Eine Regel, die nicht läuft, muss lauter sein als eine, die nichts findet.

    Deshalb kritisch und nicht nur ein Protokolleintrag: ein Spiel mit
    kritischem Befund lässt sich nicht abhaken. Ein stiller Ausfall sähe aus
    wie ein sauberes Spiel — und genau so verschwindet eine Prüfung, ohne dass
    es jemand merkt.
    """
    return Violation(
        rule="regel_fehlerhaft",
        severity=Severity.CRITICAL,
        message=(f"Regel '{name}' aus {quelle} ist fehlerhaft und wurde übersprungen: {text}"),
        details={"regel": name, "quelle": quelle, "fehler": text},
    )


def pruefen(
    report: MatchReport,
    staffel: Staffelangabe | None = None,
    ordner: Path | None = None,
    auskunft: regelwerk.Auskunft | None = None,
    abgeschaltet: Collection[str] = (),
) -> list[Violation]:
    """Alle Regeln aus den Regeldateien auf einen Spielbericht anwenden.

    `auskunft` reicht den lesenden Zugang zu Verwarnungszähler und Sperren
    durch. Ohne sie antworten die betreffenden Vokabeln `None`, und die
    Regeln, die darauf bauen, schweigen — sichtbar, weil sie es selbst melden.
    """
    ladung = regeln(ordner)

    verstoesse: list[Violation] = [
        _fehlerbefund("(ganze Datei)", text, datei) for datei, text in sorted(ladung.fehler.items())
    ]

    if ladung.anzahl == 0:
        # Kein Ordner, kein Schreibrecht, nichts ausgerollt: dreissig Regeln
        # sind weg, und der Bericht saehe geprueft aus. Das muss laut sein.
        verstoesse.append(
            _fehlerbefund(
                "(keine)",
                f"Aus {ladung.ordner} wurde keine einzige Regel geladen",
                str(ladung.ordner),
            )
        )
        return verstoesse

    try:
        spiel = uebersetzen(report, staffel, auskunft)
    except Exception as fehler:
        logger.exception("Der Spielbericht liess sich nicht fuer die Regeln aufbereiten")
        verstoesse.append(
            Violation(
                rule="regel_fehlerhaft",
                severity=Severity.CRITICAL,
                message=(
                    "Der Spielbericht ließ sich nicht für die Regelprüfung "
                    f"aufbereiten: {type(fehler).__name__}: {fehler}"
                ),
                details={"fehler": str(fehler)},
            )
        )
        return verstoesse

    # Zwei Quellen, und beide zaehlen: die Regeluebersicht der Oberflaeche
    # und die Datei neben den Regeln. Wer ohne Oberflaeche arbeitet, soll
    # trotzdem abschalten koennen.
    stillgelegt = set(abgeschaltet) | set(schalter.laden())
    for regel in ladung.registry:
        if regel.id in stillgelegt:
            # Nicht ausfuehren, aber auch nicht verschweigen: die Zahl steht
            # im Protokoll des Prueflaufs.
            continue
        befunde, fehler_text = ausfuehren(regel, spiel)
        if fehler_text:
            verstoesse.append(_fehlerbefund(regel.name, fehler_text, regel.quelle))
        for befund in befunde:
            einzelheiten = dict(befund.details)
            # Der Anzeigename reist mit: so bleibt ein gespeicherter Befund
            # lesbar, auch wenn die Regel laengst umbenannt oder geloescht ist.
            einzelheiten.setdefault("regelname", regel.name)
            if befund.person:
                einzelheiten.setdefault("person", befund.person)
                einzelheiten.setdefault("player", befund.person)
            if befund.mannschaft:
                einzelheiten.setdefault("team", befund.mannschaft)
            if regel.paragraf:
                einzelheiten.setdefault("paragraf", regel.paragraf)
            # Die Mannschaft gehoert in die Meldung, nicht nur in die Details:
            # in der Liste steht der Text allein, und "Mueller ist 19" ohne
            # Verein zwingt zum Oeffnen des Spiels.
            text = befund.nachricht
            if befund.mannschaft and not text.startswith(befund.mannschaft):
                text = f"{befund.mannschaft}: {text}"
            verstoesse.append(
                Violation(
                    rule=regel.id,
                    severity=SCHWERE_ZU_SEVERITY.get(regel.schwere, Severity.WARNING),
                    message=text,
                    details=einzelheiten,
                )
            )
    return verstoesse


#: Die Wege der Regeldateien auf die des Artefakts.
#:
#: Das Artefakt kennt drei: kein Schreiben, Mahnung, Sportgericht. Die
#: Regeldateien kennen "beides" -- Mahnung **und** Sportgericht. Es wird zur
#: Mahnung: der Weg, der ohne Verfahren auskommt. Betroffen sind die drei
#: Spielerfoto-Regeln, und das Mahnungsformular des Verbandes hat fuer sie ein
#: eigenes Feld. Wer eine davon vor das Sportgericht bringen will, stellt sie
#: in der Regeluebersicht um.
_WEG_IM_ARTEFAKT = {
    "sportgericht": "sportgericht",
    "mahnung": "mahnung",
    "beides": "mahnung",
    "hinweis": "kein",
}


def katalog(ordner: Path | None = None) -> list[dict[str, str]]:
    """Die Regeln des Staffelleiters, wie der Regelkatalog sie fuehrt."""
    return [
        {
            "schluessel": r.id,
            "name": r.name,
            "beschreibung": (getattr(r, "beschreibung", "") or "")[:1000],
            "schwere": r.schwere,
            "weg": _WEG_IM_ARTEFAKT.get(r.weg, "kein"),
        }
        for r in regeln(ordner).registry
    ]


def befunde_aus(
    report: MatchReport,
    staffel: Staffelangabe | None = None,
    ordner: Path | None = None,
    auskunft: regelwerk.Auskunft | None = None,
    abgeschaltet: Collection[str] = (),
) -> list[dict[str, object]]:
    """Die Regeln des Katalogs, fertig für das Artefakt."""
    aus = set(abgeschaltet)
    return [
        als_befund(v)
        for v in pruefen(report, staffel, ordner, auskunft, abgeschaltet=aus)
        if v.rule not in aus
    ]


def _ganzzahl(wert: object) -> int:
    """Eine Zahl, oder 0 fuer alles andere -- also *nicht bekannt*.

    Das Artefakt liefert einen `int`; wer sich darauf verlaesst, bekommt beim
    ersten `null` einen Abbruch mitten im Lauf.
    """
    if isinstance(wert, bool) or not isinstance(wert, int | float | str):
        return 0
    try:
        return int(wert)
    except ValueError:
        return 0


def staffelangabe(staffel: dict[str, object]) -> Staffelangabe:
    """Aus der Staffel des Artefakts das, was die Regeln lesen.

    `hoehere_mannschaften` bleibt leer: das Artefakt führt sie je Mannschaft
    und nicht je Staffel. Der Übersetzer erschließt sie dann aus den Namen --
    "SV Loschwitz" steht über "SV Loschwitz 2". Das ist die Rückfallebene der
    alten Anwendung und nicht das Ende der Arbeit; die gepflegte Liste kennt
    Spielgemeinschaften, die aus einem Namen nicht abzulesen sind.
    """
    return Staffelangabe(
        name=str(staffel.get("name") or ""),
        altersklasse=str(staffel.get("altersklasse") or ""),
        saison=str(staffel.get("saison") or ""),
        spieltage=_ganzzahl(staffel.get("spieltage")),
    )
