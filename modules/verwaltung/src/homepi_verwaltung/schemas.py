"""Der Vertrag nach außen.

Bewusst ohne ``from_attributes``: jede Ausgabe wird im Router Feld für Feld
gebaut. Automatisch aus dem ORM-Objekt zu übernehmen hätte schon einmal mehr
mitgenommen als gewollt - beim Benutzer wäre das der Passwort-Hash.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from homepi_core.auth import Rolle
from pydantic import BaseModel, Field


class BenutzerAusgabe(BaseModel):
    id: uuid.UUID
    name: str
    anzeigename: str
    aktiv: bool
    #: Artefakt -> Rolle.
    rechte: dict[str, Rolle] = {}
    angelegt: datetime | None = None
    #: True, wenn dieses Konto die Verwaltung darf. Die Oberfläche blendet
    #: danach Knöpfe aus - geprüft wird trotzdem hier im Backend.
    verwalter: bool = False


class NeuerBenutzer(BaseModel):
    name: str = Field(min_length=1, max_length=32)
    passwort: str = Field(min_length=1, max_length=200)
    anzeigename: str | None = Field(default=None, max_length=100)


class BenutzerAenderung(BaseModel):
    """Nur, was ein Verwalter an einem fremden Konto ändern darf.

    Der Benutzername steht bewusst nicht drin: er ist die Kennung, unter der
    sich jemand anmeldet, und ein stiller Wechsel wäre ein Ärgernis. Wer
    umbenennen will, legt ein neues Konto an.
    """

    anzeigename: str | None = Field(default=None, max_length=100)
    aktiv: bool | None = None


class PasswortSetzen(BaseModel):
    passwort: str = Field(min_length=1, max_length=200)


class RechtSetzen(BaseModel):
    rolle: Rolle


class ArtefaktAusgabe(BaseModel):
    """Ein Artefakt, für das sich Rechte vergeben lassen."""

    id: str
    titel: str
    #: "oeffentlich" braucht kein Recht - die Oberfläche sagt das dazu.
    zugang: str


class Ueberblick(BaseModel):
    """Was unter ``/verwaltung`` steht.

    Jedes Artefakt antwortet unter seinem Praefix - daran erkennt der
    Rauchtest, dass ein Modul aus dem Manifest wirklich eingehaengt ist. Hier
    sind es die Zahlen, die man beim Nachsehen ohnehin wissen will.
    """

    konten: int
    verwalter: int
    gesperrt: int
    artefakte: int
