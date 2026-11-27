"""Der Vertrag nach außen.

Was hier steht, landet im OpenAPI-Schema. Die Grenzen, die schon an der Form
einer Anfrage hängen (0 bis 100, bekannte Korrekturart), prüft Pydantic; alles,
was den Kriterienkatalog braucht, prüft ``dienst.aendere_bewertung``.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


def _trimmen(wert: object) -> object:
    return wert.strip() if isinstance(wert, str) else wert


NameFeld = Annotated[str, Field(min_length=1, max_length=100)]
KurzText = Annotated[str, Field(max_length=100)]
Punkte = Annotated[int, Field(ge=0, le=100)]
Bemerkung = Annotated[str, Field(max_length=4000)]
Korrekturart = Literal["Erstkorrektur", "Zweitkorrektur", "Information"]
MepBereich = Literal["planen_softwareprodukt", "algorithmen", "wiso"]
DokumentArt = Literal["projekt", "kunde"]


# ── Prüfungstage ─────────────────────────────────────────────────────────────


class TagAnlegen(BaseModel):
    datum: date
    ort: KurzText = ""
    korrektor: KurzText = ""

    _trim = field_validator("ort", "korrektor", mode="before")(_trimmen)


class TagAendern(BaseModel):
    datum: date | None = None
    ort: KurzText | None = None
    korrektor: KurzText | None = None

    _trim = field_validator("ort", "korrektor", mode="before")(_trimmen)


class TagAusgabe(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    datum: date
    ort: str
    korrektor: str
    anzahl_prueflinge: int = 0


class PrueflingKurz(BaseModel):
    id: uuid.UUID
    reihenfolge: int
    name: str
    ident: str
    korrekturart: Korrekturart
    status: Status
    doku_punkte: int | None
    doku_note: float | None
    praesi_punkte: int | None
    praesi_note: float | None
    #: Wie viele PDFs hinterlegt sind. Ob die Doku vorliegt, muss niemand
    #: von Hand abhaken - es steht hier.
    dokumente: int
    #: Fortschritt für die Übersicht: bewertete Kriterien bzw. Sektionen.
    doku_bewertet: int
    doku_kriterien: int
    praesi_bewertet: int
    praesi_sektionen: int
    doku_grenzfall: bool
    praesi_grenzfall: bool
    #: Gesamtergebnis, sobald alle Teile da sind - mit Ergänzungsprüfung,
    #: wenn eine eingetragen ist.
    gesamt_punkte: int | None
    gesamt_note: float | None
    gesamt_grenzfall: bool


class TagDetail(BaseModel):
    tag: TagAusgabe
    prueflinge: list[PrueflingKurz]


# ── Prüflinge ────────────────────────────────────────────────────────────────


class Status(BaseModel):
    runtergeladen: bool = False
    kontrolliert: bool = False
    abgestimmt: bool = False
    hochgeladen: bool = False


class StatusAendern(BaseModel):
    runtergeladen: bool | None = None
    kontrolliert: bool | None = None
    abgestimmt: bool | None = None
    hochgeladen: bool | None = None


class PrueflingAnlegen(BaseModel):
    name: NameFeld

    _trim = field_validator("name", mode="before")(_trimmen)


class PrueflingAendern(BaseModel):
    name: NameFeld | None = None
    ident: Annotated[str, Field(max_length=40)] | None = None
    korrekturart: Korrekturart | None = None
    status: StatusAendern | None = None

    _trim = field_validator("name", "ident", mode="before")(_trimmen)


class BewertungAendern(BaseModel):
    """Teiländerung: Genannte Schlüssel werden gesetzt, ``null`` entfernt sie."""

    doku: dict[str, int | None] | None = None
    doku_bemerkungen: dict[str, Bemerkung | None] | None = None
    praesi_skala: dict[str, float | None] | None = None
    praesi_punkte: dict[str, int | None] | None = None
    praesi_bemerkungen: dict[str, Bemerkung | None] | None = None
    notizen: Annotated[str, Field(max_length=20000)] | None = None
    fragen: Annotated[str, Field(max_length=20000)] | None = None


class BewertungAusgabe(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    doku: dict[str, int]
    doku_bemerkungen: dict[str, str]
    praesi_skala: dict[str, float]
    praesi_punkte: dict[str, int]
    praesi_bemerkungen: dict[str, str]
    notizen: str
    fragen: str


class MepEingabe(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    bereich: MepBereich
    punkte: Punkte


class TeilnotenEingabe(BaseModel):
    """Ersetzt die Teilnoten vollständig - ``null`` heißt: noch nicht bekannt."""

    model_config = ConfigDict(from_attributes=True)

    teil1: Punkte | None = None
    planen_softwareprodukt: Punkte | None = None
    algorithmen: Punkte | None = None
    wiso: Punkte | None = None
    #: Mündliche Ergänzungsprüfung in genau einem Bereich von Teil 2.
    mep: MepEingabe | None = None


class RechnerEingabe(TeilnotenEingabe):
    """Was der Notenrechner bekommt - nichts davon wird gespeichert."""

    doku: Punkte | None = None
    praesentation: Punkte | None = None


class NotenstufeAusgabe(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    punkte: int
    note: float
    ganze_note: int
    grenzfall: bool
    bessere_note: int | None
    fehlen: int | None
    puffer: int


class RechnerAusgabe(BaseModel):
    ohne_mep: GesamtErgebnisAusgabe
    mit_mep: GesamtErgebnisAusgabe | None
    stufe_ohne_mep: NotenstufeAusgabe | None
    stufe_mit_mep: NotenstufeAusgabe | None
    stufe_doku: NotenstufeAusgabe | None
    stufe_praesentation: NotenstufeAusgabe | None


class ZeitAktion(BaseModel):
    aktion: Literal["praesentation_starten", "fachgespraech_starten", "beenden", "zuruecksetzen"]


class ZeitenAusgabe(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    praesi_start: datetime | None
    praesi_ende: datetime | None
    fg_start: datetime | None
    fg_ende: datetime | None


class DokumentAusgabe(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    art: DokumentArt
    dateiname: str
    groesse: int
    angelegt: datetime


class SektionErgebnisAusgabe(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    nr: str
    label: str
    max: int
    wert: int | None
    vollstaendig: bool
    vorschlag: int | None


class TeilErgebnisAusgabe(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    sektionen: list[SektionErgebnisAusgabe]
    gesamt: int | None
    note: float | None
    grenzfall: bool
    fehlend: list[str]


class BereichErgebnisAusgabe(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    label: str
    gewicht: int
    schriftlich: int | None
    muendlich: int | None
    wert: int | None


class GesamtErgebnisAusgabe(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    projekt: int | None
    bereiche: list[BereichErgebnisAusgabe]
    teil1: int | None
    teil2: int | None
    gesamt: int | None
    note: float | None
    grenzfall: bool
    fehlend: list[str]


class Auswertung(BaseModel):
    doku: TeilErgebnisAusgabe
    praesentation: TeilErgebnisAusgabe
    gesamt_ohne_mep: GesamtErgebnisAusgabe
    gesamt_mit_mep: GesamtErgebnisAusgabe | None


class PrueflingDetail(BaseModel):
    id: uuid.UUID
    tag: TagAusgabe
    reihenfolge: int
    name: str
    ident: str
    korrekturart: Korrekturart
    status: Status
    bewertung: BewertungAusgabe
    teilnoten: TeilnotenEingabe
    zeiten: ZeitenAusgabe
    dokumente: list[DokumentAusgabe]
    auswertung: Auswertung
    #: Uhr des Servers. Die Oberfläche rechnet laufende Zeiten gegen sie,
    #: nicht gegen die Uhr des Tablets - sonst verschiebt jede Abweichung
    #: zwischen beiden die Prüfungszeit.
    jetzt: datetime


# ── Katalog ──────────────────────────────────────────────────────────────────


class KnotenAusgabe(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    label: str
    art: Literal["points", "malus", "group", "scale"]
    max: int | None
    hinweis: str
    kinder: list[KnotenAusgabe]


class BlockAusgabe(BaseModel):
    id: str
    knoten: list[str]


class SektionAusgabe(BaseModel):
    id: str
    nr: str
    label: str
    max: int
    kinder: list[KnotenAusgabe]
    bloecke: list[BlockAusgabe]


class NotenbandAusgabe(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    von: int
    bis: int
    note: int


class BereichAusgabe(BaseModel):
    id: MepBereich
    label: str


class KatalogAusgabe(BaseModel):
    doku: list[SektionAusgabe]
    praesentation: list[SektionAusgabe]
    skala: list[float]
    korrekturarten: list[Korrekturart]
    notenbaender: list[NotenbandAusgabe]
    teil1_label: str
    bereiche: list[BereichAusgabe]
    projekt_label: str
    praesi_grenze_min: int
    gesamt_grenze_min: int


PrueflingKurz.model_rebuild()
RechnerAusgabe.model_rebuild()
TagDetail.model_rebuild()
