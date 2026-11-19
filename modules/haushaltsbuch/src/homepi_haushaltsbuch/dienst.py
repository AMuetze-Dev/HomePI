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


class AnlageOhnePerson(ServiceError):
    status = 422
    title = "Anlage ohne Person"


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
    #: Was auf dem Konto liegen bleibt, bevor angelegt wird. Die Anlage
    #: nimmt nur, was darueber hinaus uebrig ist.
    sockel: Decimal = NULL


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
    #: Gesetzt heisst: Dieser Posten hat keinen festen Betrag, sondern
    #: nimmt diesen Anteil an dem, was der Person uebrig bleibt.
    anlage_gewicht: int | None = None


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
    #: Davon aus dem Ueberschuss angelegt. Steckt auch in `sparen` oder
    #: `fest` - es ist eine zweite Sicht auf dieselben Betraege, nicht eine
    #: weitere Ausgabe.
    anlage: Decimal = NULL
    kategorien: dict[str, Decimal] = field(default_factory=dict)

    def verbuchen(
        self,
        betrag: Decimal,
        kategorie: str,
        sparen: bool,
        variabel: bool,
        anlage: bool = False,
    ) -> None:
        if sparen:
            self.sparen += betrag
        elif variabel:
            self.variabel += betrag
        else:
            self.fest += betrag
        if anlage:
            self.anlage += betrag
        self.kategorien[kategorie] = self.kategorien.get(kategorie, NULL) + betrag


def _kategoriename(kategorie: KategorieSicht | None) -> str:
    return kategorie.name if kategorie else OHNE_KATEGORIE


def _zeile(
    posten: PostenSicht,
    konten: dict[uuid.UUID, KontoSicht],
    kategorien: dict[uuid.UUID, KategorieSicht],
    monat: int,
    rate: Decimal | None = None,
) -> PostenZeile:
    """Eine Zeile des Monatsplans.

    ``rate`` setzt den Monatsbetrag von aussen - das brauchen die
    Anlageposten, deren Betrag erst aus dem Ueberschuss entsteht. Ohne
    Angabe rechnet die Zeile ihn wie immer aus dem Betrag und dem Rhythmus.
    """
    kategorie = kategorien.get(posten.kategorie_id) if posten.kategorie_id else None
    if rate is None:
        rate = monatsrate(posten.betrag, posten.intervall_monate)
    gewichte = [gewicht for _, gewicht in posten.anteile]
    teile = aufteilen(rate, gewichte) if gewichte else []

    return PostenZeile(
        id=posten.id,
        art=posten.art,  # type: ignore[arg-type]
        name=posten.name,
        konto=konten[posten.konto_id].name if posten.konto_id in konten else "",
        kategorie=_kategoriename(kategorie),
        betrag=rate if posten.anlage_gewicht is not None else posten.betrag,
        monatsrate=rate,
        intervall_monate=posten.intervall_monate,
        faelligkeitsmonat=posten.faelligkeitsmonat,
        abbuchungstag=posten.abbuchungstag,
        faellige_monate=list(faelligkeiten(posten.intervall_monate, posten.faelligkeitsmonat)),
        faellig_im_monat=ist_faellig(posten.intervall_monate, posten.faelligkeitsmonat, monat),
        ruecklagenstand=(
            NULL
            if posten.anlage_gewicht is not None
            else ruecklagenstand(
                posten.betrag, posten.intervall_monate, posten.faelligkeitsmonat, monat
            )
        ),
        anteile={
            str(person): teil for (person, _), teil in zip(posten.anteile, teile, strict=True)
        },
    )


@dataclass(slots=True)
class _Durchgang:
    """Was ein Lauf ueber alle Posten ergibt."""

    je_person: dict[uuid.UUID, _Konto] = field(default_factory=lambda: defaultdict(_Konto))
    gemeinschaft_ein: Decimal = NULL
    gemeinschaft_aus: Decimal = NULL
    ohne_aufteilung: list[str] = field(default_factory=list)


def _durchrechnen(
    konto_nach_id: dict[uuid.UUID, KontoSicht],
    kategorie_nach_id: dict[uuid.UUID, KategorieSicht],
    posten: Sequence[PostenSicht],
    raten: dict[uuid.UUID, Decimal],
) -> _Durchgang:
    """Verteilt die Monatsbetraege auf die Personen und die Gemeinschaft.

    ``raten`` sagt, mit welchem Betrag ein Posten zaehlt - und welche
    ueberhaupt zaehlen: Was dort fehlt, bleibt aussen vor. Genau das ist der
    Grund fuer diese eigene Funktion. Der Topf, aus dem die Anlageposten
    schoepfen, ist das Ergebnis eines Laufs OHNE sie; mit ihnen waere die
    Rechnung im Kreis gelaufen.
    """
    durchgang = _Durchgang()

    for eintrag in posten:
        rate = raten.get(eintrag.id)
        if rate is None:
            continue

        konto = konto_nach_id.get(eintrag.konto_id)
        if konto is None:
            continue
        kategorie = kategorie_nach_id.get(eintrag.kategorie_id) if eintrag.kategorie_id else None
        name = _kategoriename(kategorie)
        spart = bool(kategorie and kategorie.zaehlt_als_sparen)
        angelegt = eintrag.anlage_gewicht is not None

        if konto.inhaber_id is not None:
            haushalt = durchgang.je_person[konto.inhaber_id]
            if eintrag.art == "einnahme":
                haushalt.einnahmen += rate
            else:
                haushalt.eigene_ausgaben += rate
                haushalt.verbuchen(rate, name, spart, eintrag.variabel, angelegt)
            continue

        # Ab hier: gemeinschaftliches Konto.
        if eintrag.art == "einnahme":
            durchgang.gemeinschaft_ein += rate
        else:
            durchgang.gemeinschaft_aus += rate

        if not eintrag.anteile:
            # Namentlich statt nur als Zahl: ein gemeinsamer Posten, den
            # niemand traegt, ist ein Fehler in der Eingabe - und der ist nur
            # zu beheben, wenn man weiss, welcher es ist.
            durchgang.ohne_aufteilung.append(eintrag.name)
            continue

        for (person_id, _), teil in zip(
            eintrag.anteile,
            aufteilen(rate, [g for _, g in eintrag.anteile]),
            strict=True,
        ):
            haushalt = durchgang.je_person[person_id]
            if eintrag.art == "einnahme":
                haushalt.gutschrift += teil
            else:
                haushalt.einzahlung += teil
                haushalt.verbuchen(teil, name, spart, eintrag.variabel, angelegt)

    return durchgang


def anlagebetraege(
    personen: Iterable[PersonSicht],
    konten: Iterable[KontoSicht],
    kategorien: Iterable[KategorieSicht],
    posten: Iterable[PostenSicht],
) -> dict[uuid.UUID, Decimal]:
    """Was jeder Anlageposten in diesem Monat bekommt.

    Ein Anlageposten legt sich nicht auf einen Betrag fest, sondern auf
    einen Anteil an dem, was seiner Person uebrig bleibt. Gerechnet wird in
    zwei Schritten, und die Reihenfolge ist die ganze Idee:

    1. Der Haushalt ohne die Anlageposten. Was dabei uebrig bleibt, ist der
       Ueberschuss der Person - abzueglich ihres Sockels, der liegen bleibt.
    2. Dieser Topf wird nach den Gewichten verteilt, mit derselben
       Cent-genauen Teilung wie eine Aufteilung zwischen Personen.

    Ein Topf ist nie negativ: Wer mehr ausgibt als einnimmt, legt nichts an.
    Das waere sonst eine Abbuchung in die falsche Richtung.

    Die Zuordnung laeuft ueber den Inhaber des Kontos - ein Anlageposten
    gehoert zu einer Person. Liegt er doch auf einem gemeinsamen Konto,
    findet er keinen Topf und bleibt bei null; den Fall weist der Speicher
    beim Anlegen ab.
    """
    posten = list(posten)
    konto_nach_id = {k.id: k for k in konten}
    gewichtet = [p for p in posten if p.aktiv and p.anlage_gewicht]
    if not gewichtet:
        return {}

    vorlauf = _durchrechnen(
        konto_nach_id,
        {k.id: k for k in kategorien},
        posten,
        {
            p.id: monatsrate(p.betrag, p.intervall_monate)
            for p in posten
            if p.aktiv and p.anlage_gewicht is None
        },
    )

    betraege: dict[uuid.UUID, Decimal] = {}
    for person in personen:
        meine = [
            p
            for p in gewichtet
            if (konto := konto_nach_id.get(p.konto_id)) and konto.inhaber_id == person.id
        ]
        if not meine:
            continue

        konto_stand = vorlauf.je_person[person.id]
        uebrig = (
            konto_stand.einnahmen
            + konto_stand.gutschrift
            - konto_stand.eigene_ausgaben
            - konto_stand.einzahlung
        )
        topf = max(NULL, uebrig - person.sockel)

        gewichte = [p.anlage_gewicht or 0 for p in meine]
        for eintrag, teil in zip(meine, aufteilen(topf, gewichte), strict=True):
            betraege[eintrag.id] = teil

    return betraege


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
    posten = list(posten)
    konto_nach_id = {k.id: k for k in konten}
    kategorie_nach_id = {k.id: k for k in kategorien}
    # Die Reihenfolge der Kategorien ist eine Entscheidung des Benutzers -
    # die Auswertung erfindet keine eigene.
    rang = {k.name: i for i, k in enumerate(kategorie_nach_id.values())}

    angelegt = anlagebetraege(personen, konten, kategorie_nach_id.values(), posten)

    def rate(eintrag: PostenSicht) -> Decimal:
        if eintrag.anlage_gewicht is not None:
            return angelegt.get(eintrag.id, NULL)
        return monatsrate(eintrag.betrag, eintrag.intervall_monate)

    zeilen = {p.id: _zeile(p, konto_nach_id, kategorie_nach_id, monat, rate(p)) for p in posten}
    durchgang = _durchrechnen(
        konto_nach_id,
        kategorie_nach_id,
        posten,
        {p.id: rate(p) for p in posten if p.aktiv},
    )
    konten_je_person = durchgang.je_person
    gemeinschaft_ein = durchgang.gemeinschaft_ein
    gemeinschaft_aus = durchgang.gemeinschaft_aus
    ohne_aufteilung = durchgang.ohne_aufteilung

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
        anlage=geld(konto.anlage),
        sockel=geld(person.sockel),
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
    personen = list(personen)
    posten = list(posten)
    konto_nach_id = {k.id: k for k in konten}
    kategorie_nach_id = {k.id: k for k in kategorien}

    # Ein Anlageposten traegt keinen eigenen Betrag - er bekommt ihn aus dem
    # Ueberschuss. Ohne diese Zeile fiele jedes Depot aus dem Bild, sobald es
    # sich daran orientiert.
    angelegt = anlagebetraege(personen, konten, kategorie_nach_id.values(), posten)

    def monatlich(eintrag: PostenSicht) -> Decimal:
        if eintrag.anlage_gewicht is not None:
            return angelegt.get(eintrag.id, NULL)
        return monatsrate(eintrag.betrag, eintrag.intervall_monate)

    aktive = [p for p in posten if p.aktiv and monatlich(p) > 0]

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

        rate = monatlich(eintrag)
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
