"""Die Entscheidungen und Rechnungen dieses Artefakts.

Reine Funktionen: keine Datenbank, kein await, keine Fixtures. Genau deshalb
laufen ihre Tests in Millisekunden und die rot-gruen-Schleife bleibt
benutzbar. Alles, was I/O macht, steht in speicher.py.

Der Kern sind drei Gedanken:

1. Ein Posten nennt, was die Bank abbucht - nicht, was monatlich
   zurueckzulegen ist. Die **Monatsrate** rechnet der Dienst, damit beide
   Zahlen nicht auseinanderlaufen koennen.
2. Was auf einem gemeinschaftlichen Konto liegt, wird nach **Gewichten**
   (1:2) auf Personen verteilt - und zwar so, dass die Teile zusammen wieder
   genau den Betrag ergeben. Ein verlorener Cent je Position summiert sich.
3. Die **Ruecklage** ist kein Kontostand, sondern eine Rechnung: Rate mal
   Monate seit der letzten Abbuchung.
"""

from __future__ import annotations

import uuid
from collections import defaultdict
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field
from decimal import ROUND_CEILING, ROUND_HALF_UP, Decimal

from homepi_core import ServiceError

from .schemas import (
    Fluss,
    Flussbild,
    Gemeinschaftsbilanz,
    Kategoriesumme,
    Knoten,
    PersonBilanz,
    PostenZeile,
    Uebersicht,
)

CENT = Decimal("0.01")
NULL = Decimal("0.00")
#: Posten ohne Kategorie bekommen trotzdem eine - sonst fehlt im Flussbild
#: eine Spalte und in der Auswertung eine Zeile.
OHNE_KATEGORIE = "Ohne Kategorie"


class PersonUnbekannt(ServiceError):
    status = 404
    title = "Person unbekannt"


class KontoUnbekannt(ServiceError):
    status = 404
    title = "Konto unbekannt"


class KategorieUnbekannt(ServiceError):
    status = 404
    title = "Kategorie unbekannt"


class PostenUnbekannt(ServiceError):
    status = 404
    title = "Posten unbekannt"


class NameVergeben(ServiceError):
    status = 409
    title = "Name bereits vergeben"


class NochInBenutzung(ServiceError):
    status = 409
    title = "Wird noch verwendet"


class AnteilOhneGewicht(ServiceError):
    status = 422
    title = "Aufteilung ohne Gewicht"


def geld(wert: Decimal) -> Decimal:
    """Auf den Cent, kaufmaennisch. Jede Zahl, die das Haus verlaesst."""
    return wert.quantize(CENT, rounding=ROUND_HALF_UP)


# ------------------------------------------------------------ Rhythmus


def monatsrate(betrag: Decimal, intervall_monate: int) -> Decimal:
    """Was jeden Monat zurueckgelegt werden muss, damit die Abbuchung gedeckt ist.

    Aufgerundet, nicht kaufmaennisch. 169 Euro im Jahr sind 14,0833 im Monat;
    kaufmaennisch gerundet legt man zwoelfmal 14,08 zurueck und hat 168,96 -
    vier Cent zu wenig, genau in dem Monat, in dem die Bank zugreift. Lieber
    zwoelf Cent zu viel auf dem Sparkonto als eine Rueckbuchung. Beim letzten
    Satz dieser Art war das genau der Grund, warum die Tabelle aufrundete.
    """
    return (betrag / intervall_monate).quantize(CENT, rounding=ROUND_CEILING)


def faelligkeiten(intervall_monate: int, faelligkeitsmonat: int) -> tuple[int, ...]:
    """Alle Monate eines Jahres, in denen die Bank zugreift.

    Ausgeschrieben statt errechnet, weil genau hier im Alltag gestritten wird:
    'alle drei Monate ab Februar' ist Februar, Mai, August, November - und das
    will niemand jedes Mal im Kopf aufloesen.
    """
    return tuple(
        sorted(
            ((faelligkeitsmonat - 1 + versatz) % 12) + 1
            for versatz in range(0, 12, intervall_monate)
        )
    )


def monate_seit_faelligkeit(intervall_monate: int, faelligkeitsmonat: int, monat: int) -> int:
    """Wie viele Raten seit der letzten Abbuchung zusammengekommen sind.

    Null im Abbuchungsmonat selbst: dann ist das Geld gerade abgeflossen.
    """
    return (monat - faelligkeitsmonat) % intervall_monate


def ist_faellig(intervall_monate: int, faelligkeitsmonat: int, monat: int) -> bool:
    return monate_seit_faelligkeit(intervall_monate, faelligkeitsmonat, monat) == 0


def ruecklagenstand(
    betrag: Decimal, intervall_monate: int, faelligkeitsmonat: int, monat: int
) -> Decimal:
    """Was zum gegebenen Monat zurueckgelegt sein muesste.

    Kein Kontostand, sondern der Sollwert. Weicht der echte Stand davon ab,
    sieht man es sofort - und genau dafuer ist die Zahl da.
    """
    raten = monate_seit_faelligkeit(intervall_monate, faelligkeitsmonat, monat)
    return geld(monatsrate(betrag, intervall_monate) * raten)


# ------------------------------------------------------------ Aufteilen


def aufteilen(betrag: Decimal, gewichte: Sequence[int]) -> list[Decimal]:
    """Einen Betrag nach Gewichten teilen, ohne dass ein Cent verschwindet.

    Naiv gerundet fehlen bei 1133,47 im Verhaeltnis 1:2 am Ende drei Cent im
    Monat - unauffaellig genug, um ein Jahr lang niemandem zu zieren, und
    teuer genug, um dann niemanden zu finden. Deshalb wird in ganzen Cent
    gerechnet und der Rest nach der Methode des groessten Restes vergeben:
    wer beim Teilen am meisten verloren hat, bekommt den ersten Cent zurueck.
    """
    gesamt = sum(gewichte)
    if gesamt <= 0:
        raise AnteilOhneGewicht("Eine Aufteilung braucht mindestens ein Gewicht über null")

    cent = int((betrag * 100).to_integral_value(rounding=ROUND_HALF_UP))
    zaehler = [cent * gewicht for gewicht in gewichte]
    teile = [wert // gesamt for wert in zaehler]

    # Bei Gleichstand entscheidet die Position - sonst haengt das Ergebnis an
    # der Reihenfolge, in der die Datenbank die Zeilen liefert.
    reihenfolge = sorted(range(len(gewichte)), key=lambda i: (-(zaehler[i] % gesamt), i))
    for i in reihenfolge[: cent - sum(teile)]:
        teile[i] += 1

    return [geld(Decimal(teil) / 100) for teil in teile]


def prozent(teil: Decimal, ganzes: Decimal) -> Decimal:
    """Ein Prozentwert mit einer Nachkommastelle - und ohne Division durch null.

    Eine frisch angelegte Person hat noch kein Konto. Das darf keine
    Ausnahme werfen, sondern soll schlicht null Prozent ergeben.
    """
    if ganzes <= 0:
        return Decimal("0.0")
    return (teil / ganzes * 100).quantize(Decimal("0.1"), rounding=ROUND_HALF_UP)


# ------------------------------------------------------------- Sichten
#
# Was die Auswertung braucht - und nicht mehr. Dadurch haengt sie nicht an
# den Tabellen und bleibt ohne Datenbank testbar.


@dataclass(frozen=True, slots=True)
class PersonSicht:
    id: uuid.UUID
    name: str


@dataclass(frozen=True, slots=True)
class KontoSicht:
    id: uuid.UUID
    name: str
    art: str
    #: None heisst gemeinschaftlich.
    inhaber_id: uuid.UUID | None


@dataclass(frozen=True, slots=True)
class KategorieSicht:
    id: uuid.UUID
    name: str
    zaehlt_als_sparen: bool


@dataclass(frozen=True, slots=True)
class PostenSicht:
    id: uuid.UUID
    name: str
    art: str
    betrag: Decimal
    intervall_monate: int
    faelligkeitsmonat: int
    abbuchungstag: int | None
    konto_id: uuid.UUID
    kategorie_id: uuid.UUID | None
    variabel: bool
    aktiv: bool
    #: (Person, Gewicht). Leer heisst: nicht geteilt.
    anteile: tuple[tuple[uuid.UUID, int], ...] = ()


@dataclass(slots=True)
class _Konto:
    """Was sich je Person waehrend eines Durchgangs ansammelt."""

    einnahmen: Decimal = NULL
    eigene_ausgaben: Decimal = NULL
    einzahlung: Decimal = NULL
    gutschrift: Decimal = NULL
    fest: Decimal = NULL
    sparen: Decimal = NULL
    variabel: Decimal = NULL
    kategorien: dict[str, Decimal] = field(default_factory=dict)

    def verbuchen(self, betrag: Decimal, kategorie: str, sparen: bool, variabel: bool) -> None:
        if sparen:
            self.sparen += betrag
        elif variabel:
            self.variabel += betrag
        else:
            self.fest += betrag
        self.kategorien[kategorie] = self.kategorien.get(kategorie, NULL) + betrag


def _kategoriename(kategorie: KategorieSicht | None) -> str:
    return kategorie.name if kategorie else OHNE_KATEGORIE


def _zeile(
    posten: PostenSicht,
    konten: dict[uuid.UUID, KontoSicht],
    kategorien: dict[uuid.UUID, KategorieSicht],
    monat: int,
) -> PostenZeile:
    kategorie = kategorien.get(posten.kategorie_id) if posten.kategorie_id else None
    rate = monatsrate(posten.betrag, posten.intervall_monate)
    gewichte = [gewicht for _, gewicht in posten.anteile]
    teile = aufteilen(rate, gewichte) if gewichte else []

    return PostenZeile(
        id=posten.id,
        art=posten.art,  # type: ignore[arg-type]
        name=posten.name,
        konto=konten[posten.konto_id].name if posten.konto_id in konten else "",
        kategorie=_kategoriename(kategorie),
        betrag=posten.betrag,
        monatsrate=rate,
        intervall_monate=posten.intervall_monate,
        faelligkeitsmonat=posten.faelligkeitsmonat,
        abbuchungstag=posten.abbuchungstag,
        faellige_monate=list(faelligkeiten(posten.intervall_monate, posten.faelligkeitsmonat)),
        faellig_im_monat=ist_faellig(posten.intervall_monate, posten.faelligkeitsmonat, monat),
        ruecklagenstand=ruecklagenstand(
            posten.betrag, posten.intervall_monate, posten.faelligkeitsmonat, monat
        ),
        anteile={
            str(person): teil for (person, _), teil in zip(posten.anteile, teile, strict=True)
        },
    )


def monatsplan(
    personen: Iterable[PersonSicht],
    konten: Iterable[KontoSicht],
    kategorien: Iterable[KategorieSicht],
    posten: Iterable[PostenSicht],
    *,
    jahr: int,
    monat: int,
) -> Uebersicht:
    """Der ganze Plan fuer einen Monat: wer zahlt was, und was liegt bereit."""
    personen = list(personen)
    konto_nach_id = {k.id: k for k in konten}
    kategorie_nach_id = {k.id: k for k in kategorien}
    # Die Reihenfolge der Kategorien ist eine Entscheidung des Benutzers -
    # die Auswertung erfindet keine eigene.
    rang = {k.name: i for i, k in enumerate(kategorie_nach_id.values())}

    zeilen = {p.id: _zeile(p, konto_nach_id, kategorie_nach_id, monat) for p in posten}
    konten_je_person: dict[uuid.UUID, _Konto] = defaultdict(_Konto)
    gemeinschaft_ein = NULL
    gemeinschaft_aus = NULL
    ohne_aufteilung: list[str] = []

    for eintrag in posten:
        if not eintrag.aktiv:
            continue

        zeile = zeilen[eintrag.id]
        konto = konto_nach_id.get(eintrag.konto_id)
        if konto is None:
            continue
        kategorie = kategorie_nach_id.get(eintrag.kategorie_id) if eintrag.kategorie_id else None
        spart = bool(kategorie and kategorie.zaehlt_als_sparen)

        if konto.inhaber_id is not None:
            haushalt = konten_je_person[konto.inhaber_id]
            if eintrag.art == "einnahme":
                haushalt.einnahmen += zeile.monatsrate
            else:
                haushalt.eigene_ausgaben += zeile.monatsrate
                haushalt.verbuchen(zeile.monatsrate, zeile.kategorie, spart, eintrag.variabel)
            continue

        # Ab hier: gemeinschaftliches Konto.
        if eintrag.art == "einnahme":
            gemeinschaft_ein += zeile.monatsrate
        else:
            gemeinschaft_aus += zeile.monatsrate

        if not eintrag.anteile:
            # Namentlich statt nur als Zahl: ein gemeinsamer Posten, den
            # niemand traegt, ist ein Fehler in der Eingabe - und der ist nur
            # zu beheben, wenn man weiss, welcher es ist.
            ohne_aufteilung.append(eintrag.name)
            continue

        for (person_id, _), teil in zip(
            eintrag.anteile,
            aufteilen(zeile.monatsrate, [g for _, g in eintrag.anteile]),
            strict=True,
        ):
            haushalt = konten_je_person[person_id]
            if eintrag.art == "einnahme":
                haushalt.gutschrift += teil
            else:
                haushalt.einzahlung += teil
                haushalt.verbuchen(teil, zeile.kategorie, spart, eintrag.variabel)

    bilanzen = [
        _bilanz(person, konten_je_person[person.id], rang, kategorie_nach_id) for person in personen
    ]

    alle = sorted(zeilen.values(), key=lambda z: (z.kategorie, z.name))
    ruecklagen = [z for z in alle if z.intervall_monate > 1]

    return Uebersicht(
        jahr=jahr,
        monat=monat,
        personen=bilanzen,
        gemeinschaft=Gemeinschaftsbilanz(
            einnahmen=geld(gemeinschaft_ein),
            ausgaben=geld(gemeinschaft_aus),
            bedarf=geld(gemeinschaft_aus - gemeinschaft_ein),
            ohne_aufteilung=sorted(ohne_aufteilung),
        ),
        faellig=[z for z in alle if z.faellig_im_monat],
        ruecklagen=ruecklagen,
        ruecklagen_summe=geld(sum((z.ruecklagenstand for z in ruecklagen), NULL)),
        alle=alle,
    )


def _bilanz(
    person: PersonSicht,
    konto: _Konto,
    rang: dict[str, int],
    kategorien: dict[uuid.UUID, KategorieSicht],
) -> PersonBilanz:
    spar_namen = {k.name for k in kategorien.values() if k.zaehlt_als_sparen}
    # Die Gutschrift aus gemeinsamen Einnahmen ist Geld der Person - sonst
    # waere ihre Sparquote kleiner, als sie ist.
    basis = konto.einnahmen + konto.gutschrift
    ausgaben = konto.eigene_ausgaben + konto.einzahlung
    moeglich = basis - konto.fest

    return PersonBilanz(
        person_id=person.id,
        name=person.name,
        einnahmen=geld(konto.einnahmen),
        eigene_ausgaben=geld(konto.eigene_ausgaben),
        einzahlung_gemeinschaft=geld(konto.einzahlung),
        gutschrift_gemeinschaft=geld(konto.gutschrift),
        ausgaben_gesamt=geld(ausgaben),
        feste_kosten=geld(konto.fest),
        sparen=geld(konto.sparen),
        variabel=geld(konto.variabel),
        moeglich=geld(moeglich),
        rest=geld(basis - ausgaben),
        sparquote=prozent(konto.sparen, basis),
        moegliche_sparquote=prozent(moeglich, basis),
        nach_kategorie=[
            Kategoriesumme(
                kategorie=name,
                betrag=geld(betrag),
                zaehlt_als_sparen=name in spar_namen,
            )
            for name, betrag in sorted(
                konto.kategorien.items(), key=lambda paar: (rang.get(paar[0], 999), paar[0])
            )
        ],
    )


# ------------------------------------------------------------- Flussbild


def _verteilerkonto(person: uuid.UUID, konten: Sequence[KontoSicht]) -> KontoSicht | None:
    """Das Konto, auf dem das Geld dieser Person ankommt.

    Die Angabe 'verteiler' gewinnt. Wer keines so benannt hat, bekommt sein
    erstes Konto - lieber ein Bild mit einer fragwuerdigen Kante als gar
    keines.
    """
    eigene = [k for k in konten if k.inhaber_id == person]
    verteiler = [k for k in eigene if k.art == "verteiler"]
    kandidaten = verteiler or eigene
    return kandidaten[0] if kandidaten else None


def _woher(
    posten: PostenSicht, konto: KontoSicht, rate: Decimal
) -> list[tuple[uuid.UUID, Decimal]]:
    """Wer dieses Geld auf das Konto bringen muss, und wie viel davon.

    Beim gemeinschaftlichen Konto sind das die Beteiligten nach ihren
    Gewichten, beim persoenlichen genau eine Person: der Inhaber. Ein
    gemeinsamer Posten ohne Aufteilung gibt niemanden zurueck - im Monatsplan
    steht er dafuer namentlich unter ``ohne_aufteilung``.
    """
    if konto.inhaber_id is not None:
        return [(konto.inhaber_id, rate)]
    if not posten.anteile:
        return []
    return [
        (person_id, teil)
        for (person_id, _), teil in zip(
            posten.anteile,
            aufteilen(rate, [gewicht for _, gewicht in posten.anteile]),
            strict=True,
        )
    ]


def flussbild(
    personen: Iterable[PersonSicht],
    konten: Iterable[KontoSicht],
    kategorien: Iterable[KategorieSicht],
    posten: Iterable[PostenSicht],
) -> Flussbild:
    """Woher das Geld kommt und wohin es geht - als gerichteter Graph.

    Die Ebenen rechnet dieses Modul aus, nicht die Oberflaeche: wie weit
    rechts ein Knoten steht, ist eine Aussage ueber den Haushalt und keine
    ueber Pixel. Die Oberflaeche macht daraus nur noch Baender.
    """
    konten = list(konten)
    konto_nach_id = {k.id: k for k in konten}
    kategorie_nach_id = {k.id: k for k in kategorien}
    aktive = [p for p in posten if p.aktiv and p.betrag > 0]

    beschriftung: dict[str, tuple[str, str]] = {}
    kanten: dict[tuple[str, str], Decimal] = defaultdict(Decimal)

    def knoten_id(art: str, schluessel: str, wort: str) -> str:
        kennung = f"{art}:{schluessel}"
        beschriftung[kennung] = (wort, art)
        return kennung

    for eintrag in aktive:
        konto = konto_nach_id.get(eintrag.konto_id)
        if konto is None:
            continue

        rate = monatsrate(eintrag.betrag, eintrag.intervall_monate)
        konto_knoten = knoten_id("konto", str(konto.id), konto.name)

        if eintrag.art == "einnahme":
            kanten[(knoten_id("einnahme", str(eintrag.id), eintrag.name), konto_knoten)] += rate
            continue

        kategorie = kategorie_nach_id.get(eintrag.kategorie_id) if eintrag.kategorie_id else None
        schluessel = str(kategorie.id) if kategorie else "ohne"
        kategorie_knoten = knoten_id("kategorie", schluessel, _kategoriename(kategorie))

        kanten[(konto_knoten, kategorie_knoten)] += rate
        kanten[(kategorie_knoten, knoten_id("posten", str(eintrag.id), eintrag.name))] += rate

        # Geld, das von einem Konto abfliesst, muss vorher dorthin gekommen
        # sein. Beim Gemeinschaftskonto sind das die Anteile der Personen,
        # beim Verbrauchskonto die Umbuchung vom eigenen Verteilerkonto -
        # dasselbe Prinzip, deshalb derselbe Zweig.
        #
        # Ohne den zweiten Fall hing das Verbrauchskonto im Bild an gar nichts
        # und stand als eigene Quelle ganz links, als faende sich das Geld
        # dort von selbst ein.
        for person_id, teil in _woher(eintrag, konto, rate):
            quelle = _verteilerkonto(person_id, konten)
            if quelle is None or quelle.id == konto.id:
                continue
            kanten[(knoten_id("konto", str(quelle.id), quelle.name), konto_knoten)] += teil

    ebenen = _ebenen(beschriftung, kanten)
    zufluss: dict[str, Decimal] = defaultdict(Decimal)
    abfluss: dict[str, Decimal] = defaultdict(Decimal)
    for (von, nach), betrag in kanten.items():
        abfluss[von] += betrag
        zufluss[nach] += betrag

    knoten = [
        Knoten(
            id=kennung,
            beschriftung=wort,
            art=art,  # type: ignore[arg-type]
            ebene=ebenen[kennung],
            betrag=geld(max(zufluss[kennung], abfluss[kennung])),
        )
        for kennung, (wort, art) in beschriftung.items()
    ]
    knoten.sort(key=lambda k: (k.ebene, -k.betrag, k.beschriftung))

    return Flussbild(
        knoten=knoten,
        fluesse=[
            Fluss(von=von, nach=nach, betrag=geld(betrag))
            for (von, nach), betrag in sorted(kanten.items())
        ],
        ebenen=max(ebenen.values(), default=-1) + 1,
    )


def _ebenen(
    beschriftung: dict[str, tuple[str, str]], kanten: dict[tuple[str, str], Decimal]
) -> dict[str, int]:
    """Spalte je Knoten: der laengste Weg von einer Quelle.

    Nicht die Art allein entscheidet, denn ein Konto kann von einem anderen
    gespeist werden - das Gemeinschaftskonto steht deshalb eine Spalte weiter
    rechts als die Konten, die es fuellen. Gerechnet wird durch wiederholtes
    Nachziehen, hoechstens so oft, wie es Knoten gibt: ein Weg kann nicht
    laenger sein, ohne sich zu schliessen.
    """
    ebene = dict.fromkeys(beschriftung, 0)
    for _ in range(len(beschriftung)):
        geaendert = False
        for von, nach in kanten:
            if ebene[nach] <= ebene[von]:
                ebene[nach] = ebene[von] + 1
                geaendert = True
        if not geaendert:
            break
    return ebene
