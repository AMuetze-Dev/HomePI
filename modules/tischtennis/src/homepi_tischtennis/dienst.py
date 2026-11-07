"""Die Entscheidungen dieses Artefakts: Saetze, Tabelle, Zeitplan, Zustaende.

REIN: keine Datenbank, kein await, keine Fixtures. Genau deshalb laufen die
Tests dazu in Millisekunden - und nur deshalb benutzt man die rot-gruen-
Schleife wirklich. Alles, was I/O macht, gehoert in speicher.py; das
Auswuerfeln steht in los.py und ist ebenso rein.

Faustregel: Entscheidungen sind rein, Seiteneffekte sind dumm.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, replace
from datetime import datetime, timedelta
from math import ceil
from typing import Literal

from homepi_core import ServiceError

#: Ein Teilnehmer, von aussen betrachtet. Im Betrieb ``str(teilnehmer.id)``.
Kennung = str

Satz = tuple[int, int]

Seite = Literal["heim", "gast"]

#: Ein Sieg zaehlt zwei Punkte, eine Niederlage keinen. Das ist die
#: uebliche Zaehlung im Tischtennis und nebenbei die, die ein Gleichstand
#: nicht halbieren kann.
PUNKTE_SIEG = 2


class TurnierUnbekannt(ServiceError):
    status = 404
    title = "Turnier unbekannt"


class TeilnehmerUnbekannt(ServiceError):
    status = 404
    title = "Teilnehmer unbekannt"


class SpielUnbekannt(ServiceError):
    status = 404
    title = "Spiel unbekannt"


class NameVergeben(ServiceError):
    status = 409
    title = "Name bereits vergeben"


class FalscherZustand(ServiceError):
    """Die Aktion waere richtig, der Zeitpunkt ist es nicht."""

    status = 409
    title = "Im jetzigen Zustand nicht moeglich"


class LosUnmoeglich(ServiceError):
    status = 409
    title = "So laesst sich nicht auslosen"


class UngueltigesErgebnis(ServiceError):
    """Kein Pydantic-Fall: ob 11:10 moeglich ist, weiss nur die Spielregel."""

    status = 422
    title = "Ergebnis gibt es nicht"


@dataclass(frozen=True, slots=True)
class Entscheidung:
    """Eine Erlaubnis mit dem Grund daran.

    Der Grund haengt an der Entscheidung und nicht im Aufrufer: so steht er
    im Backend einmal und erscheint beim Benutzer woertlich.
    """

    erlaubt: bool
    grund: str = ""


@dataclass(frozen=True, slots=True)
class Spielstand:
    saetze_heim: int
    saetze_gast: int
    sieger: Seite | None
    entschieden: bool


def satz_pruefen(satz: Satz, punkte_bis: int) -> None:
    """Gibt es diesen Satz?

    Die Regel, die am haeufigsten falsch eingetippt wird, ist die letzte:
    ab 10:10 geht es weiter, bis einer zwei Punkte vorn liegt. 11:10 ist
    kein Satzende, 13:11 schon.
    """
    heim, gast = satz
    if heim < 0 or gast < 0:
        raise UngueltigesErgebnis(f"Ein Satz hat keine negativen Punkte: {heim}:{gast}")

    hoch, tief = max(heim, gast), min(heim, gast)
    if hoch < punkte_bis:
        raise UngueltigesErgebnis(
            f"Ein Satz geht bis mindestens {punkte_bis} Punkte - {heim}:{gast} ist nicht zu Ende"
        )
    if hoch - tief < 2:
        raise UngueltigesErgebnis(
            f"Ein Satz endet mit mindestens zwei Punkten Vorsprung, nicht {heim}:{gast}"
        )
    if tief >= punkte_bis - 1 and hoch - tief != 2:
        raise UngueltigesErgebnis(
            f"Ab {punkte_bis - 1}:{punkte_bis - 1} endet der Satz genau zwei Punkte "
            f"spaeter - {heim}:{gast} gibt es nicht"
        )
    if hoch > punkte_bis and tief < punkte_bis - 1:
        raise UngueltigesErgebnis(
            f"Ueber {punkte_bis} hinaus geht es nur ab {punkte_bis - 1}:{punkte_bis - 1} - "
            f"{heim}:{gast} gibt es nicht"
        )


def satzbilanz(saetze: Sequence[Satz]) -> tuple[int, int]:
    """Gewonnene Saetze je Seite. Zaehlt, prueft nicht."""
    heim = sum(1 for links, rechts in saetze if links > rechts)
    gast = sum(1 for links, rechts in saetze if rechts > links)
    return heim, gast


def noetige_saetze(best_of: int) -> int:
    return best_of // 2 + 1


def spielstand(saetze: Sequence[Satz], best_of: int, punkte_bis: int) -> Spielstand:
    """Prueft das ganze Ergebnis und sagt, wer gewonnen hat.

    Ein Ergebnis ohne Saetze ist in Ordnung: so sieht jedes Spiel aus, das
    noch nicht gespielt wurde.
    """
    noetig = noetige_saetze(best_of)
    if len(saetze) > best_of:
        raise UngueltigesErgebnis(
            f"Bei best of {best_of} gibt es hoechstens {best_of} Saetze, hier stehen {len(saetze)}"
        )

    heim = gast = 0
    for nummer, satz in enumerate(saetze, start=1):
        if heim >= noetig or gast >= noetig:
            raise UngueltigesErgebnis(
                f"Das Spiel war nach {nummer - 1} Saetzen entschieden ({heim}:{gast}) - "
                f"einen {nummer}. Satz kann es nicht geben"
            )
        satz_pruefen(satz, punkte_bis)
        if satz[0] > satz[1]:
            heim += 1
        else:
            gast += 1

    sieger: Seite | None = "heim" if heim >= noetig else "gast" if gast >= noetig else None
    return Spielstand(
        saetze_heim=heim, saetze_gast=gast, sieger=sieger, entschieden=sieger is not None
    )


@dataclass(frozen=True, slots=True)
class Ergebnis:
    """Ein gespieltes Spiel, wie die Tabelle es braucht.

    ``best_of`` steht mit dabei, weil sich ohne es nicht sagen laesst, ob
    ein Spiel zu Ende ist: 2:1 ist bei best of 3 ein Sieg und bei best of 5
    ein Zwischenstand.
    """

    heim: Kennung
    gast: Kennung
    saetze: tuple[Satz, ...]
    best_of: int = 5


@dataclass(frozen=True, slots=True)
class TabellenZeile:
    teilnehmer: Kennung
    platz: int
    spiele: int
    siege: int
    niederlagen: int
    punkte: int
    saetze_fuer: int
    saetze_gegen: int
    baelle_fuer: int
    baelle_gegen: int

    @property
    def satzdifferenz(self) -> int:
        return self.saetze_fuer - self.saetze_gegen

    @property
    def balldifferenz(self) -> int:
        return self.baelle_fuer - self.baelle_gegen


@dataclass(slots=True)
class _Konto:
    siege: int = 0
    niederlagen: int = 0
    saetze_fuer: int = 0
    saetze_gegen: int = 0
    baelle_fuer: int = 0
    baelle_gegen: int = 0

    def buchen(self, eigene: Sequence[Satz], als_heim: bool, gewonnen: bool) -> None:
        heim_saetze, gast_saetze = satzbilanz(eigene)
        heim_baelle = sum(links for links, _ in eigene)
        gast_baelle = sum(rechts for _, rechts in eigene)

        self.saetze_fuer += heim_saetze if als_heim else gast_saetze
        self.saetze_gegen += gast_saetze if als_heim else heim_saetze
        self.baelle_fuer += heim_baelle if als_heim else gast_baelle
        self.baelle_gegen += gast_baelle if als_heim else heim_baelle
        if gewonnen:
            self.siege += 1
        else:
            self.niederlagen += 1

    @property
    def spiele(self) -> int:
        return self.siege + self.niederlagen


@dataclass(slots=True)
class _Kleinbilanz:
    """Dasselbe nur zwischen den Punktgleichen - der direkte Vergleich."""

    punkte: int = 0
    satzdifferenz: int = 0
    balldifferenz: int = 0


def _beendet(ergebnis: Ergebnis) -> bool:
    heim, gast = satzbilanz(ergebnis.saetze)
    return max(heim, gast) >= noetige_saetze(ergebnis.best_of)


def tabelle(
    teilnehmer: Sequence[Kennung],
    ergebnisse: Iterable[Ergebnis],
    freilose: Mapping[Kennung, int] | None = None,
) -> list[TabellenZeile]:
    """Die Tabelle, sortiert und mit Platzziffern.

    Gezaehlt werden nur beendete Spiele - ein laufendes Spiel steht mit 1:0
    in der Satzbilanz und saehe in der Tabelle wie ein halber Sieg aus.

    Die Reihenfolge: Punkte, dann der direkte Vergleich unter den
    Punktgleichen, dann Satzdifferenz, dann Balldifferenz, dann der Name.
    Der Name zuletzt ist kein Schoenheitsfehler, sondern der Grund, warum
    die Tabelle bei zwei Abrufen gleich aussieht.

    ``freilose`` sind geschenkte Siege aus dem Schweizer System: sie zaehlen
    Punkte, aber keine Saetze und keine Baelle. Wer ein Freilos hatte, soll
    dadurch nicht an die Spitze rutschen - und auch nicht abstuerzen, weil
    ihm ein Spiel fehlt.
    """
    gezaehlt = [e for e in ergebnisse if _beendet(e)]

    konten: dict[Kennung, _Konto] = {wer: _Konto() for wer in teilnehmer}
    for wer, anzahl in (freilose or {}).items():
        if wer in konten:
            konten[wer].siege += anzahl
    for spiel in gezaehlt:
        heim_saetze, gast_saetze = satzbilanz(spiel.saetze)
        heim_gewinnt = heim_saetze > gast_saetze
        if spiel.heim in konten:
            konten[spiel.heim].buchen(spiel.saetze, als_heim=True, gewonnen=heim_gewinnt)
        if spiel.gast in konten:
            konten[spiel.gast].buchen(spiel.saetze, als_heim=False, gewonnen=not heim_gewinnt)

    zeilen = [
        TabellenZeile(
            teilnehmer=wer,
            platz=0,
            spiele=konto.spiele,
            siege=konto.siege,
            niederlagen=konto.niederlagen,
            punkte=konto.siege * PUNKTE_SIEG,
            saetze_fuer=konto.saetze_fuer,
            saetze_gegen=konto.saetze_gegen,
            baelle_fuer=konto.baelle_fuer,
            baelle_gegen=konto.baelle_gegen,
        )
        for wer, konto in konten.items()
    ]

    klein = _direkter_vergleich(zeilen, gezaehlt)

    def ordnung(zeile: TabellenZeile) -> tuple[int, int, int, int, int, int, str]:
        eigen = klein[zeile.teilnehmer]
        return (
            -zeile.punkte,
            -eigen.punkte,
            -eigen.satzdifferenz,
            -eigen.balldifferenz,
            -zeile.satzdifferenz,
            -zeile.balldifferenz,
            zeile.teilnehmer,
        )

    sortiert = sorted(zeilen, key=ordnung)
    # platz wird erst hier gesetzt: vorher ist er nicht bekannt, und ein
    # Feld, das waehrend des Aufbaus falsch ist, wird irgendwann gelesen.
    return [replace(zeile, platz=nummer) for nummer, zeile in enumerate(sortiert, start=1)]


def _direkter_vergleich(
    zeilen: Sequence[TabellenZeile], ergebnisse: Sequence[Ergebnis]
) -> dict[Kennung, _Kleinbilanz]:
    """Je Punktgleichheitsgruppe eine kleine Tabelle aus deren Spielen.

    Wer nur mit einem Punktestand allein steht, bekommt eine leere Bilanz -
    sie aendert dann an der Reihenfolge nichts.
    """
    bilanzen: dict[Kennung, _Kleinbilanz] = {z.teilnehmer: _Kleinbilanz() for z in zeilen}

    nach_punkten: dict[int, list[Kennung]] = {}
    for zeile in zeilen:
        nach_punkten.setdefault(zeile.punkte, []).append(zeile.teilnehmer)

    for gleiche in nach_punkten.values():
        if len(gleiche) < 2:
            continue
        kreis = set(gleiche)
        for spiel in ergebnisse:
            if spiel.heim not in kreis or spiel.gast not in kreis:
                continue
            heim_saetze, gast_saetze = satzbilanz(spiel.saetze)
            heim_baelle = sum(links for links, _ in spiel.saetze)
            gast_baelle = sum(rechts for _, rechts in spiel.saetze)

            heim, gast = bilanzen[spiel.heim], bilanzen[spiel.gast]
            heim.satzdifferenz += heim_saetze - gast_saetze
            gast.satzdifferenz += gast_saetze - heim_saetze
            heim.balldifferenz += heim_baelle - gast_baelle
            gast.balldifferenz += gast_baelle - heim_baelle
            if heim_saetze > gast_saetze:
                heim.punkte += PUNKTE_SIEG
            else:
                gast.punkte += PUNKTE_SIEG

    return bilanzen


def platzierung(zeilen: Sequence[TabellenZeile]) -> list[Kennung]:
    """Die Tabelle als reine Namensliste - so nimmt das Los sie an."""
    return [zeile.teilnehmer for zeile in sorted(zeilen, key=lambda z: z.platz)]


@dataclass(frozen=True, slots=True)
class Spielstandzeile:
    """Was der Zeitplan ueber ein Spiel wissen muss, und nicht mehr."""

    id: str
    zustand: str
    tisch: int | None = None
    begonnen_am: datetime | None = None


@dataclass(frozen=True, slots=True)
class Planzeile:
    spiel: str
    tisch: int
    erwartet_ab: datetime
    laeuft: bool
    #: Das laufende Spiel an diesem Tisch ist der direkte Vorgaenger - wer
    #: hier steht, wird als naechstes aufgerufen. Das ist die Glocke.
    gleich_dran: bool


def planen(
    spiele: Sequence[Spielstandzeile], tische: int, minuten: int, jetzt: datetime
) -> list[Planzeile]:
    """Verteilt die offenen Spiele auf die Tische und schaetzt die Zeiten.

    Die Schaetzung ist eine Schaetzung und wird mit jedem eingetragenen
    Ergebnis neu gerechnet. Zwei Dinge sind trotzdem verlaesslich: ein
    laufendes Spiel belegt seinen Tisch, und keine erwartete Zeit liegt in
    der Vergangenheit - ein Spiel, das laenger dauert als geschaetzt, wuerde
    sonst den ganzen Plan nach hinten in die Vergangenheit schieben.
    """
    dauer = timedelta(minutes=minuten)
    frei: dict[int, datetime] = {nummer: jetzt for nummer in range(1, max(1, tische) + 1)}
    vorgaenger_laeuft: dict[int, bool] = dict.fromkeys(frei, False)
    zeilen: dict[str, Planzeile] = {}

    def freiester() -> int:
        return min(frei, key=lambda nummer: (frei[nummer], nummer))

    for spiel in (s for s in spiele if s.zustand == "laeuft"):
        tisch = spiel.tisch if spiel.tisch in frei else freiester()
        beginn = spiel.begonnen_am or jetzt
        frei[tisch] = max(jetzt, beginn + dauer)
        vorgaenger_laeuft[tisch] = True
        zeilen[spiel.id] = Planzeile(
            spiel=spiel.id, tisch=tisch, erwartet_ab=beginn, laeuft=True, gleich_dran=False
        )

    for spiel in (s for s in spiele if s.zustand == "geplant"):
        tisch = freiester()
        ab = frei[tisch]
        zeilen[spiel.id] = Planzeile(
            spiel=spiel.id,
            tisch=tisch,
            erwartet_ab=ab,
            laeuft=False,
            gleich_dran=vorgaenger_laeuft[tisch],
        )
        frei[tisch] = ab + dauer
        vorgaenger_laeuft[tisch] = False

    # In der Reihenfolge zurueck, in der die Spiele hereinkamen: das ist die
    # Reihenfolge des Spielplans, und der Aufrufer hat sie so sortiert.
    return [zeilen[spiel.id] for spiel in spiele if spiel.id in zeilen]


def geschaetzte_dauer(anzahl_spiele: int, tische: int, minuten: int) -> timedelta:
    """Wie lange das Ganze dauert - die Zahl, nach der der Modus gewaehlt wird.

    Angefangene Durchgaenge zaehlen voll: neun Spiele auf zwei Tischen sind
    fuenf Durchgaenge und nicht viereinhalb.
    """
    durchgaenge = ceil(anzahl_spiele / max(1, tische))
    return timedelta(minutes=durchgaenge * minuten)


def gruppen_vorschlag(anzahl_teilnehmer: int) -> int:
    """Ein Vorschlag, der auf Vierergruppen zielt.

    Vier ist das uebliche Mass: drei Spiele je Person, und die Gruppe ist in
    sechs Spielen durch. Es ist ein Vorschlag im Formular, keine Regel -
    deshalb steht hier auch keine Fehlerbehandlung, sondern immer eine Zahl,
    mit der sich auslosen laesst.
    """
    return max(1, min(anzahl_teilnehmer // 2, round(anzahl_teilnehmer / 4)))


@dataclass(frozen=True, slots=True)
class Stand:
    """Der Fortschritt eines Turniers, soweit die Entscheidung ihn braucht."""

    modus: str
    runde_angesetzt: int
    runden: int
    ko_steht: bool
    offene_spiele: int


Schritt = Literal["spielen", "ko_ansetzen", "runde_ansetzen", "fertig"]


def naechster_schritt(stand: Stand) -> Schritt:
    """Was als Naechstes zu tun ist - die einzige Stelle, die das entscheidet.

    Ohne diese Funktion stuende die Frage "ist das Turnier eigentlich durch?"
    an drei Stellen im Speicher und an einer im Frontend, und eine davon
    waere irgendwann anderer Meinung.
    """
    if stand.offene_spiele > 0:
        return "spielen"
    if stand.modus == "gruppen_ko" and not stand.ko_steht:
        return "ko_ansetzen"
    if stand.modus == "schweizer" and stand.runde_angesetzt < stand.runden:
        return "runde_ansetzen"
    return "fertig"


def darf_auswuerfeln(zustand: str) -> Entscheidung:
    if zustand == "planung":
        return Entscheidung(True)
    if zustand == "laufend":
        return Entscheidung(
            False,
            "Das Turnier laeuft schon. Noch einmal auszuwuerfeln hiesse, die "
            "eingetragenen Ergebnisse auf Spiele zu beziehen, die es dann nicht "
            "mehr gibt. Setze das Turnier dafuer zurueck in die Planung.",
        )
    return Entscheidung(False, "Das Turnier ist beendet")


def darf_teilnehmer_aendern(zustand: str) -> Entscheidung:
    if zustand == "planung":
        return Entscheidung(True)
    return Entscheidung(
        False,
        "Der Spielplan steht schon. Wer jetzt dazukaeme, haette keine Spiele - "
        "und wer wegfiele, hinterliesse Spiele ohne Gegner.",
    )


#: Einstellungen, an denen der ganze Spielplan haengt. Sie zu aendern, waehrend
#: gespielt wird, hiesse: eingetragene Ergebnisse gehoeren zu anderen Regeln
#: als die noch kommenden.
PLANFESTE_FELDER = frozenset(
    {"modus", "anzahl_gruppen", "weiter_pro_gruppe", "runden", "best_of", "punkte_bis"}
)


def darf_einstellung_aendern(zustand: str, abweichend: Iterable[str]) -> Entscheidung:
    """Tische und Minuten gehen immer, die Regeln nur in der Planung."""
    if zustand == "planung":
        return Entscheidung(True)

    verboten = sorted(PLANFESTE_FELDER & set(abweichend))
    if not verboten:
        return Entscheidung(True)
    return Entscheidung(
        False,
        f"Nicht mehr aenderbar, solange gespielt wird: {', '.join(verboten)}. "
        "Tischzahl und geschaetzte Spieldauer gehen jederzeit.",
    )


def ko_bezeichnung(runde: int, runden_gesamt: int) -> str:
    """Wie die KO-Runde heisst.

    Sie haengt an der Rastergroesse und nicht an der Nummer: in einem Raster
    fuer vier ist Runde 1 das Halbfinale, in einem fuer sechzehn das
    Achtelfinale. Das im Frontend zu entscheiden hiesse, ihm die
    Rastergroesse mitzugeben - und dann zweimal zu rechnen.
    """
    namen = {0: "Endspiel", 1: "Halbfinale", 2: "Viertelfinale", 3: "Achtelfinale"}
    return namen.get(runden_gesamt - runde, f"KO-Runde {runde}")


def runde_vollstaendig(zustaende: Sequence[str]) -> bool:
    """Ist die laufende Runde durch? Keine Runde ist nicht vollstaendig."""
    return bool(zustaende) and all(zustand == "beendet" for zustand in zustaende)


__all__ = [
    "Entscheidung",
    "Ergebnis",
    "FalscherZustand",
    "Kennung",
    "LosUnmoeglich",
    "NameVergeben",
    "Planzeile",
    "Satz",
    "Seite",
    "SpielUnbekannt",
    "Spielstand",
    "Spielstandzeile",
    "Stand",
    "TabellenZeile",
    "TeilnehmerUnbekannt",
    "TurnierUnbekannt",
    "UngueltigesErgebnis",
    "darf_auswuerfeln",
    "darf_einstellung_aendern",
    "darf_teilnehmer_aendern",
    "geschaetzte_dauer",
    "gruppen_vorschlag",
    "ko_bezeichnung",
    "naechster_schritt",
    "noetige_saetze",
    "planen",
    "platzierung",
    "runde_vollstaendig",
    "satz_pruefen",
    "satzbilanz",
    "spielstand",
    "tabelle",
]
