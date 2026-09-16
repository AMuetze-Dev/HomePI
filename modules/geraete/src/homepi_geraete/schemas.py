from __future__ import annotations

import uuid
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

Zustand = Literal["bereit", "wartung"]

# Ein Name aus Leerzeichen ist kein Name. min_length greift erst nach dem
# Trimmen - deshalb der Validator, nicht nur die Laengenangabe.
NameFeld = Annotated[str, Field(min_length=1, max_length=100)]


class GeraetAnlegen(BaseModel):
    name: NameFeld
    raum: NameFeld
    zustand: Zustand = "bereit"
    eingeschaltet: bool = False

    @field_validator("name", "raum", mode="before")
    @classmethod
    def _trimmen(cls, wert: object) -> object:
        return wert.strip() if isinstance(wert, str) else wert


class GeraetAendern(BaseModel):
    eingeschaltet: bool


class GeraetAusgabe(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    raum: str
    zustand: Zustand
    eingeschaltet: bool


class Zusammenfassung(BaseModel):
    anzahl: int
    eingeschaltet: int
    in_wartung: int
    raeume: dict[str, int]
