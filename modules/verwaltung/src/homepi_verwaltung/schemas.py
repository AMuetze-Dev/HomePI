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
    #: True, solange das Passwort von jemand anderem gesetzt wurde.
    passwort_wechseln: bool = False
    #: Artefakt -> Rolle.
    rechte: dict[str, Rolle] = {}
    angelegt: datetime | None = None
    #: True, wenn dieses Konto die Verwaltung darf. Die Oberfläche blendet
    #: danach Knöpfe aus - geprüft wird trotzdem hier im Backend.
    verwalter: bool = False


class NeuerBenutzer(BaseModel):
    """Zum Anlegen genuegen Name und Anzeigename.

    Ohne Passwort erzeugt der Dienst ein Startpasswort und gibt es genau
    einmal zurueck. Der Benutzer muss es beim ersten Anmelden ersetzen -
    ein Passwort, das jemand anders kennt, soll nicht das bleibende sein.
    """

    name: str = Field(min_length=1, max_length=32)
    passwort: str | None = Field(default=None, min_length=1, max_length=200)
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
    """Ohne Angabe entsteht ein neues Startpasswort."""

    passwort: str | None = Field(default=None, min_length=1, max_length=200)


class KontoAngelegt(BenutzerAusgabe):
    """Die Antwort aufs Anlegen - einmalig mit dem Startpasswort.

    Es steht nur hier, nie in der Datenbank und in keiner weiteren Antwort.
    Wer das Konto anlegt, gibt es weiter; danach ist es nicht mehr abrufbar.
    """

    startpasswort: str | None = None


class PasswortGesetzt(BaseModel):
    """Auch hier einmalig: das Startpasswort, das der Verwalter weitergibt."""

    startpasswort: str | None = None


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
