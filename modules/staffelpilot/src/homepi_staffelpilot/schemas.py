"""Der Vertrag nach aussen.

Was hier steht, landet im OpenAPI-Schema - und damit in der generischen
Ansicht des Frontends und in jedem erzeugten Client. Aenderungen hier sind
Aenderungen an der Schnittstelle.

Die Begriffe kommen aus der Spielordnung und bleiben deutsch: ein Staffelleiter
liest 'Befund' und 'abhaken', nicht 'finding' und 'acknowledge'.
"""

from __future__ import annotations

import datetime as dt
import uuid
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

# Ein Name aus Leerzeichen ist kein Name. min_length greift erst nach dem
# Trimmen - deshalb der Validator, nicht nur die Laengenangabe.
NameFeld = Annotated[str, Field(min_length=1, max_length=120)]
KurzFeld = Annotated[str, Field(max_length=120)]

#: Wie schwer ein Befund wiegt. Diese Reihenfolge ist auch die Sortierung in
#: der Oberflaeche - kritisch zuerst, weil ein Feldverweis nicht unter zwanzig
#: Hinweisen verschwinden darf.
Schwere = Literal["kritisch", "warnung", "hinweis"]

#: Was der Staffelleiter mit einem Befund gemacht hat. 'offen' blockiert das
#: Abhaken des Spiels - das ist die ganze Zusage dieses Artefakts.
Entscheidung = Literal["offen", "kenntnis", "verworfen"]

#: Altersklassen nach SpO SFV, soweit sie in einem Kreis vorkommen.
Altersklasse = Literal["maenner", "frauen", "ue32", "ue35", "ue40", "ue50"]


def _getrimmt(wert: object) -> object:
    return wert.strip() if isinstance(wert, str) else wert


# ── Staffel ───────────────────────────────────────────────────────────────


class StaffelAnlegen(BaseModel):
    name: NameFeld
    altersklasse: Altersklasse
    spielklasse: NameFeld
    saison: Annotated[str, Field(max_length=10)] = ""
    aktiv: bool = True

    @field_validator("name", "spielklasse", "saison", mode="before")
    @classmethod
    def _trimmen(cls, wert: object) -> object:
        return _getrimmt(wert)


class StaffelAendern(BaseModel):
    """Nur der Schalter. Name und Spielklasse stehen in DFBnet und werden dort
    geaendert; sie hier zusaetzlich bearbeitbar zu machen liesse beides
    auseinanderlaufen."""

    aktiv: bool


class StaffelAusgabe(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    altersklasse: Altersklasse
    spielklasse: str
    saison: str
    aktiv: bool


# ── Befund ────────────────────────────────────────────────────────────────


class BefundEingang(BaseModel):
    """Ein Befund, wie ihn ein Prueflauf einreicht."""

    regel: NameFeld
    schwere: Schwere
    titel: NameFeld
    text: Annotated[str, Field(max_length=2000)] = ""
    person: KurzFeld = ""
    mannschaft: KurzFeld = ""

    @field_validator("regel", "titel", "text", "person", "mannschaft", mode="before")
    @classmethod
    def _trimmen(cls, wert: object) -> object:
        return _getrimmt(wert)


class BefundAusgabe(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    regel: str
    schwere: Schwere
    titel: str
    text: str
    person: str
    mannschaft: str
    entscheidung: Entscheidung
    grund: str


class EntscheidungSetzen(BaseModel):
    """'kenntnis' heisst: gesehen, mehr passiert nicht. 'verworfen' heisst:
    kein Verstoss - und das braucht eine Begruendung, weil es die einzige
    Entscheidung ist, die einen Befund aus der Bearbeitung nimmt."""

    art: Literal["kenntnis", "verworfen"]
    grund: Annotated[str, Field(max_length=500)] = ""

    @field_validator("grund", mode="before")
    @classmethod
    def _trimmen(cls, wert: object) -> object:
        return _getrimmt(wert)


# ── Spielbericht ──────────────────────────────────────────────────────────


class SpielEingang(BaseModel):
    """Ein geprueftes Spiel, wie es ein Prueflauf einreicht.

    `dfbnet_id` ist der Schluessel: derselbe Bericht darf mehrfach eingereicht
    werden, ohne sich zu verdoppeln.
    """

    dfbnet_id: NameFeld
    datum: dt.date
    heim: NameFeld
    gast: NameFeld
    ergebnis: KurzFeld = ""
    befunde: list[BefundEingang] = Field(default_factory=list)

    @field_validator("dfbnet_id", "heim", "gast", "ergebnis", mode="before")
    @classmethod
    def _trimmen(cls, wert: object) -> object:
        return _getrimmt(wert)


class ImportAuftrag(BaseModel):
    """Der Weg, auf dem Daten hereinkommen.

    Bewusst ein eigener Endpunkt und kein interner Aufruf: die
    DFBnet-Automation faehrt minutenlang einen Browser und gehoert deshalb in
    einen eigenen Dienst (docs/06-artefakte.md). Sie schiebt dann hier herein,
    ohne dass sich an diesem Artefakt etwas aendert.
    """

    staffel_id: uuid.UUID
    spiele: list[SpielEingang]


class ImportErgebnis(BaseModel):
    angelegt: int
    aktualisiert: int
    befunde: int


class SpielAusgabe(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    staffel_id: uuid.UUID
    dfbnet_id: str
    datum: dt.date
    heim: str
    gast: str
    ergebnis: str
    abgehakt: bool
    abgehakt_am: dt.datetime | None
    befunde: list[BefundAusgabe]


class SpielZeile(BaseModel):
    """Eine Zeile der Warteschlange, ohne die Befunde selbst.

    Dreissig Spiele mit je zehn Befunden waeren ein Vielfaches an Daten fuer
    eine Ansicht, die nur Zaehler zeigt.
    """

    id: uuid.UUID
    dfbnet_id: str
    datum: dt.date
    heim: str
    gast: str
    ergebnis: str
    abgehakt: bool
    offene_befunde: int
    kritische_befunde: int


class Zusammenfassung(BaseModel):
    """Was auf der Kachel und im Seitenkopf steht."""

    spiele: int
    offen: int
    abgehakt: int
    befunde_offen: int
    befunde_kritisch: int
    staffeln_aktiv: int
