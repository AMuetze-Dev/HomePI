"""Der Vertrag nach aussen.

Pydantic-Fehler werden vom Gateway zu 422 mit Feldnamen - die Oberflaeche
zeigt sie unveraendert an. Deshalb steht jede Bedingung hier und nicht als
stille Annahme im Dienst.
"""

from __future__ import annotations

import uuid
from decimal import Decimal
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

#: Wozu ein Konto da ist. Nicht, wem es gehoert - das steht im Inhaber.
#:
#:   verteiler  Hier kommt Geld an und wird weiterverteilt (Gehaltskonto,
#:              Gemeinschaftskonto). Genau eines je Inhaber.
#:   verbrauch  Woraus der Alltag bezahlt wird.
#:   sparen     Was waechst und liegen bleibt.
#:   ruecklage  Woher die unregelmaessigen Abbuchungen kommen.
Kontoart = Literal["verteiler", "verbrauch", "sparen", "ruecklage"]

Postenart = Literal["einnahme", "ausgabe"]

#: Alles, was sich gleichmaessig auf Monate verteilen laesst. Woechentlich
#: fehlt mit Absicht: eine Ruecklage rechnet in Monaten, und ein
#: woechentlicher Posten ist in diesem Buch ein monatlicher mit anderem Betrag.
Intervall = Literal[1, 3, 6, 12]

NameFeld = Annotated[str, Field(min_length=1, max_length=80)]
#: Nicht negativ: ein Posten hat eine Richtung (Einnahme oder Ausgabe), der
#: Betrag traegt sie nicht noch einmal.
BetragFeld = Annotated[Decimal, Field(ge=0, le=Decimal("9999999.99"), decimal_places=2)]
MonatFeld = Annotated[int, Field(ge=1, le=12)]
TagFeld = Annotated[int, Field(ge=1, le=31)]


def _getrimmt(wert: object) -> object:
    return wert.strip() if isinstance(wert, str) else wert


# --------------------------------------------------------------- Person


class PersonAnlegen(BaseModel):
    name: NameFeld
    reihenfolge: int = 0

    _trimmen = field_validator("name", mode="before")(_getrimmt)


class PersonAendern(BaseModel):
    name: NameFeld | None = None
    reihenfolge: int | None = None

    _trimmen = field_validator("name", mode="before")(_getrimmt)


class PersonAusgabe(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    reihenfolge: int


# ---------------------------------------------------------------- Konto


class KontoAnlegen(BaseModel):
    name: NameFeld
    art: Kontoart = "verbrauch"
    #: Leer heisst gemeinschaftlich. Das ist kein Sonderfall, sondern der
    #: Grund, warum es dieses Artefakt gibt.
    inhaber_id: uuid.UUID | None = None
    notiz: str = Field(default="", max_length=200)
    reihenfolge: int = 0

    _trimmen = field_validator("name", "notiz", mode="before")(_getrimmt)


class KontoAendern(BaseModel):
    name: NameFeld | None = None
    art: Kontoart | None = None
    inhaber_id: uuid.UUID | None = None
    #: Ohne dieses Feld liesse sich ein Konto nicht von "gehoert Aaron" auf
    #: "gemeinschaftlich" zuruecksetzen: None heisst beim Aendern sonst
    #: "nicht angefasst".
    gemeinschaftlich: bool | None = None
    notiz: str | None = Field(default=None, max_length=200)
    reihenfolge: int | None = None

    _trimmen = field_validator("name", "notiz", mode="before")(_getrimmt)


class KontoAusgabe(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    art: Kontoart
    inhaber_id: uuid.UUID | None
    notiz: str
    reihenfolge: int


# ------------------------------------------------------------ Kategorie


class KategorieAnlegen(BaseModel):
    name: NameFeld
    #: Was hierhin fliesst, ist kein Verbrauch, sondern Ruecklage oder
    #: Anlage - es geht in die Sparquote statt in die festen Kosten.
    zaehlt_als_sparen: bool = False
    reihenfolge: int = 0

    _trimmen = field_validator("name", mode="before")(_getrimmt)


class KategorieAendern(BaseModel):
    name: NameFeld | None = None
    zaehlt_als_sparen: bool | None = None
    reihenfolge: int | None = None

    _trimmen = field_validator("name", mode="before")(_getrimmt)


class KategorieAusgabe(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    zaehlt_als_sparen: bool
    reihenfolge: int


# ---------------------------------------------------------------- Posten


class Anteil(BaseModel):
    """Ein Teil eines gemeinsamen Postens.

    Gewichte statt Prozent: 1:2 bleibt beim Aendern des Betrags richtig,
    33,3 % zu 66,7 % nicht. Und die Summe muss nirgends 100 ergeben.
    """

    model_config = ConfigDict(from_attributes=True)

    person_id: uuid.UUID
    gewicht: Annotated[int, Field(ge=1, le=1000)]


class PostenBasis(BaseModel):
    name: NameFeld
    art: Postenart
    #: Was die Bank abbucht - nicht, was monatlich zurueckgelegt wird. Das
    #: rechnet der Dienst aus, damit beides nicht auseinanderlaeuft.
    betrag: BetragFeld
    intervall_monate: Intervall = 1
    faelligkeitsmonat: MonatFeld = 1
    abbuchungstag: TagFeld | None = None
    konto_id: uuid.UUID
    kategorie_id: uuid.UUID | None = None
    #: Ein Puffer, kein fester Posten: Variabel ist das, was uebrig bleiben
    #: darf. Es zaehlt nicht zu den festen Kosten und drueckt damit nicht die
    #: moegliche Sparquote.
    variabel: bool = False
    aktiv: bool = True
    anteile: list[Anteil] = Field(default_factory=list)

    _trimmen = field_validator("name", mode="before")(_getrimmt)

    @model_validator(mode="after")
    def _faelligkeit_vereinheitlichen(self) -> PostenBasis:
        """Monat 8 bei Quartal meint dieselben vier Monate wie Monat 2.

        Ohne diese Normalisierung haetten zwei Posten mit gleichem Rhythmus
        verschiedene Zahlen in der Datenbank, und jeder Vergleich muesste sie
        erst wieder zusammenrechnen.
        """
        self.faelligkeitsmonat = ((self.faelligkeitsmonat - 1) % self.intervall_monate) + 1
        return self

    @field_validator("anteile")
    @classmethod
    def _jede_person_hoechstens_einmal(cls, anteile: list[Anteil]) -> list[Anteil]:
        kennungen = [a.person_id for a in anteile]
        if len(set(kennungen)) != len(kennungen):
            raise ValueError("Jede Person darf in einem Posten nur einmal stehen")
        return anteile


class PostenAnlegen(PostenBasis):
    pass


class PostenAendern(BaseModel):
    """Alles optional: was fehlt, bleibt stehen.

    ``anteile`` ist die Ausnahme - eine leere Liste loescht die Aufteilung,
    denn anders liesse sich ein geteilter Posten nie wieder zu einem ganzen
    machen.
    """

    name: NameFeld | None = None
    #: Auch die Richtung: wer beim Anlegen "Einnahme" statt "Ausgabe" erwischt
    #: hat, soll das aendern koennen und nicht loeschen muessen.
    art: Postenart | None = None
    betrag: BetragFeld | None = None
    intervall_monate: Intervall | None = None
    faelligkeitsmonat: MonatFeld | None = None
    abbuchungstag: TagFeld | None = None
    tag_loeschen: bool = False
    konto_id: uuid.UUID | None = None
    kategorie_id: uuid.UUID | None = None
    kategorie_loeschen: bool = False
    variabel: bool | None = None
    aktiv: bool | None = None
    anteile: list[Anteil] | None = None

    _trimmen = field_validator("name", mode="before")(_getrimmt)


class PostenAusgabe(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    art: Postenart
    betrag: Decimal
    intervall_monate: int
    faelligkeitsmonat: int
    abbuchungstag: int | None
    konto_id: uuid.UUID
    kategorie_id: uuid.UUID | None
    variabel: bool
    aktiv: bool
    anteile: list[Anteil]


# ------------------------------------------------------------- Auswertung


class PostenZeile(BaseModel):
    """Ein Posten, wie ihn der Monatsplan zeigt - mit allem Gerechneten."""

    id: uuid.UUID
    name: str
    art: Postenart
    konto: str
    kategorie: str
    betrag: Decimal
    #: betrag / intervall_monate. Der Betrag, der jeden Monat zurueckgelegt
    #: werden muss, damit die Abbuchung gedeckt ist.
    monatsrate: Decimal
    intervall_monate: int
    faelligkeitsmonat: int
    abbuchungstag: int | None
    #: In welchen Monaten die Bank zugreift - ausgeschrieben, damit niemand
    #: alle drei Monate ab Februar im Kopf aufloesen muss.
    faellige_monate: list[int]
    faellig_im_monat: bool
    #: Was bis jetzt zurueckgelegt sein muesste. Null im Faelligkeitsmonat,
    #: denn dann ist das Geld gerade abgeflossen.
    ruecklagenstand: Decimal
    #: Person -> monatlicher Anteil. Leer, wenn der Posten nicht geteilt ist.
    anteile: dict[str, Decimal]


class Kategoriesumme(BaseModel):
    kategorie: str
    betrag: Decimal
    zaehlt_als_sparen: bool


class PersonBilanz(BaseModel):
    person_id: uuid.UUID
    name: str
    einnahmen: Decimal
    #: Ausgaben auf den eigenen Konten.
    eigene_ausgaben: Decimal
    #: Was in die gemeinsamen Konten fliesst - die Summe aller Anteile.
    einzahlung_gemeinschaft: Decimal
    #: Anteil an den gemeinsamen Einnahmen (Kindergeld und dergleichen).
    gutschrift_gemeinschaft: Decimal
    ausgaben_gesamt: Decimal
    #: Ausgaben ohne Spar-Kategorien und ohne variable Posten.
    feste_kosten: Decimal
    #: Was tatsaechlich in Spar-Kategorien geht.
    sparen: Decimal
    variabel: Decimal
    #: einnahmen - feste_kosten. Die Obergrenze dessen, was sparbar waere.
    moeglich: Decimal
    #: Was nach allem uebrig bleibt. Negativ heisst: die Rechnung geht nicht auf.
    rest: Decimal
    sparquote: Decimal
    moegliche_sparquote: Decimal
    nach_kategorie: list[Kategoriesumme]


class Gemeinschaftsbilanz(BaseModel):
    einnahmen: Decimal
    ausgaben: Decimal
    #: Was die Personen zusammen einzahlen muessen: Ausgaben minus eigene
    #: Einnahmen der gemeinsamen Konten.
    bedarf: Decimal
    #: Posten auf gemeinsamen Konten ohne Aufteilung. Die zahlt niemand -
    #: deshalb stehen sie namentlich da und nicht nur als Zahl.
    ohne_aufteilung: list[str]


class Uebersicht(BaseModel):
    jahr: int
    monat: int
    personen: list[PersonBilanz]
    gemeinschaft: Gemeinschaftsbilanz
    #: Was die Bank in diesem Monat abbucht.
    faellig: list[PostenZeile]
    #: Alles, was seltener als monatlich kommt - mit dem Stand der Ruecklage.
    ruecklagen: list[PostenZeile]
    ruecklagen_summe: Decimal
    alle: list[PostenZeile]


class Zusammenfassung(BaseModel):
    """Die Zahlen fuer die Kachel."""

    konten: int
    posten: int
    einnahmen: Decimal
    ausgaben: Decimal
    rest: Decimal
    ruecklagen_summe: Decimal
    faellig_im_monat: int


# ---------------------------------------------------------------- Flussbild

Knotenart = Literal["einnahme", "konto", "kategorie", "posten"]


class Knoten(BaseModel):
    id: str
    beschriftung: str
    art: Knotenart
    #: Spalte von links. Berechnet als laengster Weg von einer Quelle -
    #: damit kein Fluss rueckwaerts laeuft, egal wie die Konten verkettet sind.
    ebene: int
    betrag: Decimal


class Fluss(BaseModel):
    von: str
    nach: str
    betrag: Decimal


class Flussbild(BaseModel):
    knoten: list[Knoten]
    fluesse: list[Fluss]
    ebenen: int
