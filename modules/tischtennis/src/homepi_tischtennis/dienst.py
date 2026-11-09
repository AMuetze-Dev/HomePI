"""Die Entscheidungen dieses Artefakts: Ergebnis, Tabelle, Zeitplan, Zustaende.

REIN: keine Datenbank, kein await, keine Fixtures. Genau deshalb laufen die
Tests dazu in Millisekunden - und nur deshalb benutzt man die rot-gruen-
Schleife wirklich. Alles, was I/O macht, gehoert in speicher.py; das
Auswuerfeln steht in los.py und ist ebenso rein.

**Ein Ergebnis ist ein Sieger und sonst nichts.** Keine Saetze, keine
Baelle, keine Differenzen. Das ist keine Sparsamkeit, sondern der Zuschnitt:
wer nebenbei ein Turnier fuehrt, tippt einen Namen an und nicht sechs
Zahlen. Was dabei verloren geht - die feine Rangfolge bei Punktgleichheit -
entscheidet dann kein Rechenweg, sondern ein Spiel.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, replace
from datetime import datetime, timedelta
from itertools import combinations
from math import ceil
from typing import Literal

from homepi_core import ServiceError

#: Ein Teilnehmer, von aussen betrachtet. Im Betrieb ``str(teilnehmer.id)``.
Kennung = str

#: Ein Sieg zaehlt zwei Punkte, eine Niederlage keinen.
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


def pruefe_sieger(sieger: Kennung, heim: Kennung | None, gast: Kennung | None) -> None:
    """Hat der Sieger in diesem Spiel ueberhaupt mitgespielt?

    Die einzige Pruefung, die ein Ergebnis noch braucht. Sie faengt den
    Fall ab, in dem zwei Fenster offen sind und das Ergebnis am falschen
    Spiel landet.
    """
    if heim is None or gast is None:
        raise UngueltigesErgebnis(
            "Fuer dieses Spiel stehen die Gegner noch nicht fest - es kann keinen Sieger haben"
        )
    if sieger not in (heim, gast):
        raise UngueltigesErgebnis("Der Sieger muss einer der beiden Gegner dieses Spiels sein")


@dataclass(frozen=True, slots=True)
class Ergebnis:
    """Ein Spiel, wie die Tabelle es braucht: wer gegen wen, und wer gewann.

    ``sieger`` ist ``None``, solange nicht gespielt ist - ein solches Spiel
    zaehlt nirgends mit.
    """

    heim: Kennung
    gast: Kennung
    sieger: Kennung | None = None


@dataclass(frozen=True, slots=True)
class TabellenZeile:
    teilnehmer: Kennung
    platz: int
    spiele: int
    siege: int
    niederlagen: int
    punkte: int


@dataclass(slots=True)
class _Konto:
    siege: int = 0
    niederlagen: int = 0

    @property
    def spiele(self) -> int:
        return self.siege + self.niederlagen


def tabelle(
    teilnehmer: Sequence[Kennung],
    ergebnisse: Iterable[Ergebnis],
    freilose: Mapping[Kennung, int] | None = None,
) -> list[TabellenZeile]:
    """Die Tabelle: Siege, Punkte, Platz.

    **Punktgleiche teilen sich den Platz.** Es gibt keinen Rechenweg, der
    sie trennt - die Satzdifferenz ist weg, und der direkte Vergleich waere
    eine stille Entscheidung an einer Stelle, an der ein Spiel hingehoert.
    Zwei auf Platz eins, der naechste auf Platz drei.

    ``freilose`` sind geschenkte Siege aus dem Schweizer System. Wer
    aussetzen musste, soll dadurch nicht abrutschen.
    """
    konten: dict[Kennung, _Konto] = {wer: _Konto() for wer in teilnehmer}
    for wer, anzahl in (freilose or {}).items():
        if wer in konten:
            konten[wer].siege += anzahl

    for spiel in ergebnisse:
        if spiel.sieger is None:
            continue
        for wer in (spiel.heim, spiel.gast):
            if wer not in konten:
                continue
            if wer == spiel.sieger:
                konten[wer].siege += 1
            else:
                konten[wer].niederlagen += 1

    roh = sorted(
        (
            TabellenZeile(
                teilnehmer=wer,
                platz=0,
                spiele=konto.spiele,
                siege=konto.siege,
                niederlagen=konto.niederlagen,
                punkte=konto.siege * PUNKTE_SIEG,
            )
            for wer, konto in konten.items()
        ),
        # Der Name zuletzt ist kein Schoenheitsfehler, sondern der Grund,
        # warum die Tabelle bei zwei Abrufen gleich aussieht.
        key=lambda zeile: (-zeile.punkte, zeile.teilnehmer),
    )

    # Geteilte Plaetze: wer gleich viele Punkte hat, steht auf demselben
    # Platz, und der naechste ueberspringt die verbrauchten.
    return [
        replace(zeile, platz=1 + sum(1 for andere in roh if andere.punkte > zeile.punkte))
        for zeile in roh
    ]


def platzierung(zeilen: Sequence[TabellenZeile]) -> list[Kennung]:
    """Die Tabelle als reine Namensliste - so nimmt das Los sie an."""
    return [zeile.teilnehmer for zeile in sorted(zeilen, key=lambda z: (z.platz, z.teilnehmer))]


def gleichstand_an_der_grenze(zeilen: Sequence[TabellenZeile], grenze: int) -> list[Kennung]:
    """Wer muss noch gegeneinander spielen, bevor es weitergeht?

    ``grenze`` ist die Zahl derer, die weiterkommen - zwei bei zwei
    Weiterkommenden je Gruppe, eins beim Turniersieger. Entscheidend ist
    allein der Gleichstand, der diese Linie kreuzt: stehen zwei punktgleich
    auf den Plaetzen eins und zwei und beide kommen weiter, ist es
    gleichgueltig, wer von ihnen vorn steht - dafuer laesst man niemanden
    noch einmal antreten.

    Ohne diese Funktion fiele die Entscheidung nach dem Alphabet, und das
    waere die unauffaelligste Art, ein Turnier unfair zu machen.
    """
    if not zeilen or grenze < 1 or grenze >= len(zeilen):
        return []

    sortiert = sorted(zeilen, key=lambda z: (z.platz, z.teilnehmer))
    an_der_grenze = sortiert[grenze - 1].platz
    betroffen = [z for z in sortiert if z.platz == an_der_grenze]

    # Reicht die Gruppe ueber die Grenze hinaus? Ihr erster Platz liegt
    # davor, ihr letzter dahinter - sonst entscheidet sie nichts.
    if len(betroffen) < 2 or an_der_grenze + len(betroffen) - 1 <= grenze:
        return []
    return sorted(zeile.teilnehmer for zeile in betroffen)


def entscheidungsspiele(punktgleiche: Sequence[Kennung]) -> list[tuple[Kennung, Kennung]]:
    """Die Paarungen, mit denen ein Gleichstand aufgeloest wird.

    Zwei spielen einmal gegeneinander. Drei spielen jeder gegen jeden - das
    sind drei Spiele und dauert, aber ein Los an dieser Stelle waere die
    Entscheidung, die am Ende niemand erklaeren will.
    """
    return [(links, rechts) for links, rechts in combinations(punktgleiche, 2)]


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
    sechs Spielen durch. Es ist ein Vorschlag im Formular, keine Regel.
    """
    return max(1, min(anzahl_teilnehmer // 2, round(anzahl_teilnehmer / 4)))


def ko_bezeichnung(runde: int, runden_gesamt: int) -> str:
    """Wie die KO-Runde heisst.

    Sie haengt an der Rastergroesse und nicht an der Nummer: in einem Raster
    fuer vier ist Runde 1 das Halbfinale, in einem fuer sechzehn das
    Achtelfinale.
    """
    namen = {0: "Endspiel", 1: "Halbfinale", 2: "Viertelfinale", 3: "Achtelfinale"}
    return namen.get(runden_gesamt - runde, f"KO-Runde {runde}")


#: Einstellungen, an denen der ganze Spielplan haengt. Sie zu aendern,
#: waehrend gespielt wird, hiesse: der halbe Plan gehoert zu anderen Regeln
#: als der andere.
#:
#: ``best_of`` steht bewusst **nicht** hier. Seit ein Ergebnis nur noch der
#: Sieger ist, steht die Zahl in keinem Datensatz - sie sagt den Spielern,
#: wie lange sie spielen, und das darf man mitten im Turnier noch kuerzen,
#: wenn es knapp wird.
PLANFESTE_FELDER = frozenset({"modus", "anzahl_gruppen", "weiter_pro_gruppe", "runden"})


def darf_einstellung_aendern(zustand: str, abweichend: Iterable[str]) -> Entscheidung:
    if zustand == "planung":
        return Entscheidung(True)

    verboten = sorted(PLANFESTE_FELDER & set(abweichend))
    if not verboten:
        return Entscheidung(True)
    return Entscheidung(
        False,
        f"Nicht mehr aenderbar, solange gespielt wird: {', '.join(verboten)}. "
        "Tischzahl, Spieldauer und Gewinnsaetze gehen jederzeit.",
    )


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


def runde_vollstaendig(zustaende: Sequence[str]) -> bool:
    """Ist die laufende Runde durch? Keine Runde ist nicht vollstaendig."""
    return bool(zustaende) and all(zustand == "beendet" for zustand in zustaende)


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


__all__ = [
    "PLANFESTE_FELDER",
    "PUNKTE_SIEG",
    "Entscheidung",
    "Ergebnis",
    "FalscherZustand",
    "Kennung",
    "LosUnmoeglich",
    "NameVergeben",
    "Planzeile",
    "Schritt",
    "SpielUnbekannt",
    "Spielstandzeile",
    "Stand",
    "TabellenZeile",
    "TeilnehmerUnbekannt",
    "TurnierUnbekannt",
    "UngueltigesErgebnis",
    "darf_auswuerfeln",
    "darf_einstellung_aendern",
    "darf_teilnehmer_aendern",
    "entscheidungsspiele",
    "geschaetzte_dauer",
    "gleichstand_an_der_grenze",
    "gruppen_vorschlag",
    "ko_bezeichnung",
    "naechster_schritt",
    "planen",
    "platzierung",
    "pruefe_sieger",
    "runde_vollstaendig",
    "tabelle",
]
