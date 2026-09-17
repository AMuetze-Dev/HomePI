from __future__ import annotations

import uuid

from pydantic import BaseModel, Field

from .dienst import Rolle


class Anmeldung(BaseModel):
    name: str = Field(min_length=1, max_length=32)
    passwort: str = Field(min_length=1, max_length=200)


class BenutzerAusgabe(BaseModel):
    # Bewusst ohne from_attributes: die Ausgabe wird im Router Feld fuer Feld
    # gebaut. Automatisches Uebernehmen aus dem ORM-Objekt hat schon zu oft
    # mehr mitgenommen als gewollt.
    id: uuid.UUID
    name: str
    anzeigename: str
    #: Artefakt -> Rolle. Das Frontend blendet danach Bedienelemente aus -
    #: die eigentliche Pruefung passiert trotzdem im Backend.
    rechte: dict[str, Rolle] = {}


class PasswortAendern(BaseModel):
    altes_passwort: str = Field(min_length=1, max_length=200)
    neues_passwort: str = Field(min_length=1, max_length=200)


class Einrichtungsstand(BaseModel):
    #: True, solange es keinen Verwalter gibt. Mehr verraet die Antwort nicht.
    noetig: bool


class Einrichtung(BaseModel):
    """Der erste Verwalter.

    Das Token ist kein Passwort und wird deshalb auch nicht wie eines geprueft
    - es ist der Nachweis, dass der Aufrufer an das Log der Maschine kommt.
    """

    token: str = Field(min_length=1, max_length=200)
    name: str = Field(min_length=1, max_length=32)
    passwort: str = Field(min_length=1, max_length=200)
    anzeigename: str | None = Field(default=None, max_length=100)
