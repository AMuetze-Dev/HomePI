"""Das Auswuerfeln: Gruppen, Spielfolge, KO-Raster, Schweizer Paarung.

REIN wie dienst.py - keine Datenbank, kein await. Der Zufall kommt
ausschliesslich aus einer uebergebenen Saat, nie aus ``random`` direkt:

  - Dasselbe Los laesst sich wiederherstellen. Die Saat steht am Turnier,
    damit "so wurde ausgelost" eine Auskunft ist und keine Behauptung.
  - Diese Funktionen sind testbar, ohne ``random`` zu verbiegen.

Die Kennung eines Teilnehmers ist hier ein ``str``. Dass es im Betrieb eine
UUID ist, muss diese Schicht nicht wissen - in den Tests stehen damit Namen
statt Kennungen, und die Zusagen bleiben lesbar.
"""

from __future__ import annotations

import random
from collections.abc import Sequence
from dataclasses import dataclass, field

from .dienst import LosUnmoeglich

#: Ein Teilnehmer, von aussen betrachtet. Im Betrieb ``str(teilnehmer.id)``.
Kennung = str

Paarung = tuple[Kennung, Kennung]


@dataclass(frozen=True, slots=True)
class Begegnung:
    """Eine ausgeloste Paarung - ohne Tisch und ohne Zeit.

    Wann und wo gespielt wird, entscheidet der Zeitplan aus den
    Tischen und dem Fortschritt; das Los legt nur fest, wer gegen wen.
    """

    heim: Kennung
    gast: Kennung
    #: 1-basiert innerhalb der Phase.
    runde: int
    #: Index der Gruppe, ``None`` ausserhalb einer Gruppenphase.
    gruppe: int | None = None


@dataclass(frozen=True, slots=True)
class KoPlatz:
    """Ein Platz im Raster: entweder jemand steht darin, oder der Sieger
    eines vorherigen Spiels laeuft dort ein.

    Genau eines von beiden ist gesetzt. Deshalb steht das Raster vollstaendig
    an der Wand, bevor der erste Ball gespielt ist - mit "Sieger aus Spiel 3"
    statt einer Leerstelle.
    """

    teilnehmer: Kennung | None = None
    aus_spiel: int | None = None
    #: Deutet ``aus_spiel`` auf den VERLIERER jenes Spiels? Nur im Doppel-KO,
    #: wo die zweite Chance genau daraus besteht. Ohne dieses Feld muesste
    #: "Verlierer aus Spiel 3" als Text irgendwo mitlaufen - und waere damit
    #: keine Angabe, die der Speicher aufloesen kann.
    verlierer: bool = False


#: Welcher Strang des Rasters. Im einfachen KO gibt es nur ``sieger``.
Zweig = str


@dataclass(frozen=True, slots=True)
class KoBegegnung:
    nummer: int
    #: 1 ist die erste Runde, die hoechste das Endspiel. Zaehlt je Zweig.
    runde: int
    heim: KoPlatz
    gast: KoPlatz
    #: einfach (nur ein Strang) | sieger | verlierer | finale
    zweig: Zweig = "einfach"


@dataclass(frozen=True, slots=True)
class Spielplan:
    """Das vollstaendige Ergebnis eines Wurfs.

    Eine Form fuer alle drei Modi - so bauen Vorschau und Festschreiben auf
    derselben Rechnung auf, und die Vorschau zeigt nicht etwas anderes, als
    danach gespeichert wird.
    """

    gruppen: list[list[Kennung]] = field(default_factory=list)
    #: Gruppenspiele oder die erste Runde im Schweizer System.
    begegnungen: list[Begegnung] = field(default_factory=list)
    #: Nur im reinen KO-Modus - sonst entsteht das Raster erst nach den Gruppen.
    ko: list[KoBegegnung] = field(default_factory=list)
    freilos: Kennung | None = None


def plan_auswuerfeln(
    modus: str,
    teilnehmer: Sequence[Kennung],
    anzahl_gruppen: int,
    saat: int,
    tische: int = 1,
    doppel_ko: bool = False,
) -> Spielplan:
    """Ein Wurf, je Modus das Passende.

    ``tische`` geht nur in die Reihenfolge ein, nicht in die Paarungen: mit
    zwei Tischen laufen zwei Spiele gleichzeitig, und dann darf im Spiel
    danach niemand stehen, der gerade gespielt hat.
    """
    if len(teilnehmer) < 2:
        raise LosUnmoeglich("Ein Turnier braucht mindestens zwei Teilnehmer - trage sie zuerst ein")

    if modus == "gruppen_ko":
        gruppen = gruppen_auswuerfeln(teilnehmer, anzahl_gruppen, saat)
        return Spielplan(
            gruppen=gruppen,
            begegnungen=entzerren(gruppenspiele(gruppen), fenster=max(1, tische)),
        )

    gemischt = list(teilnehmer)
    random.Random(saat).shuffle(gemischt)

    if modus == "ko":
        return Spielplan(ko=doppel_ko_raster(gemischt) if doppel_ko else ko_raster(gemischt))

    if modus == "schweizer":
        paarungen, freilos = schweizer_paarung(gemischt, bisherige=set(), freilose=set())
        return Spielplan(
            begegnungen=[Begegnung(heim=heim, gast=gast, runde=1) for heim, gast in paarungen],
            freilos=freilos,
        )

    raise LosUnmoeglich(f"Unbekannter Spielmodus '{modus}'")


def gruppen_auswuerfeln(
    teilnehmer: Sequence[Kennung], anzahl_gruppen: int, saat: int
) -> list[list[Kennung]]:
    """Verteilt die Teilnehmer zufaellig auf moeglichst gleich grosse Gruppen."""
    if len(teilnehmer) < 2:
        raise LosUnmoeglich("Ein Turnier braucht mindestens zwei Teilnehmer")
    if anzahl_gruppen < 1:
        raise LosUnmoeglich("Ein Turnier braucht mindestens eine Gruppe")
    if len(teilnehmer) < anzahl_gruppen * 2:
        # Wer allein in einer Gruppe steht, hat kein Spiel - und stuende
        # trotzdem als Gruppensieger im Raster.
        raise LosUnmoeglich(
            f"{len(teilnehmer)} Teilnehmer reichen nicht fuer {anzahl_gruppen} Gruppen: "
            f"jede Gruppe braucht mindestens zwei. Moeglich sind hoechstens "
            f"{len(teilnehmer) // 2} Gruppen."
        )

    gemischt = list(teilnehmer)
    random.Random(saat).shuffle(gemischt)

    gruppen: list[list[Kennung]] = [[] for _ in range(anzahl_gruppen)]
    # Reihum verteilen statt in Blöcke schneiden: so unterscheiden sich die
    # Gruppengroessen um hoechstens eins, ohne dass jemand nachrechnet.
    for stelle, wer in enumerate(gemischt):
        gruppen[stelle % anzahl_gruppen].append(wer)
    return gruppen


def berger_runden(teilnehmer: Sequence[Kennung]) -> list[list[Paarung]]:
    """Jeder gegen jeden, nach Runden geordnet (Kreismethode).

    Der Nutzen steckt in der Ordnung, nicht in der Menge: in einer Runde
    kommt jeder hoechstens einmal vor. Damit laufen die Spiele einer Runde
    gleichzeitig an mehreren Tischen, ohne dass jemand an zwei Tischen
    gebraucht wird - bei einer schlicht aufgezaehlten Paarungsliste ist
    genau das der Normalfall.
    """
    if len(teilnehmer) < 2:
        raise LosUnmoeglich("Fuer jeder-gegen-jeden braucht es mindestens zwei Teilnehmer")

    leute: list[Kennung | None] = list(teilnehmer)
    if len(leute) % 2:
        # Der Platzhalter macht die Zahl gerade; wer auf ihn trifft, setzt
        # diese Runde aus.
        leute.append(None)

    anzahl = len(leute)
    runden: list[list[Paarung]] = []
    for nummer in range(anzahl - 1):
        paarungen: list[Paarung] = []
        for stelle in range(anzahl // 2):
            links, rechts = leute[stelle], leute[anzahl - 1 - stelle]
            if links is None or rechts is None:
                continue
            # Abwechselnd anschreiben: sonst stuende immer derselbe als
            # Heim in der Liste, und bei Tischtennis beginnt der Aufschlag
            # beim ersten Genannten.
            paarungen.append((links, rechts) if (nummer + stelle) % 2 == 0 else (rechts, links))
        runden.append(paarungen)
        leute = [leute[0], leute[-1], *leute[1:-1]]
    return runden


def gruppenspiele(gruppen: Sequence[Sequence[Kennung]]) -> list[Begegnung]:
    """Die Spielfolge der Gruppenphase, verschraenkt ueber alle Gruppen.

    Gruppe fuer Gruppe abzuarbeiten waere einfacher und im Saal falsch: Gruppe
    A spielte ihre sechs Spiele, und Gruppe B sass dabei eine Stunde herum.
    Deshalb wird reihum durch die Gruppen gegangen - und weil innerhalb einer
    Runde niemand zweimal vorkommt, steht niemand zwei Spiele hintereinander
    am Tisch.
    """
    runden_je_gruppe = [berger_runden(gruppe) for gruppe in gruppen]
    if not runden_je_gruppe:
        return []

    spiele: list[Begegnung] = []
    for runde in range(max(len(runden) for runden in runden_je_gruppe)):
        offen = [
            (nummer, list(runden[runde]))
            for nummer, runden in enumerate(runden_je_gruppe)
            if runde < len(runden)
        ]
        while any(paarungen for _, paarungen in offen):
            for gruppe, paarungen in offen:
                if not paarungen:
                    continue
                heim, gast = paarungen.pop(0)
                spiele.append(Begegnung(heim=heim, gast=gast, runde=runde + 1, gruppe=gruppe))
    return spiele


def entzerren(begegnungen: Sequence[Begegnung], fenster: int) -> list[Begegnung]:
    """Schiebt die Spielfolge so, dass niemand zweimal kurz hintereinander dran ist.

    Die Berger-Tabelle sorgt dafuer, dass innerhalb einer Runde niemand
    doppelt vorkommt. Ueber die Rundengrenze hinweg gilt das nicht - und mit
    zwei Tischen heisst "ein Spiel dazwischen" eben nicht "eine Pause":
    beobachtet an einem fertigen Plan, in dem Anna an Tisch 1 zwei Spiele in
    Folge hatte, waehrend am anderen Tisch eines lief.

    Gewaehlt wird immer das fruehstmoegliche Spiel, das passt - die Ordnung
    der Runden bleibt damit so weit erhalten, wie es geht. Passt keines mehr
    (gegen Ende einer Gruppe unvermeidlich), wird das naechste genommen: ein
    unvollstaendiger Plan waere schlimmer als eine kurze Pause.
    """
    rest = list(begegnungen)
    geordnet: list[Begegnung] = []

    while rest:
        zuletzt = {wer for spiel in geordnet[-fenster:] for wer in (spiel.heim, spiel.gast)}
        wahl = next(
            (
                stelle
                for stelle, spiel in enumerate(rest)
                if {spiel.heim, spiel.gast}.isdisjoint(zuletzt)
            ),
            0,
        )
        geordnet.append(rest.pop(wahl))

    return geordnet


def setzpositionen(groesse: int) -> list[int]:
    """Die Setzplaetze in der Reihenfolge der Rasterplaetze.

    Fuer acht: 1-8, 4-5, 2-7, 3-6. Die Zusage dahinter ist, dass sich die
    beiden Erstgesetzten erst im Endspiel treffen koennen, die Nummern 1 bis
    4 erst im Halbfinale, und so weiter.
    """
    ordnung = [1]
    while len(ordnung) < groesse:
        hoechste = len(ordnung) * 2 + 1
        gespiegelt: list[int] = []
        for platz in ordnung:
            gespiegelt.append(platz)
            gespiegelt.append(hoechste - platz)
        ordnung = gespiegelt
    return ordnung


def ko_raster(gesetzte: Sequence[Kennung]) -> list[KoBegegnung]:
    """Das vollstaendige Raster, vom ersten Spiel bis zum Endspiel.

    ``gesetzte`` ist die Setzliste, der Staerkste zuerst. Ist die Zahl keine
    Zweierpotenz, bekommen die Erstgesetzten die Freilose: sie steigen eine
    Runde spaeter ein, und fuer sie entsteht in der ersten Runde kein Spiel.
    Ein Freilos als Gegner waere ein Spiel, das niemand spielt - und das in
    jeder Liste und jedem Zeitplan erklaert werden muesste.
    """
    if len(gesetzte) < 2:
        raise LosUnmoeglich("Ein KO-Raster braucht mindestens zwei Teilnehmer")

    groesse = 1 << (len(gesetzte) - 1).bit_length()
    plaetze: list[KoPlatz | None] = [
        KoPlatz(teilnehmer=gesetzte[platz - 1]) if platz <= len(gesetzte) else None
        for platz in setzpositionen(groesse)
    ]

    spiele: list[KoBegegnung] = []
    nummer = 0
    runde = 1
    while len(plaetze) > 1:
        naechste: list[KoPlatz | None] = []
        for stelle in range(0, len(plaetze), 2):
            links, rechts = plaetze[stelle], plaetze[stelle + 1]
            if links is None or rechts is None:
                # Freilos: der Anwesende rueckt auf, ohne gespielt zu haben.
                naechste.append(links if rechts is None else rechts)
                continue
            nummer += 1
            spiele.append(KoBegegnung(nummer=nummer, runde=runde, heim=links, gast=rechts))
            naechste.append(KoPlatz(aus_spiel=nummer))
        plaetze = naechste
        runde += 1
    return spiele


def doppel_ko_raster(gesetzte: Sequence[Kennung]) -> list[KoBegegnung]:
    """Dasselbe Raster, aber mit zweiter Chance: wer einmal verliert, spielt
    in der Verliererrunde weiter und ist erst nach der zweiten Niederlage aus.

    Das Ergebnis ist eine Liste in Spielreihenfolge, und die Reihenfolge ist
    die eines echten Turniers: erst eine Runde im Siegerzweig, dann die
    Verliererrunde, die deren Verlierer auffaengt. Die Nummer ist damit
    gleichzeitig die Reihenfolge, und kein Spiel verweist nach vorn.

    Drei Zahlen dazu, weil sie beim Planen gebraucht werden: es sind
    ``2n - 2`` Spiele statt ``n - 1``, jeder spielt mindestens zwei, und der
    Sieger des Verliererzweigs tritt im Endspiel genau einmal gegen den
    Sieger des Siegerzweigs an.

    **Kein bracket reset.** Gewinnt im Endspiel der aus dem Verliererzweig,
    hat er den anderen einmal geschlagen und ist Turniersieger - im strengen
    Doppel-KO waere jetzt ein zweites Endspiel faellig, weil der andere erst
    eine Niederlage hat. Das ist richtig und hier trotzdem weggelassen: ein
    Turnier, dessen Ende "vielleicht noch ein Spiel" ist, laesst sich nebenbei
    nicht fuehren.
    """
    sieger_zweig = ko_raster(gesetzte)

    nach_runde: dict[int, list[KoBegegnung]] = {}
    for spiel in sieger_zweig:
        nach_runde.setdefault(spiel.runde, []).append(spiel)

    spiele: list[KoBegegnung] = []
    #: Alte Nummer aus ``ko_raster`` -> neue, weil sich die Verliererrunden
    #: dazwischenschieben.
    umbenannt: dict[int, int] = {}
    #: Wer im Verliererzweig noch lebt - als Platz, nicht als Name: wer das
    #: ist, steht erst fest, wenn gespielt wurde.
    lebend: list[KoPlatz] = []
    lb_runde = 0

    def _ansetzen(heim: KoPlatz, gast: KoPlatz, runde: int, zweig: str) -> KoPlatz:
        nummer = len(spiele) + 1
        spiele.append(KoBegegnung(nummer=nummer, runde=runde, heim=heim, gast=gast, zweig=zweig))
        return KoPlatz(aus_spiel=nummer)

    def _verliererrunde(feld: list[KoPlatz]) -> list[KoPlatz]:
        """Paart das Feld und gibt zurueck, wer danach noch lebt.

        Eine ungerade Zahl bedeutet ein Freilos: der Uebrige rueckt auf, ohne
        gespielt zu haben. Ein Spiel gegen niemanden waere eines, das in jedem
        Zeitplan erklaert werden muesste.
        """
        nonlocal lb_runde
        if len(feld) < 2:
            return feld
        lb_runde += 1
        weiter = [
            _ansetzen(feld[stelle], feld[stelle + 1], lb_runde, "verlierer")
            for stelle in range(0, len(feld) - 1, 2)
        ]
        if len(feld) % 2:
            weiter.append(feld[-1])
        return weiter

    runden = sorted(nach_runde)
    for stelle, runde in enumerate(runden):
        for spiel in nach_runde[runde]:
            nummer = len(spiele) + 1
            umbenannt[spiel.nummer] = nummer
            spiele.append(
                KoBegegnung(
                    nummer=nummer,
                    runde=runde,
                    heim=_umbenennen(spiel.heim, umbenannt),
                    gast=_umbenennen(spiel.gast, umbenannt),
                    zweig="sieger",
                )
            )

        absteiger = [
            KoPlatz(aus_spiel=umbenannt[spiel.nummer], verlierer=True)
            for spiel in nach_runde[runde]
        ]

        # Kreuzweise: wer schon eine Niederlage hat, trifft einen gerade
        # Abgestiegenen - und nicht sofort wieder denselben Gegner.
        gekreuzt: list[KoPlatz] = []
        absteiger.reverse()
        while lebend and absteiger:
            gekreuzt.append(lebend.pop(0))
            gekreuzt.append(absteiger.pop(0))
        gekreuzt.extend(lebend)
        gekreuzt.extend(absteiger)
        lebend = _verliererrunde(gekreuzt)

        # So lange zusammenfuehren, bis gerade so viele uebrig sind, wie in
        # der naechsten Runde von oben nachkommen. Ohne diesen Schritt
        # staende der Verliererzweig am Ende mit zwei Leuten da.
        nachkommend = len(nach_runde[runden[stelle + 1]]) if stelle + 1 < len(runden) else 0
        while len(lebend) > max(1, nachkommend):
            lebend = _verliererrunde(lebend)

    hoechste = runden[-1]
    aus_dem_siegerzweig = KoPlatz(aus_spiel=umbenannt[nach_runde[hoechste][0].nummer])
    _ansetzen(aus_dem_siegerzweig, lebend[0], 1, "finale")
    return spiele


def _umbenennen(platz: KoPlatz, umbenannt: dict[int, int]) -> KoPlatz:
    """Dasselbe Platzhalterfeld, nur mit der neuen Spielnummer."""
    if platz.aus_spiel is None:
        return platz
    return KoPlatz(
        teilnehmer=platz.teilnehmer,
        aus_spiel=umbenannt[platz.aus_spiel],
        verlierer=platz.verlierer,
    )


def ko_setzliste(
    platzierungen: Sequence[Sequence[Kennung]], weiter_pro_gruppe: int
) -> list[Kennung]:
    """Wer aus den Gruppen weiterkommt, als Setzliste fuer das Raster.

    ``platzierungen`` ist je Gruppe die Tabelle, der Erste zuerst. Alle
    Gruppensieger stehen vor allen Zweiten - und danach wird so lange
    getauscht, bis in der ersten KO-Runde niemand gegen seinen eigenen
    Gruppengegner spielt. Sonst war die Gruppenphase fuer die beiden umsonst.
    """
    setzliste: list[Kennung] = []
    herkunft: dict[Kennung, int] = {}
    bloecke: list[list[int]] = []

    for platz in range(weiter_pro_gruppe):
        block: list[int] = []
        for gruppe, tabelle in enumerate(platzierungen):
            if platz >= len(tabelle):
                # Eine Gruppe, aus der mehr weiterkommen sollen als sie Leute
                # hat, liefert eben weniger - keine Luecke im Raster.
                continue
            herkunft[tabelle[platz]] = gruppe
            block.append(len(setzliste))
            setzliste.append(tabelle[platz])
        if block:
            bloecke.append(block)

    return _gruppenduelle_entflechten(setzliste, herkunft, bloecke)


def _erstrundenpaare(anzahl: int) -> list[tuple[int, int]]:
    """Welche Stellen der Setzliste in der ersten Runde aufeinandertreffen."""
    groesse = 1 << (anzahl - 1).bit_length()
    ordnung = setzpositionen(groesse)
    return [
        (ordnung[stelle] - 1, ordnung[stelle + 1] - 1)
        for stelle in range(0, groesse, 2)
        if ordnung[stelle] <= anzahl and ordnung[stelle + 1] <= anzahl
    ]


def _gruppenduelle_entflechten(
    setzliste: list[Kennung], herkunft: dict[Kennung, int], bloecke: list[list[int]]
) -> list[Kennung]:
    if len(setzliste) < 2:
        return setzliste

    paare = _erstrundenpaare(len(setzliste))

    def konflikte(liste: list[Kennung]) -> list[tuple[int, int]]:
        return [
            (links, rechts)
            for links, rechts in paare
            if herkunft[liste[links]] == herkunft[liste[rechts]]
        ]

    # Getauscht wird nur innerhalb eines Blocks - ein Gruppensieger bleibt
    # vor den Zweiten. Jeder Tausch verringert die Zahl der Konflikte, deshalb
    # endet die Schleife; bleibt einer uebrig, ist er nicht aufloesbar (zwei
    # Gruppen mit je zwei Weiterkommenden lassen sich nicht immer trennen).
    while True:
        offen = konflikte(setzliste)
        if not offen:
            return setzliste

        _, rechts = offen[0]
        block = next((b for b in bloecke if rechts in b), [])
        for kandidat in block:
            if kandidat == rechts:
                continue
            probe = list(setzliste)
            probe[rechts], probe[kandidat] = probe[kandidat], probe[rechts]
            if len(konflikte(probe)) < len(offen):
                setzliste = probe
                break
        else:
            return setzliste


def schweizer_paarung(
    reihenfolge: Sequence[Kennung],
    bisherige: set[frozenset[Kennung]],
    freilose: set[Kennung],
) -> tuple[list[Paarung], Kennung | None]:
    """Die naechste Runde im Schweizer System.

    ``reihenfolge`` ist die Tabelle, der Fuehrende zuerst: gepaart wird von
    oben nach unten, damit Punktgleiche aufeinandertreffen. Eine Paarung, die
    es schon gab, wird nicht wiederholt - dafuer wird notfalls eine schon
    getroffene Entscheidung zurueckgenommen (gieriges Paaren laeuft sich fest
    und laesst die letzten zwei uebrig, die schon gegeneinander gespielt
    haben).
    """
    leute = list(reihenfolge)
    freilos: Kennung | None = None

    if len(leute) % 2:
        # Von unten nach oben, und nur an jemanden, der noch keines hatte:
        # ein Freilos ist ein geschenkter Sieg.
        freilos = next((wer for wer in reversed(leute) if wer not in freilose), leute[-1])
        leute.remove(freilos)

    paarungen = _paaren(leute, bisherige)
    if paarungen is None:
        raise LosUnmoeglich(
            "Es gibt keine Runde mehr, in der nicht zwei gegeneinander spielen, "
            "die schon gegeneinander gespielt haben"
        )
    return paarungen, freilos


def _paaren(leute: list[Kennung], bisherige: set[frozenset[Kennung]]) -> list[Paarung] | None:
    if not leute:
        return []

    erster, rest = leute[0], leute[1:]
    for stelle, gegner in enumerate(rest):
        if frozenset((erster, gegner)) in bisherige:
            continue
        weiter = _paaren([*rest[:stelle], *rest[stelle + 1 :]], bisherige)
        if weiter is not None:
            return [(erster, gegner), *weiter]
    return None
