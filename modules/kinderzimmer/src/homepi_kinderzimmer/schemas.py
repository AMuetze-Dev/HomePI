"""Der Vertrag nach aussen.

Zwei Leser: die Elternseite im Browser und die Firmware auf dem ESP32. Alles,
was unter ``Manifest`` und ``Ereignisse`` steht, ist der Vertrag mit der
Firmware (siehe AGENTS.md, "Geraeteschnittstelle") - wer dort etwas aendert,
aendert ``FORMAT``.
"""

from __future__ import annotations

import datetime as dt
import uuid
from typing import Annotated, Literal

from pydantic import (
    BaseModel,
    BeforeValidator,
    ConfigDict,
    Field,
    field_validator,
    model_validator,
)

from .uid import normalisiere_uid

#: Version der Geraeteschnittstelle. Steigt bei jeder inkompatiblen Aenderung.
FORMAT = 1


def _trimmen(wert: object) -> object:
    """Ein Name aus Leerzeichen ist kein Name: erst trimmen, dann Laenge pruefen."""
    return " ".join(wert.split()) if isinstance(wert, str) else wert


Name60 = Annotated[str, BeforeValidator(_trimmen), Field(min_length=1, max_length=60)]
Name80 = Annotated[str, BeforeValidator(_trimmen), Field(min_length=1, max_length=80)]


Art = Literal[
    "familie", "tier", "farbe", "form", "menge", "ritual", "gefuehl", "geschichte", "sonstiges"
]
Farbwort = Literal[
    "rot", "blau", "gelb", "gruen", "orange", "lila", "rosa", "weiss", "schwarz", "braun"
]
Formwort = Literal["kreis", "quadrat", "dreieck", "rechteck", "stern", "herz"]
AufnahmeArt = Literal["stimme", "klang"]
EreignisArt = Literal["start", "knopf", "figur_auf", "figur_ab", "spiel", "ruhe", "abgleich"]

Hexfarbe = Annotated[str, Field(pattern=r"^#[0-9A-Fa-f]{6}$")]


# --- Spiele -----------------------------------------------------------------


class PhaseAusgabe(BaseModel):
    nummer: int
    titel: str
    alter: str


class SpielAusgabe(BaseModel):
    id: str
    nummer: int
    phase: int
    titel: str
    alter: str
    ablauf: str
    foerdert: str
    warum: str
    bereit: bool
    #: In den Einstellungen eingeschaltet
    aktiv: bool


class Zahlen(BaseModel):
    figuren: int
    aufnahmen: int
    geraete: int


class Uebersicht(BaseModel):
    phasen: list[PhaseAusgabe]
    spiele: list[SpielAusgabe]
    stand: str
    zahlen: Zahlen


# --- Einstellungen ----------------------------------------------------------


class Knopf(BaseModel):
    nummer: int = Field(ge=1, le=8)
    farbe: Hexfarbe = "#FFB000"
    klang: uuid.UUID | None = None

    @field_validator("farbe")
    @classmethod
    def _gross(cls, wert: str) -> str:
        return wert.upper()


class Einstellungen(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    #: Obergrenze in Prozent der Verstaerkerleistung. Die Firmware darf sie
    #: nie ueberschreiten, auch nicht ueber einen Knopf.
    lautstaerke_max: int = Field(default=40, ge=5, le=100)
    helligkeit_max: int = Field(default=40, ge=5, le=100)
    #: Nach so vielen Minuten ohne Handlung wird das Geraet still.
    ruhe_nach_min: int = Field(default=10, ge=1, le=60)
    startspiel: str = "licht-und-klang"
    spiele_aktiv: list[str] = Field(
        default_factory=lambda: ["licht-und-klang", "stimmen"], min_length=1
    )
    knoepfe: list[Knopf] = Field(
        default_factory=lambda: [Knopf(nummer=1, farbe="#FFB000")], max_length=8
    )

    @model_validator(mode="after")
    def _knoepfe_einmalig(self) -> Einstellungen:
        nummern = [k.nummer for k in self.knoepfe]
        if len(nummern) != len(set(nummern)):
            raise ValueError("Jeder Knopf darf nur einmal vorkommen")
        return self


# --- Aufnahmen --------------------------------------------------------------


class AufnahmeAusgabe(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    titel: str
    art: AufnahmeArt
    dauer_ms: int
    bytes: int
    sha256: str
    angelegt: dt.datetime


class AufnahmeAendern(BaseModel):
    titel: Name80
    art: AufnahmeArt


# --- Figuren ----------------------------------------------------------------


class FigurEingabe(BaseModel):
    uid: str
    name: Name60
    art: Art = "sonstiges"
    farbe: Farbwort | None = None
    form: Formwort | None = None
    menge: int | None = Field(default=None, ge=1, le=10)
    stimme: uuid.UUID | None = None
    klang: uuid.UUID | None = None

    @field_validator("uid", mode="before")
    @classmethod
    def _uid(cls, wert: object) -> object:
        return normalisiere_uid(wert) if isinstance(wert, str) else wert


class FigurAusgabe(BaseModel):
    id: uuid.UUID
    uid: str
    name: str
    art: Art
    farbe: Farbwort | None
    form: Formwort | None
    menge: int | None
    stimme: uuid.UUID | None
    klang: uuid.UUID | None


class UnbekannteFigur(BaseModel):
    uid: str
    zuletzt: dt.datetime | None


# --- Geraete ----------------------------------------------------------------


class GeraetAnlegen(BaseModel):
    name: Name60


class GeraetAusgabe(BaseModel):
    id: uuid.UUID
    name: str
    zuletzt_gesehen: dt.datetime | None
    firmware: str | None
    #: Hat das Geraet den aktuellen Stand? None: hat sich noch nie gemeldet.
    stand_aktuell: bool | None
    angelegt: dt.datetime


class GeraetMitToken(GeraetAusgabe):
    #: Steht genau einmal hier. In der Datenbank liegt nur der SHA-256.
    token: str


# --- Protokoll und Tagebuch -------------------------------------------------


class EreignisAusgabe(BaseModel):
    id: int
    geraet: str
    art: EreignisArt
    text: str
    zeitpunkt: dt.datetime | None
    empfangen: dt.datetime


class TagebuchEingabe(BaseModel):
    datum: dt.date
    text: Annotated[str, Field(min_length=1, max_length=2000)]

    @field_validator("text", mode="before")
    @classmethod
    def _rand(cls, wert: object) -> object:
        return wert.strip() if isinstance(wert, str) else wert


class TagebuchAusgabe(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    datum: dt.date
    text: str


# --- Geraeteschnittstelle ---------------------------------------------------


class ManifestKnopf(BaseModel):
    nummer: int
    farbe: str
    klang: str | None


class ManifestEinstellungen(BaseModel):
    lautstaerke_max: int
    helligkeit_max: int
    ruhe_nach_min: int
    startspiel: str
    spiele_aktiv: list[str]
    knoepfe: list[ManifestKnopf]


class ManifestFigur(BaseModel):
    uid: str
    name: str
    art: str
    farbe: str | None
    form: str | None
    menge: int | None
    stimme: str | None
    klang: str | None


class ManifestDatei(BaseModel):
    id: str
    sha256: str
    bytes: int
    dauer_ms: int


class Manifest(BaseModel):
    format: int
    stand: str
    einstellungen: ManifestEinstellungen
    figuren: list[ManifestFigur]
    dateien: list[ManifestDatei]


class EreignisEingang(BaseModel):
    #: Nur fuer Nachgereichtes aus einem frueheren Start. Fehlt es, gilt der
    #: Start aus dem Kopf der Sendung.
    start: int | None = Field(default=None, ge=0)
    nr: int = Field(ge=1)
    ms: int = Field(ge=0)
    zeit: dt.datetime | None = None
    art: EreignisArt
    knopf: int | None = Field(default=None, ge=1, le=8)
    uid: str | None = None
    spiel: str | None = Field(default=None, max_length=40)

    @field_validator("uid", mode="before")
    @classmethod
    def _uid(cls, wert: object) -> object:
        return normalisiere_uid(wert) if isinstance(wert, str) else wert


class EreignisseEingang(BaseModel):
    start: int = Field(ge=0)
    jetzt_ms: int = Field(ge=0)
    firmware: str = Field(default="", max_length=40)
    stand: str | None = Field(default=None, max_length=64)
    ereignisse: list[EreignisEingang] = Field(max_length=500)


class EreignisseAntwort(BaseModel):
    neu: int
    doppelt: int
    stand: str
