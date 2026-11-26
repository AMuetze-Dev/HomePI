"""Kriterienkatalog und Notentabelle der IHK-Vorlage.

Die beiden JSON-Dateien in ``katalog/`` werden nicht von Hand gepflegt: Sie
stammen aus ``TEMPLATE.xlsm`` und wurden im ExamManager V2 mit
``tools/extract_template.py`` erzeugt. Wer den Katalog ändern will, ändert die
Vorlage und erzeugt neu - sonst rechnet HomePI anders als der Bogen der IHK.

Gelesen wird einmal beim Import. Das ist konstante Paketlage, kein I/O im
Sinne der Schichtung: Der Rechenkern bleibt ohne Datenbank testbar.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from importlib.resources import files
from typing import Any, Literal

Art = Literal["points", "malus", "group", "scale"]


@dataclass(frozen=True, slots=True)
class Knoten:
    id: str
    label: str
    art: Art
    max: int | None = None
    hinweis: str = ""
    kinder: tuple[Knoten, ...] = ()


@dataclass(frozen=True, slots=True)
class Sektion:
    id: str
    nr: str
    label: str
    max: int
    kinder: tuple[Knoten, ...]


@dataclass(frozen=True, slots=True)
class Bereich:
    id: str
    label: str
    gewicht: int


@dataclass(frozen=True, slots=True)
class Gesamtschema:
    teil1_label: str
    teil1_gewicht: int
    teil2_divisor: int
    bereiche: tuple[Bereich, ...]
    projekt_label: str
    projekt_gewicht: int
    projekt_divisor: int
    gesamt_divisor: int


@dataclass(frozen=True, slots=True)
class Katalog:
    doku: tuple[Sektion, ...]
    praesentation: tuple[Sektion, ...]
    gesamt: Gesamtschema
    praesi_grenze_min: int
    gesamt_grenze_min: int
    doku_blaetter: tuple[Knoten, ...] = field(default=())
    praesi_blaetter: tuple[Knoten, ...] = field(default=())


@dataclass(frozen=True, slots=True)
class Noten:
    tabelle: dict[int, float]
    grenzfaelle: tuple[int, ...]
    skala: tuple[float, ...]
    korrekturarten: tuple[str, ...]


def blaetter(knoten: Knoten | Sektion) -> list[Knoten]:
    """Alle bewertbaren Blätter in Bogenreihenfolge. Gruppen tragen nur Aufbau."""
    if isinstance(knoten, Knoten) and not knoten.kinder:
        return [] if knoten.art == "group" else [knoten]
    return [blatt for kind in knoten.kinder for blatt in blaetter(kind)]


def _knoten(roh: dict[str, Any]) -> Knoten:
    return Knoten(
        id=roh["id"],
        label=roh["label"],
        art=roh["kind"],
        max=roh.get("max"),
        hinweis=roh.get("hint", ""),
        kinder=tuple(_knoten(k) for k in roh.get("children", [])),
    )


def _sektion(roh: dict[str, Any]) -> Sektion:
    return Sektion(
        id=roh["id"],
        nr=roh["no"],
        label=roh["label"],
        max=roh["max"],
        kinder=tuple(_knoten(k) for k in roh["children"]),
    )


def _lade(name: str) -> dict[str, Any]:
    daten: dict[str, Any] = json.loads(
        files("homepi_ihk").joinpath("katalog", name).read_text(encoding="utf-8")
    )
    return daten


def _katalog(roh: dict[str, Any]) -> Katalog:
    doku = tuple(_sektion(s) for s in roh["doku"]["sections"])
    praesi = tuple(_sektion(s) for s in roh["praesentation"]["sections"])
    g = roh["gesamt"]
    t2 = g["teil2"]
    return Katalog(
        doku=doku,
        praesentation=praesi,
        gesamt=Gesamtschema(
            teil1_label=g["teil1"]["label"],
            teil1_gewicht=g["teil1"]["weight"],
            teil2_divisor=t2["divisor"],
            bereiche=tuple(Bereich(b["id"], b["label"], b["weight"]) for b in t2["bereiche"]),
            projekt_label=t2["projekt"]["label"],
            projekt_gewicht=t2["projekt"]["weight"],
            projekt_divisor=t2["projekt"]["divisor"],
            gesamt_divisor=g["gesamt"]["divisor"],
        ),
        praesi_grenze_min=roh["timing"]["praesentation"]["limit_min"],
        gesamt_grenze_min=roh["timing"]["fachgespraech"]["limit_min"],
        doku_blaetter=tuple(b for s in doku for b in blaetter(s)),
        praesi_blaetter=tuple(b for s in praesi for b in blaetter(s)),
    )


def _noten(roh: dict[str, Any]) -> Noten:
    return Noten(
        tabelle={int(k): float(v) for k, v in roh["table"].items()},
        grenzfaelle=tuple(roh["borderline"]),
        skala=tuple(float(s) for s in roh["scale"]),
        korrekturarten=tuple(roh["korrekturarten"]),
    )


KATALOG = _katalog(_lade("kriterien.json"))
NOTEN = _noten(_lade("noten.json"))
