from __future__ import annotations

import uuid
from typing import Literal

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
    #: True, solange das Passwort von jemand anderem gesetzt wurde. Bis zum
    #: Wechsel kommt dieses Konto an kein Artefakt.
    passwort_wechseln: bool = False


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


class Darstellung(BaseModel):
    """Wie die Oberflaeche fuer dieses Konto aussieht.

    Die Grundfarbe ist bewusst nur ein Muster und keine Liste: Welche es gibt,
    weiss die Oberflaeche. Eine unbekannte faellt dort auf die Voreinstellung
    zurueck - eine neue soll nicht erst das Gateway anfassen muessen.
    """

    thema: Literal["system", "hell", "dunkel"] = "system"
    grund: str = Field(default="nocturne", pattern=r"^[a-z]{1,20}$")
    bewegung_reduziert: bool = False
