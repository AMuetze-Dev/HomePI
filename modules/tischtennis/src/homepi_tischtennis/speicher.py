"""Datenbankzugriff. Hier faellt I/O an, hier stehen keine Entscheidungen.

Kein einziges if, das eine Fachregel abbildet - solche stehen in dienst.py
und los.py und werden von hier aus gerufen. Erlaubt sind nur Pruefungen, die
die Datenbank selbst beantwortet, etwa ob ein Datensatz existiert.

Die Teilnehmerkennung ist fuer die reinen Schichten ein ``str``. Die
Umrechnung von und nach UUID passiert ausschliesslich hier.
"""

from __future__ import annotations

import datetime as dt
import random
import uuid
from collections.abc import Sequence

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from . import dienst, los
from .dienst import (
    FalscherZustand,
    NameVergeben,
    SpielUnbekannt,
    TeilnehmerUnbekannt,
    TurnierUnbekannt,
)
from .modelle import Gruppe, Spiel, Teilnehmer, Turnier
from .schemas import (
    ErgebnisEintragen,
    TeilnehmerAnlegen,
    TurnierAnlegen,
    TurnierEinstellungen,
)

#: Gruppen heissen A, B, C - nicht "Gruppe 0". Mehr als sechzehn Gruppen
#: laesst das Schema nicht zu.
GRUPPENNAMEN = "ABCDEFGHIJKLMNOP"


def jetzt() -> dt.datetime:
    return dt.datetime.now(dt.UTC)


# ---------------------------------------------------------------- Turniere


async def turniere(sitzung: AsyncSession) -> list[Turnier]:
    ergebnis = await sitzung.execute(select(Turnier).order_by(Turnier.angelegt.desc()))
    return list(ergebnis.scalars())


async def turnier(sitzung: AsyncSession, turnier_id: uuid.UUID) -> Turnier:
    gefunden = await sitzung.get(Turnier, turnier_id)
    if gefunden is None:
        raise TurnierUnbekannt(f"Es gibt kein Turnier mit der Kennung {turnier_id}")
    return gefunden


async def aktives_turnier(sitzung: AsyncSession) -> Turnier | None:
    """Das Turnier, das die oeffentliche Ansicht zeigt.

    Das neueste laufende, und wenn keines laeuft, das neueste ueberhaupt.
    Bewusst kein Haekchen "aktiv" an der Tabelle: ein zweites Turnier
    anzulegen soll das erste nicht aus dem Dashboard werfen, und ein Haekchen,
    das genau einmal gesetzt sein muss, ist eine Bedingung, die irgendwann
    verletzt ist.
    """
    laufend = await sitzung.execute(
        select(Turnier)
        .where(Turnier.zustand == "laufend")
        .order_by(Turnier.angelegt.desc())
        .limit(1)
    )
    gefunden = laufend.scalar_one_or_none()
    if gefunden is not None:
        return gefunden

    neuestes = await sitzung.execute(select(Turnier).order_by(Turnier.angelegt.desc()).limit(1))
    return neuestes.scalar_one_or_none()


async def turnier_anlegen(sitzung: AsyncSession, daten: TurnierAnlegen) -> Turnier:
    neues = Turnier(**daten.model_dump())
    sitzung.add(neues)
    try:
        await sitzung.flush()
    except IntegrityError as fehler:
        await sitzung.rollback()
        raise NameVergeben(f"Ein Turnier '{daten.name}' gibt es schon") from fehler
    await sitzung.refresh(neues)
    return neues


async def turnier_aendern(
    sitzung: AsyncSession, turnier_id: uuid.UUID, daten: TurnierEinstellungen
) -> Turnier:
    gefunden = await turnier(sitzung, turnier_id)

    neu = daten.model_dump()
    abweichend = [feld for feld, wert in neu.items() if getattr(gefunden, feld) != wert]
    entscheidung = dienst.darf_einstellung_aendern(gefunden.zustand, abweichend)
    if not entscheidung.erlaubt:
        raise FalscherZustand(entscheidung.grund)

    for feld, wert in neu.items():
        setattr(gefunden, feld, wert)
    await sitzung.flush()
    return gefunden


async def turnier_loeschen(sitzung: AsyncSession, turnier_id: uuid.UUID) -> None:
    await sitzung.delete(await turnier(sitzung, turnier_id))


async def turnier_beenden(sitzung: AsyncSession, turnier_id: uuid.UUID) -> Turnier:
    gefunden = await turnier(sitzung, turnier_id)
    gefunden.zustand = "beendet"
    await sitzung.flush()
    return gefunden


async def zuruecksetzen(sitzung: AsyncSession, turnier_id: uuid.UUID) -> Turnier:
    """Spielplan weg, Teilnehmer bleiben.

    Der Weg zurueck in die Planung - und der einzige, auf dem ein zweites
    Auswuerfeln moeglich wird. Dass dabei alle Ergebnisse verschwinden, ist
    kein Nebeneffekt, sondern der Punkt: sie gehoeren zu Spielen, die es
    danach nicht mehr gibt.
    """
    gefunden = await turnier(sitzung, turnier_id)

    for spiel in await spiele(sitzung, turnier_id):
        await sitzung.delete(spiel)
    for teil in await teilnehmer(sitzung, turnier_id):
        teil.gruppe_id = None
        teil.freilose = 0
    await sitzung.flush()
    for gruppe in await gruppen(sitzung, turnier_id):
        await sitzung.delete(gruppe)

    gefunden.zustand = "planung"
    gefunden.saat = None
    gefunden.runde_angesetzt = 0
    gefunden.ko_steht = False
    await sitzung.flush()
    return gefunden


# ------------------------------------------------------------- Teilnehmer


async def teilnehmer(sitzung: AsyncSession, turnier_id: uuid.UUID) -> list[Teilnehmer]:
    ergebnis = await sitzung.execute(
        select(Teilnehmer).where(Teilnehmer.turnier_id == turnier_id).order_by(Teilnehmer.name)
    )
    return list(ergebnis.scalars())


async def gruppen(sitzung: AsyncSession, turnier_id: uuid.UUID) -> list[Gruppe]:
    ergebnis = await sitzung.execute(
        select(Gruppe).where(Gruppe.turnier_id == turnier_id).order_by(Gruppe.nummer)
    )
    return list(ergebnis.scalars())


async def ein_teilnehmer(sitzung: AsyncSession, teilnehmer_id: uuid.UUID) -> Teilnehmer:
    gefunden = await sitzung.get(Teilnehmer, teilnehmer_id)
    if gefunden is None:
        raise TeilnehmerUnbekannt(f"Es gibt keinen Teilnehmer mit der Kennung {teilnehmer_id}")
    return gefunden


async def teilnehmer_anlegen(
    sitzung: AsyncSession, turnier_id: uuid.UUID, daten: TeilnehmerAnlegen
) -> Teilnehmer:
    gefunden = await turnier(sitzung, turnier_id)
    _pruefe_teilnehmer_aenderbar(gefunden)

    neuer = Teilnehmer(turnier_id=turnier_id, **daten.model_dump())
    sitzung.add(neuer)
    try:
        await sitzung.flush()
    except IntegrityError as fehler:
        await sitzung.rollback()
        # Die Datenbank ist die einzige Stelle, die das zuverlaessig weiss -
        # eine Vorabpruefung waere ein Rennen zwischen zwei Anfragen.
        raise NameVergeben(f"'{daten.name}' steht schon auf der Liste") from fehler
    await sitzung.refresh(neuer)
    return neuer


async def teilnehmer_aendern(
    sitzung: AsyncSession, teilnehmer_id: uuid.UUID, daten: TeilnehmerAnlegen
) -> Teilnehmer:
    gefunden = await ein_teilnehmer(sitzung, teilnehmer_id)
    _pruefe_teilnehmer_aenderbar(await turnier(sitzung, gefunden.turnier_id))

    gefunden.name = daten.name
    gefunden.notiz = daten.notiz
    try:
        await sitzung.flush()
    except IntegrityError as fehler:
        await sitzung.rollback()
        raise NameVergeben(f"'{daten.name}' steht schon auf der Liste") from fehler
    return gefunden


async def teilnehmer_loeschen(sitzung: AsyncSession, teilnehmer_id: uuid.UUID) -> None:
    gefunden = await ein_teilnehmer(sitzung, teilnehmer_id)
    _pruefe_teilnehmer_aenderbar(await turnier(sitzung, gefunden.turnier_id))
    await sitzung.delete(gefunden)


def _pruefe_teilnehmer_aenderbar(gefunden: Turnier) -> None:
    entscheidung = dienst.darf_teilnehmer_aendern(gefunden.zustand)
    if not entscheidung.erlaubt:
        raise FalscherZustand(entscheidung.grund)


# ------------------------------------------------------------------ Spiele


async def spiele(sitzung: AsyncSession, turnier_id: uuid.UUID) -> list[Spiel]:
    ergebnis = await sitzung.execute(
        select(Spiel).where(Spiel.turnier_id == turnier_id).order_by(Spiel.nummer)
    )
    return list(ergebnis.scalars())


async def ein_spiel(sitzung: AsyncSession, spiel_id: uuid.UUID) -> Spiel:
    gefunden = await sitzung.get(Spiel, spiel_id)
    if gefunden is None:
        raise SpielUnbekannt(f"Es gibt kein Spiel mit der Kennung {spiel_id}")
    return gefunden


async def spiel_beginnen(sitzung: AsyncSession, spiel_id: uuid.UUID, tisch: int | None) -> Spiel:
    gefunden = await ein_spiel(sitzung, spiel_id)
    lauf = await turnier(sitzung, gefunden.turnier_id)

    if gefunden.freilos:
        raise FalscherZustand("Ein Freilos wird nicht gespielt")
    if gefunden.heim_id is None or gefunden.gast_id is None:
        raise FalscherZustand(
            "Die Gegner stehen noch nicht fest - erst muessen die Spiele davor gespielt sein"
        )
    if gefunden.zustand == "beendet":
        raise FalscherZustand(
            "Das Spiel ist schon gewertet. Nimm das Ergebnis zurueck, wenn es doch noch laeuft."
        )

    gefunden.tisch = tisch if tisch is not None else await _freier_tisch(sitzung, lauf, gefunden)
    gefunden.zustand = "laeuft"
    gefunden.begonnen_am = jetzt()
    await sitzung.flush()
    return gefunden


async def _freier_tisch(sitzung: AsyncSession, lauf: Turnier, gefunden: Spiel) -> int:
    """Welcher Tisch gerade frei ist - aus demselben Plan wie die Anzeige.

    Dieselbe Rechnung wie im Dashboard, damit der Tisch, an dem der Aufruf
    landet, der ist, der dort angekuendigt war.
    """
    plan = dienst.planen(
        planzeilen(await spiele(sitzung, lauf.id)),
        tische=lauf.tische,
        minuten=lauf.minuten_pro_spiel,
        jetzt=jetzt(),
    )
    for zeile in plan:
        if zeile.spiel == str(gefunden.id):
            return zeile.tisch
    return 1


async def ergebnis_eintragen(
    sitzung: AsyncSession, spiel_id: uuid.UUID, daten: ErgebnisEintragen
) -> Spiel:
    """Saetze eintragen - auch unvollstaendig.

    Ein Zwischenstand ist erlaubt und sogar der Normalfall: wer am Tisch
    steht, traegt nach jedem Satz ein, und das Dashboard zeigt es. Erst wenn
    die noetigen Saetze erreicht sind, ist das Spiel beendet - und dann
    rueckt der Sieger im Raster auf.
    """
    gefunden = await ein_spiel(sitzung, spiel_id)
    lauf = await turnier(sitzung, gefunden.turnier_id)

    if gefunden.freilos:
        raise FalscherZustand("Ein Freilos hat kein Ergebnis")
    if gefunden.heim_id is None or gefunden.gast_id is None:
        raise FalscherZustand("Die Gegner stehen noch nicht fest")

    saetze = [(satz.heim, satz.gast) for satz in daten.saetze]
    stand = dienst.spielstand(saetze, lauf.best_of, lauf.punkte_bis)

    gefunden.saetze = [[heim, gast] for heim, gast in saetze]
    if stand.entschieden:
        gefunden.zustand = "beendet"
        gefunden.sieger_id = gefunden.heim_id if stand.sieger == "heim" else gefunden.gast_id
        gefunden.beendet_am = jetzt()
        if gefunden.begonnen_am is None:
            gefunden.begonnen_am = gefunden.beendet_am
    else:
        gefunden.zustand = "laeuft" if saetze else "geplant"
        gefunden.sieger_id = None
        gefunden.beendet_am = None
        if saetze and gefunden.begonnen_am is None:
            gefunden.begonnen_am = jetzt()

    await _sieger_weiterreichen(sitzung, lauf, gefunden)
    await _zustand_nachfuehren(sitzung, lauf)
    await sitzung.flush()
    return gefunden


async def ergebnis_zuruecknehmen(sitzung: AsyncSession, spiel_id: uuid.UUID) -> Spiel:
    gefunden = await ein_spiel(sitzung, spiel_id)
    lauf = await turnier(sitzung, gefunden.turnier_id)

    gefunden.saetze = []
    gefunden.sieger_id = None
    gefunden.zustand = "geplant"
    gefunden.begonnen_am = None
    gefunden.beendet_am = None
    gefunden.tisch = None

    await _sieger_weiterreichen(sitzung, lauf, gefunden)
    await _zustand_nachfuehren(sitzung, lauf)
    await sitzung.flush()
    return gefunden


async def _sieger_weiterreichen(sitzung: AsyncSession, lauf: Turnier, ausgangspunkt: Spiel) -> None:
    """Setzt den Sieger in das Folgespiel - und raeumt auf, wenn er wechselt.

    Der zweite Teil ist der wichtigere: wird ein Ergebnis korrigiert, stand
    im Folgespiel bisher der falsche Name. Haette dieses Folgespiel selbst
    schon ein Ergebnis, waere es das Ergebnis eines Spiels zwischen Leuten,
    die so nie gegeneinander angetreten sind - deshalb wird es mit
    zurueckgenommen, und zwar bis zum Endspiel durch.
    """
    alle = await spiele(sitzung, lauf.id)
    offen = [ausgangspunkt]

    while offen:
        aktuell = offen.pop()
        for folge in alle:
            geaendert = False
            if folge.heim_aus_spiel == aktuell.nummer and folge.heim_id != aktuell.sieger_id:
                folge.heim_id = aktuell.sieger_id
                geaendert = True
            if folge.gast_aus_spiel == aktuell.nummer and folge.gast_id != aktuell.sieger_id:
                folge.gast_id = aktuell.sieger_id
                geaendert = True
            if not geaendert:
                continue
            if folge.saetze or folge.zustand != "geplant":
                folge.saetze = []
                folge.sieger_id = None
                folge.zustand = "geplant"
                folge.begonnen_am = None
                folge.beendet_am = None
                folge.tisch = None
                # Die Nummer eines Folgespiels ist immer groesser, deshalb
                # endet dieser Durchlauf.
                offen.append(folge)


async def _zustand_nachfuehren(sitzung: AsyncSession, lauf: Turnier) -> None:
    alle = await spiele(sitzung, lauf.id)
    schritt = dienst.naechster_schritt(_stand(lauf, alle))

    if schritt == "fertig" and alle:
        lauf.zustand = "beendet"
    elif lauf.zustand == "beendet":
        # Ein zurueckgenommenes Ergebnis macht das Turnier wieder zu einem
        # laufenden - sonst zeigte das Dashboard "beendet" und daneben ein
        # offenes Spiel.
        lauf.zustand = "laufend"


def _stand(lauf: Turnier, alle: Sequence[Spiel]) -> dienst.Stand:
    return dienst.Stand(
        modus=lauf.modus,
        runde_angesetzt=lauf.runde_angesetzt,
        runden=lauf.runden,
        ko_steht=lauf.ko_steht,
        offene_spiele=sum(1 for spiel in alle if spiel.zustand != "beendet"),
    )


def planzeilen(alle: Sequence[Spiel]) -> list[dienst.Spielstandzeile]:
    """Die offenen Spiele, wie der Zeitplan sie erwartet - Freilose nicht."""
    return [
        dienst.Spielstandzeile(
            id=str(spiel.id),
            zustand=spiel.zustand,
            tisch=spiel.tisch,
            begonnen_am=spiel.begonnen_am,
        )
        for spiel in alle
        if not spiel.freilos
    ]


# --------------------------------------------------------------------- Los


async def plan_vorschlag(
    sitzung: AsyncSession, turnier_id: uuid.UUID, saat: int | None
) -> tuple[Turnier, dict[str, Teilnehmer], los.Spielplan, int]:
    """Was dieses Los ergaebe. Schreibt nichts.

    Gibt die Saat mit zurueck, damit der Aufrufer dasselbe Los festschreiben
    kann, das er gesehen hat.
    """
    lauf = await turnier(sitzung, turnier_id)
    entscheidung = dienst.darf_auswuerfeln(lauf.zustand)
    if not entscheidung.erlaubt:
        raise FalscherZustand(entscheidung.grund)

    leute = await teilnehmer(sitzung, turnier_id)
    gezogen = saat if saat is not None else random.randrange(1_000_000_000)
    plan = los.plan_auswuerfeln(
        modus=lauf.modus,
        teilnehmer=[str(wer.id) for wer in leute],
        anzahl_gruppen=lauf.anzahl_gruppen,
        saat=gezogen,
        tische=lauf.tische,
    )
    return lauf, {str(wer.id): wer for wer in leute}, plan, gezogen


async def auswuerfeln(sitzung: AsyncSession, turnier_id: uuid.UUID, saat: int | None) -> Turnier:
    """Schreibt den ausgewuerfelten Spielplan und startet das Turnier."""
    lauf, nach_kennung, plan, gezogen = await plan_vorschlag(sitzung, turnier_id, saat)

    nummer = 0
    gruppen_nach_index: dict[int, Gruppe] = {}
    for index, mitglieder in enumerate(plan.gruppen):
        gruppe = Gruppe(turnier_id=lauf.id, nummer=index, name=f"Gruppe {GRUPPENNAMEN[index]}")
        sitzung.add(gruppe)
        await sitzung.flush()
        gruppen_nach_index[index] = gruppe
        for kennung in mitglieder:
            nach_kennung[kennung].gruppe_id = gruppe.id

    for begegnung in plan.begegnungen:
        nummer += 1
        # Ohne Gruppe ist es die erste Runde des Schweizer Systems.
        zugehoerig: Gruppe | None = (
            gruppen_nach_index.get(begegnung.gruppe) if begegnung.gruppe is not None else None
        )
        sitzung.add(
            Spiel(
                turnier_id=lauf.id,
                nummer=nummer,
                phase="gruppe" if zugehoerig is not None else "runde",
                runde=begegnung.runde,
                gruppe_id=zugehoerig.id if zugehoerig is not None else None,
                bezeichnung=(
                    f"{zugehoerig.name}, Runde {begegnung.runde}"
                    if zugehoerig is not None
                    else f"Runde {begegnung.runde}"
                ),
                heim_id=nach_kennung[begegnung.heim].id,
                gast_id=nach_kennung[begegnung.gast].id,
            )
        )

    if plan.freilos is not None:
        nummer += 1
        empfaenger = nach_kennung[plan.freilos]
        empfaenger.freilose += 1
        sitzung.add(
            Spiel(
                turnier_id=lauf.id,
                nummer=nummer,
                phase="runde",
                runde=1,
                bezeichnung="Runde 1, Freilos",
                heim_id=empfaenger.id,
                zustand="beendet",
                sieger_id=empfaenger.id,
                beendet_am=jetzt(),
                freilos=True,
            )
        )

    nummer = _ko_schreiben(sitzung, lauf, plan.ko, nach_kennung, versatz=nummer)

    lauf.saat = gezogen
    lauf.zustand = "laufend"
    lauf.runde_angesetzt = 1
    lauf.ko_steht = bool(plan.ko)
    await sitzung.flush()
    return lauf


def _ko_schreiben(
    sitzung: AsyncSession,
    lauf: Turnier,
    raster: Sequence[los.KoBegegnung],
    nach_kennung: dict[str, Teilnehmer],
    versatz: int,
) -> int:
    """Schreibt ein KO-Raster hinter die vorhandenen Spiele.

    Der Versatz ist der Grund fuer diese eigene Funktion: die Nummern im
    Raster sind rasterintern, in der Datenbank sind sie turnierweit - und die
    Verweise "Sieger aus Spiel 3" muessen mitwandern.
    """
    if not raster:
        return versatz

    runden = max(spiel.runde for spiel in raster)
    for spiel in raster:
        sitzung.add(
            Spiel(
                turnier_id=lauf.id,
                nummer=versatz + spiel.nummer,
                phase="ko",
                runde=spiel.runde,
                bezeichnung=dienst.ko_bezeichnung(spiel.runde, runden),
                heim_id=(nach_kennung[spiel.heim.teilnehmer].id if spiel.heim.teilnehmer else None),
                gast_id=(nach_kennung[spiel.gast.teilnehmer].id if spiel.gast.teilnehmer else None),
                heim_aus_spiel=(versatz + spiel.heim.aus_spiel if spiel.heim.aus_spiel else None),
                gast_aus_spiel=(versatz + spiel.gast.aus_spiel if spiel.gast.aus_spiel else None),
            )
        )
    return versatz + len(raster)


async def naechste_runde(sitzung: AsyncSession, turnier_id: uuid.UUID) -> Turnier:
    """Setzt an, was nach dem jetzigen Stand ansteht - Raster oder Runde."""
    lauf = await turnier(sitzung, turnier_id)
    alle = await spiele(sitzung, turnier_id)
    schritt = dienst.naechster_schritt(_stand(lauf, alle))

    if schritt == "spielen":
        raise FalscherZustand(
            "Es sind noch Spiele offen. Erst wenn alle gewertet sind, steht die "
            "Tabelle - und ohne Tabelle gibt es keine Setzliste."
        )
    if schritt == "fertig":
        raise FalscherZustand("Es gibt nichts mehr anzusetzen, das Turnier ist durch")

    leute = await teilnehmer(sitzung, turnier_id)
    nach_kennung = {str(wer.id): wer for wer in leute}

    if schritt == "ko_ansetzen":
        await _ko_ansetzen(sitzung, lauf, alle, leute, nach_kennung)
    else:
        await _schweizer_runde_ansetzen(sitzung, lauf, alle, leute, nach_kennung)

    await _zustand_nachfuehren(sitzung, lauf)
    await sitzung.flush()
    return lauf


async def _ko_ansetzen(
    sitzung: AsyncSession,
    lauf: Turnier,
    alle: Sequence[Spiel],
    leute: Sequence[Teilnehmer],
    nach_kennung: dict[str, Teilnehmer],
) -> None:
    platzierungen = [
        dienst.platzierung(
            dienst.tabelle(
                [str(wer.id) for wer in leute if wer.gruppe_id == gruppe.id],
                _ergebnisse(alle, lauf.best_of, nur_gruppe=gruppe.id),
            )
        )
        for gruppe in await gruppen(sitzung, lauf.id)
    ]
    setzliste = los.ko_setzliste(platzierungen, lauf.weiter_pro_gruppe)

    # Eine Gruppe, aus der genau einer weiterkommt: dann ist der
    # Gruppensieger der Turniersieger, und ein Raster aus einem Namen waere
    # ein Spiel ohne Gegner.
    if len(setzliste) >= 2:
        raster = los.ko_raster(setzliste)
        _ko_schreiben(
            sitzung,
            lauf,
            raster,
            nach_kennung,
            versatz=max((spiel.nummer for spiel in alle), default=0),
        )
    lauf.ko_steht = True


async def _schweizer_runde_ansetzen(
    sitzung: AsyncSession,
    lauf: Turnier,
    alle: Sequence[Spiel],
    leute: Sequence[Teilnehmer],
    nach_kennung: dict[str, Teilnehmer],
) -> None:
    reihenfolge = dienst.platzierung(
        dienst.tabelle(
            [str(wer.id) for wer in leute],
            _ergebnisse(alle, lauf.best_of),
            freilose={str(wer.id): wer.freilose for wer in leute},
        )
    )
    bisherige = {
        frozenset((str(spiel.heim_id), str(spiel.gast_id)))
        for spiel in alle
        if spiel.heim_id and spiel.gast_id
    }
    paarungen, freilos = los.schweizer_paarung(
        reihenfolge,
        bisherige=bisherige,
        freilose={str(wer.id) for wer in leute if wer.freilose},
    )

    runde = lauf.runde_angesetzt + 1
    nummer = max((spiel.nummer for spiel in alle), default=0)
    for heim, gast in paarungen:
        nummer += 1
        sitzung.add(
            Spiel(
                turnier_id=lauf.id,
                nummer=nummer,
                phase="runde",
                runde=runde,
                bezeichnung=f"Runde {runde}",
                heim_id=nach_kennung[heim].id,
                gast_id=nach_kennung[gast].id,
            )
        )
    if freilos is not None:
        nummer += 1
        empfaenger = nach_kennung[freilos]
        empfaenger.freilose += 1
        sitzung.add(
            Spiel(
                turnier_id=lauf.id,
                nummer=nummer,
                phase="runde",
                runde=runde,
                bezeichnung=f"Runde {runde}, Freilos",
                heim_id=empfaenger.id,
                zustand="beendet",
                sieger_id=empfaenger.id,
                beendet_am=jetzt(),
                freilos=True,
            )
        )
    lauf.runde_angesetzt = runde


def _ergebnisse(
    alle: Sequence[Spiel], best_of: int, nur_gruppe: uuid.UUID | None = None
) -> list[dienst.Ergebnis]:
    """Die gewerteten Spiele als Eingabe fuer die Tabelle."""
    return [
        dienst.Ergebnis(
            heim=str(spiel.heim_id),
            gast=str(spiel.gast_id),
            saetze=tuple((satz[0], satz[1]) for satz in spiel.saetze),
            best_of=best_of,
        )
        for spiel in alle
        if spiel.heim_id
        and spiel.gast_id
        and not spiel.freilos
        and (nur_gruppe is None or spiel.gruppe_id == nur_gruppe)
    ]


def tabellen_daten(
    lauf: Turnier,
    alle: Sequence[Spiel],
    leute: Sequence[Teilnehmer],
    gruppenliste: Sequence[Gruppe],
) -> list[tuple[str, list[dienst.TabellenZeile]]]:
    """Je Gruppe eine Tabelle, sonst eine einzige.

    Rein rechnerisch und deshalb ohne ``await`` - die Daten sind schon da.
    """
    if gruppenliste:
        return [
            (
                gruppe.name,
                dienst.tabelle(
                    [str(wer.id) for wer in leute if wer.gruppe_id == gruppe.id],
                    _ergebnisse(alle, lauf.best_of, nur_gruppe=gruppe.id),
                ),
            )
            for gruppe in gruppenliste
        ]

    return [
        (
            "Tabelle",
            dienst.tabelle(
                [str(wer.id) for wer in leute],
                _ergebnisse(alle, lauf.best_of),
                freilose={str(wer.id): wer.freilose for wer in leute},
            ),
        )
    ]
