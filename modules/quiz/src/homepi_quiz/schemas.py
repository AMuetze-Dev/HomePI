"""Der Vertrag nach aussen.

Was hier steht, landet im OpenAPI-Schema - und damit in der generischen
Ansicht des Frontends und in jedem erzeugten Client. Aenderungen hier sind
Aenderungen an der Schnittstelle.

Zwei Sorten Ausgabe, und der Unterschied ist der Kern dieses Artefakts:

* ``Steuerung`` und ``FrageAusgabe`` gehen nur an die Leitung (mit Konto) und
  enthalten die Loesungen.
* ``Rundenstand`` geht an jeden, der den Code kennt - Spieler und
  Anzeigetafel. Er enthaelt die Loesung erst, wenn die Frage aufgeloest ist,
  und von den Mitspielern nur Name und Punkte.
"""

from __future__ import annotations

import datetime as dt
import uuid
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

# ------------------------------------------------------------- Bausteine


def _trimmen(wert: object) -> object:
    return " ".join(wert.split()) if isinstance(wert, str) else wert


Kurztext = Annotated[str, Field(min_length=1, max_length=200)]

Fragetyp = Literal[
    "freitext", "zahl", "schaetzung", "auswahl", "buzzer", "bild", "hotspot", "sortieren"
]
Rundenstatus = Literal["lobby", "laeuft", "beendet"]
Phase = Literal["keine", "bereit", "offen", "gesperrt", "aufgeloest"]


class _Getrimmt(BaseModel):
    """Trimmt jeden Text, bevor die Laenge geprueft wird - sonst ginge eine
    Antwort aus drei Leerzeichen als Text durch."""

    @model_validator(mode="before")
    @classmethod
    def _texte_trimmen(cls, werte: object) -> object:
        # Als Modell-Validator und nicht je Feld: ein Feld-Validator auf "*"
        # erfasste auch ``typ``, und das verbietet Pydantic fuer das Feld, an
        # dem es die Fragetypen unterscheidet.
        if not isinstance(werte, dict):
            return werte
        return {
            schluessel: (
                [_trimmen(eintrag) for eintrag in wert]
                if isinstance(wert, list)
                else _trimmen(wert)
            )
            for schluessel, wert in werte.items()
        }


# --------------------------------------------------------- Fragedaten
#
# Je Typ ein eigenes Modell mit dem Feld ``typ`` als Unterscheidung. Damit
# meldet ein falsches Feld eine 422 mit Namen, statt still ignoriert zu werden.


class FreitextDaten(_Getrimmt):
    """Freie Eingabe. Richtig ist, was einer der Loesungen gleicht - ohne
    Ruecksicht auf Gross- und Kleinschreibung und Leerzeichen."""

    typ: Literal["freitext"] = "freitext"
    loesungen: list[Kurztext] = Field(min_length=1, max_length=20)


class ZahlDaten(_Getrimmt):
    typ: Literal["zahl"] = "zahl"
    loesung: float
    toleranz: float = Field(default=0, ge=0)
    einheit: str = Field(default="", max_length=20)


class SchaetzDaten(_Getrimmt):
    """Schaetzfrage mit Schieberegler. Wer am naechsten liegt, gewinnt."""

    typ: Literal["schaetzung"] = "schaetzung"
    minimum: float
    maximum: float
    schritt: float = Field(default=1, gt=0)
    loesung: float
    einheit: str = Field(default="", max_length=20)

    @model_validator(mode="after")
    def _bereich(self) -> SchaetzDaten:
        if self.minimum >= self.maximum:
            raise ValueError("Das Minimum muss kleiner als das Maximum sein")
        if not self.minimum <= self.loesung <= self.maximum:
            raise ValueError("Die Lösung muss zwischen Minimum und Maximum liegen")
        return self


class Option(_Getrimmt):
    text: Kurztext
    richtig: bool = False


class AuswahlDaten(_Getrimmt):
    """Eine oder mehrere richtige Optionen. Bei mehreren kreuzen die Spieler
    mehrere an, sonst genau eine."""

    typ: Literal["auswahl"] = "auswahl"
    optionen: list[Option] = Field(min_length=2, max_length=8)

    @model_validator(mode="after")
    def _eine_richtig(self) -> AuswahlDaten:
        if not any(option.richtig for option in self.optionen):
            raise ValueError("Mindestens eine Option muss richtig sein")
        return self


class BuzzerDaten(_Getrimmt):
    """Wer zuerst drueckt, antwortet muendlich. Die Loesung steht nur als
    Hilfe fuer die Leitung da - bewertet wird von Hand."""

    typ: Literal["buzzer"] = "buzzer"
    loesung: str = Field(default="", max_length=200)


class BildDaten(_Getrimmt):
    """Bildfrage: ein Bild, eine freie Antwort. Ohne Loesungen bewertet die
    Leitung von Hand."""

    typ: Literal["bild"] = "bild"
    loesungen: list[Kurztext] = Field(default_factory=list, max_length=20)


class Ziel(BaseModel):
    """Kreis auf dem Bild, in Prozent von Breite und Hoehe."""

    x: float = Field(ge=0, le=100)
    y: float = Field(ge=0, le=100)
    radius: float = Field(default=8, gt=0, le=50)


class HotspotDaten(BaseModel):
    typ: Literal["hotspot"] = "hotspot"
    ziele: list[Ziel] = Field(min_length=1, max_length=10)


class SortierDaten(_Getrimmt):
    """Die Elemente in der richtigen Reihenfolge. Die Spieler bekommen sie
    gemischt."""

    typ: Literal["sortieren"] = "sortieren"
    elemente: list[Kurztext] = Field(min_length=2, max_length=8)


FrageDaten = Annotated[
    FreitextDaten
    | ZahlDaten
    | SchaetzDaten
    | AuswahlDaten
    | BuzzerDaten
    | BildDaten
    | HotspotDaten
    | SortierDaten,
    Field(discriminator="typ"),
]


# ------------------------------------------------------------- Kataloge


class KatalogEingabe(_Getrimmt):
    titel: Annotated[str, Field(min_length=1, max_length=120)]
    beschreibung: str = Field(default="", max_length=500)


class KatalogAusgabe(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    titel: str
    beschreibung: str
    anzahl_fragen: int = 0
    geaendert: dt.datetime


class FrageEingabe(_Getrimmt):
    text: Annotated[str, Field(min_length=1, max_length=500)]
    kategorie: str = Field(default="", max_length=60)
    punkte: int = Field(default=1, ge=1, le=100)
    #: Sekunden. Ohne Zeitlimit laeuft die Frage, bis die Leitung sperrt.
    zeitlimit: int | None = Field(default=None, ge=5, le=600)
    daten: FrageDaten


class FrageAusgabe(BaseModel):
    """Eine Frage samt Loesung - nur fuer die Leitung."""

    id: uuid.UUID
    position: int
    text: str
    kategorie: str
    punkte: int
    zeitlimit: int | None
    hat_bild: bool
    daten: FrageDaten


class KatalogDetail(KatalogAusgabe):
    fragen: list[FrageAusgabe] = Field(default_factory=list)


class Reihenfolge(BaseModel):
    fragen: list[uuid.UUID] = Field(min_length=1)


# ---------------------------------------------------------- Runden (Leitung)


class RundeAnlegen(BaseModel):
    katalog_id: uuid.UUID


class RundeAusgabe(BaseModel):
    id: uuid.UUID
    code: str
    katalog_id: uuid.UUID
    katalog_titel: str
    status: Rundenstatus
    anzahl_spieler: int
    angelegt: dt.datetime


class FrageWaehlen(BaseModel):
    frage_id: uuid.UUID


class Zeigen(BaseModel):
    #: Mit Zeitlimit der Frage starten. Ohne bleibt sie offen, bis gesperrt wird.
    timer: bool = True


class BildSichtbar(BaseModel):
    sichtbar: bool


class BuzzerUrteil(BaseModel):
    richtig: bool


class PunkteSetzen(BaseModel):
    punkte: int = Field(ge=-1000, le=1000)


class Korrektur(_Getrimmt):
    punkte: int = Field(ge=-100, le=100)
    grund: str = Field(default="", max_length=120)

    @field_validator("punkte")
    @classmethod
    def _nicht_null(cls, wert: int) -> int:
        if wert == 0:
            raise ValueError("Null Punkte ändern nichts")
        return wert


class AntwortSicht(BaseModel):
    """Eine Antwort, wie die Leitung sie sieht: im Klartext und mit Bewertung."""

    id: uuid.UUID
    spieler_id: uuid.UUID
    spieler: str
    anzeige: str
    eingeloggt: bool
    punkte: int | None
    richtig: bool | None
    #: Rohwert fuer die Darstellung, etwa der Klickpunkt beim Hotspot.
    wert: dict[str, object]


class BuzzerSicht(BaseModel):
    spieler_id: uuid.UUID
    spieler: str
    position: int
    urteil: Literal["wartet", "richtig", "falsch"]


class SpielerSicht(BaseModel):
    id: uuid.UUID
    name: str
    punkte: int
    rang: int
    zuletzt_gesehen: dt.datetime
    #: In der letzten Dreiviertelminute gesehen - das Handy ist noch dabei.
    verbunden: bool


class Steuerung(BaseModel):
    """Alles, was die Leitung waehrend der Runde braucht."""

    runde: RundeAusgabe
    phase: Phase
    frage: FrageAusgabe | None
    fragen: list[FrageAusgabe]
    beantwortet: list[uuid.UUID]
    bild_sichtbar: bool
    frist: dt.datetime | None
    jetzt: dt.datetime
    spieler: list[SpielerSicht]
    antworten: list[AntwortSicht]
    buzzer: list[BuzzerSicht]


class Wiederkehrcode(BaseModel):
    """Einmal angezeigt, nirgends gespeichert ausser als Hash."""

    code: str
    gueltig_bis: dt.datetime


# ------------------------------------------------------------ Spieler


class Beitritt(_Getrimmt):
    name: Annotated[str, Field(min_length=1, max_length=24)]
    #: Nur wer von der Leitung einen Wiederkehrcode bekommen hat - nach einem
    #: verlorenen Geraet. Ohne Code ist ein vergebener Name vergeben.
    wiederkehrcode: str | None = Field(default=None, max_length=20)


class AntwortEingabe(BaseModel):
    """Was ein Spieler abgibt. Welches Feld zaehlt, haengt am Fragetyp."""

    text: str | None = Field(default=None, max_length=200)
    zahl: float | None = None
    auswahl: list[int] | None = Field(default=None, max_length=8)
    x: float | None = Field(default=None, ge=0, le=100)
    y: float | None = Field(default=None, ge=0, le=100)
    reihenfolge: list[str] | None = Field(default=None, max_length=8)
    #: Eingeloggt heisst: fertig. Die Leitung sieht, wer noch tippt.
    eingeloggt: bool = False


class Element(BaseModel):
    kennung: str
    text: str


class Loesung(BaseModel):
    """Erst nach dem Aufloesen oeffentlich."""

    anzeige: str
    texte: list[str] = Field(default_factory=list)
    zahl: float | None = None
    toleranz: float | None = None
    optionen: list[int] = Field(default_factory=list)
    ziele: list[Ziel] = Field(default_factory=list)
    reihenfolge: list[str] = Field(default_factory=list)


class OeffentlicheFrage(BaseModel):
    """Die Frage, wie Spieler und Tafel sie sehen. Ohne Loesung, solange
    nicht aufgeloest ist - und vor dem Zeigen nur Nummer und Kategorie."""

    nummer: int
    anzahl: int
    kategorie: str
    typ: Fragetyp
    punkte: int
    text: str | None
    hat_bild: bool
    optionen: list[str] = Field(default_factory=list)
    mehrfach: bool = False
    elemente: list[Element] = Field(default_factory=list)
    minimum: float | None = None
    maximum: float | None = None
    schritt: float | None = None
    einheit: str = ""
    loesung: Loesung | None = None


class Platz(BaseModel):
    """Eine Zeile der Rangliste - Name und Punkte, mehr nicht."""

    name: str
    punkte: int
    rang: int


class EigeneAntwort(BaseModel):
    wert: dict[str, object]
    eingeloggt: bool
    punkte: int | None
    richtig: bool | None


class Ich(BaseModel):
    """Was nur der Spieler selbst sieht, erkannt am Cookie."""

    name: str
    punkte: int
    rang: int
    antwort: EigeneAntwort | None
    #: Platz in der Buzzer-Reihenfolge, 1 ist dran. None: nicht gedrueckt.
    buzzer_position: int | None
    buzzer_urteil: Literal["wartet", "richtig", "falsch"] | None


class Rundenstand(BaseModel):
    code: str
    titel: str
    status: Rundenstatus
    phase: Phase
    frage: OeffentlicheFrage | None
    bild_sichtbar: bool
    frist: dt.datetime | None
    #: Uhrzeit des Servers. Der Countdown rechnet damit, nicht mit der Uhr
    #: des Handys, die eine halbe Minute danebenliegen kann.
    jetzt: dt.datetime
    rangliste: list[Platz]
    anzahl_antworten: int
    #: Wer gerade dran ist, ein Name.
    buzzer: str | None
    ich: Ich | None


class Uebersicht(BaseModel):
    laufende_runden: int
