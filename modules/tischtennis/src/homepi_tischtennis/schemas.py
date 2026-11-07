"""Der Vertrag nach aussen.

Was hier steht, landet im OpenAPI-Schema - und damit in der generischen
Ansicht des Frontends und in jedem erzeugten Client. Aenderungen hier sind
Aenderungen an der Schnittstelle.

Zwei Entscheidungen, die man in den Feldnamen wiederfindet:

  - Ein Satz ist ein Objekt mit ``heim`` und ``gast`` und kein Zahlenpaar.
    Im Formular steht dann "Heim 11, Gast 9" und nicht "[0] und [1]".
  - Ein Spiel nennt neben den Kennungen auch die Namen und, solange der
    Gegner noch nicht feststeht, dessen Herkunft ("Sieger aus Spiel 3").
    Die Dashboard-Ansicht soll keine zweite Abfrage brauchen, um einen
    Spielplan anzuzeigen.
"""

from __future__ import annotations

import datetime as dt
import uuid
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

NameFeld = Annotated[str, Field(min_length=1, max_length=100)]

Modus = Literal["gruppen_ko", "ko", "schweizer"]
TurnierZustand = Literal["planung", "laufend", "beendet"]
SpielZustand = Literal["geplant", "laeuft", "beendet"]
Phase = Literal["gruppe", "ko", "runde"]


def _getrimmt(wert: object) -> object:
    return wert.strip() if isinstance(wert, str) else wert


class TurnierEinstellungen(BaseModel):
    """Alles, was sich am laufenden Betrieb noch aendern laesst.

    Die Grenzen sind absichtlich weit: wer zu acht an einem Tisch spielt,
    soll das eintragen koennen. Eng wird es nur dort, wo eine Zahl keinen
    Sinn hat - best of 4 gibt es nicht.
    """

    modus: Modus = "gruppen_ko"
    tische: int = Field(2, ge=1, le=12, description="Wie viele Tische gleichzeitig bespielt werden")
    best_of: Literal[3, 5, 7] = Field(5, description="Gewinnsaetze: best of 3, 5 oder 7")
    punkte_bis: Literal[11, 21] = Field(11, description="Punkte je Satz")
    minuten_pro_spiel: int = Field(
        12, ge=1, le=120, description="Schaetzung fuer den Zeitplan, nicht mehr"
    )
    anzahl_gruppen: int = Field(2, ge=1, le=16, description="Nur bei Gruppen + KO")
    weiter_pro_gruppe: int = Field(
        2, ge=1, le=8, description="Wie viele je Gruppe ins KO-Raster kommen"
    )
    runden: int = Field(4, ge=1, le=20, description="Nur beim Schweizer System")


class TurnierAnlegen(TurnierEinstellungen):
    name: NameFeld

    @field_validator("name", mode="before")
    @classmethod
    def _trimmen(cls, wert: object) -> object:
        return _getrimmt(wert)


class TurnierAusgabe(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    modus: Modus
    zustand: TurnierZustand
    tische: int
    best_of: int
    punkte_bis: int
    minuten_pro_spiel: int
    anzahl_gruppen: int
    weiter_pro_gruppe: int
    runden: int
    saat: int | None
    runde_angesetzt: int
    ko_steht: bool
    anzahl_teilnehmer: int = 0
    anzahl_spiele: int = 0
    offene_spiele: int = 0


class TeilnehmerAnlegen(BaseModel):
    name: NameFeld
    notiz: str = Field("", max_length=100, description="Abteilung, Standort, was hilft")

    @field_validator("name", "notiz", mode="before")
    @classmethod
    def _trimmen(cls, wert: object) -> object:
        return _getrimmt(wert)


class TeilnehmerAusgabe(BaseModel):
    id: uuid.UUID
    name: str
    notiz: str
    gruppe: str | None = None
    freilose: int = 0


class SatzEingabe(BaseModel):
    heim: int = Field(ge=0, le=99)
    gast: int = Field(ge=0, le=99)


class ErgebnisEintragen(BaseModel):
    """Alle Saetze auf einmal.

    Satz fuer Satz zu schicken waere naeher am Spielverlauf und in der
    Bedienung schlechter: ein Tippfehler im zweiten Satz liesse sich dann
    nur durch Zuruecknehmen des dritten beheben.
    """

    saetze: list[SatzEingabe] = Field(max_length=9)


class SpielBeginnen(BaseModel):
    tisch: int | None = Field(None, ge=1, le=12, description="Ohne Angabe: der freie Tisch")


class SpielAusgabe(BaseModel):
    id: uuid.UUID
    nummer: int
    phase: Phase
    runde: int
    bezeichnung: str
    gruppe: str | None = None

    heim_id: uuid.UUID | None = None
    gast_id: uuid.UUID | None = None
    heim: str | None = None
    gast: str | None = None
    #: Steht statt des Namens, solange der Gegner nicht feststeht.
    heim_herkunft: str | None = None
    gast_herkunft: str | None = None

    zustand: SpielZustand
    tisch: int | None = None
    saetze: list[SatzEingabe] = Field(default_factory=list)
    saetze_heim: int = 0
    saetze_gast: int = 0
    sieger_id: uuid.UUID | None = None
    freilos: bool = False

    begonnen_am: dt.datetime | None = None
    beendet_am: dt.datetime | None = None
    #: Aus dem Zeitplan gerechnet, kein gespeicherter Wert.
    erwartet_ab: dt.datetime | None = None
    #: Der Vorgaenger am selben Tisch laeuft gerade - das ist die Glocke.
    gleich_dran: bool = False


class TabellenzeileAusgabe(BaseModel):
    platz: int
    teilnehmer_id: uuid.UUID | None = None
    teilnehmer: str
    spiele: int
    siege: int
    niederlagen: int
    punkte: int
    saetze_fuer: int
    saetze_gegen: int
    baelle_fuer: int
    baelle_gegen: int
    satzdifferenz: int
    balldifferenz: int


class TabelleAusgabe(BaseModel):
    titel: str
    zeilen: list[TabellenzeileAusgabe]


class GruppeVorschau(BaseModel):
    name: str
    teilnehmer: list[str]


class PaarungVorschau(BaseModel):
    bezeichnung: str
    heim: str
    gast: str


class Auslosung(BaseModel):
    """Was dieses Los ergaebe - gespeichert ist davon nichts.

    Der Knopf "nochmal wuerfeln" ist der Grund fuer diese Trennung: Wer
    erst speichert und dann ansieht, muss zum Verwerfen den halben
    Spielplan wieder loeschen.
    """

    saat: int
    modus: Modus
    gruppen: list[GruppeVorschau] = Field(default_factory=list)
    paarungen: list[PaarungVorschau] = Field(default_factory=list)
    anzahl_spiele: int
    dauer_minuten: int
    hinweis: str = ""


class AuswuerfelnAnfrage(BaseModel):
    saat: int | None = Field(
        None, ge=0, le=999_999_999, description="Ohne Angabe wird eine neue Saat gezogen"
    )


class TischAusgabe(BaseModel):
    tisch: int
    laeuft: SpielAusgabe | None = None
    danach: list[SpielAusgabe] = Field(default_factory=list)


class Dashboard(BaseModel):
    """Alles, was die oeffentliche Ansicht braucht - in einem Abruf.

    Die Seite fragt im Sekundentakt nach; drei Abrufe je Durchgang waeren
    dreimal so viele Verbindungen fuer dieselbe Auskunft.
    """

    turnier: TurnierAusgabe | None = None
    stand: dt.datetime
    tische: list[TischAusgabe] = Field(default_factory=list)
    naechste: list[SpielAusgabe] = Field(default_factory=list)
    letzte: list[SpielAusgabe] = Field(default_factory=list)
    tabellen: list[TabelleAusgabe] = Field(default_factory=list)
    teilnehmer: list[TeilnehmerAusgabe] = Field(default_factory=list)
    #: Vorbei, wenn kein Spiel mehr offen ist.
    fertig: bool = False
