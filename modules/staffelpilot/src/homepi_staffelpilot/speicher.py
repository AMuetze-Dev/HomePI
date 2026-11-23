"""Datenbankzugriff. Hier faellt I/O an, hier stehen keine Entscheidungen."""

from __future__ import annotations

import datetime as dt
import os
import uuid

from homepi_core.auth.modelle import Benutzer
from sqlalchemy import ColumnElement, Select, delete, func, select, true
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import InstrumentedAttribute, selectinload

from . import dienst, texte
from .dienst import (
    AuftragUnbekannt,
    BefundUnbekannt,
    KeinZugang,
    RegelUnbekannt,
    SpielUnbekannt,
    StaffelUnbekannt,
    UebertragungUnbekannt,
    VorgangUnbekannt,
    VorgangVergeben,
)
from .modelle import (
    Ansicht,
    Auftrag,
    Auftraggeber,
    Befund,
    Einstellung,
    Karte,
    Kontoeinstellung,
    Kontotext,
    Kontozugang,
    Mannschaft,
    Regel,
    Regeldatei,
    Regelparameter,
    Regelwahl,
    Spielbericht,
    Staffel,
    Staffelkonto,
    Uebertragung,
    Vorgang,
)
from .schemas import (
    Abschluss,
    EinstellungenSetzen,
    Fortschritt,
    ImportAuftrag,
    MannschaftEingang,
    RegelAendern,
    RegeldateiAendern,
    RegeldateiSetzen,
    RegelEingang,
    StaffelAendern,
    StaffelAnlegen,
    StaffelnAusDfbnet,
    UebertragungAbschluss,
    VorgangAnlegen,
    VorlagenUebergeben,
    ZugangSetzen,
)

# ── Wer was sieht ─────────────────────────────────────────────────────────

#: Mit wessen Augen gelesen wird. `None` heisst *alles*, und das gibt es nur
#: beim Pruefdienst (`dienst.Blick`).
#:
#: Ohne Vorgabewert an jeder Funktion: wer ihn vergisst, soll am Typpruefer
#: scheitern und nicht die Berichte aller anderen lesen.
Konto = uuid.UUID | None


def _in_meinen(spalte: InstrumentedAttribute[uuid.UUID], konto: Konto) -> ColumnElement[bool]:
    """Nur Staffeln, die diesem Konto gehoeren."""
    if konto is None:
        return true()
    return spalte.in_(select(Staffelkonto.staffel_id).where(Staffelkonto.benutzer_id == konto))


def _von_mir(spalte: InstrumentedAttribute[uuid.UUID], konto: Konto) -> ColumnElement[bool]:
    """Nur Zeilen dieses Kontos."""
    return true() if konto is None else spalte == konto


# ── Staffeln ──────────────────────────────────────────────────────────────


async def staffeln(sitzung: AsyncSession, konto: Konto) -> list[Staffel]:
    ergebnis = await sitzung.execute(
        select(Staffel).where(_in_meinen(Staffel.id, konto)).order_by(Staffel.name)
    )
    return list(ergebnis.scalars())


async def staffel(sitzung: AsyncSession, konto: Konto, staffel_id: uuid.UUID) -> Staffel:
    ergebnis = await sitzung.execute(
        select(Staffel).where(Staffel.id == staffel_id, _in_meinen(Staffel.id, konto))
    )
    gefunden = ergebnis.scalar_one_or_none()
    if gefunden is None:
        raise StaffelUnbekannt(f"Es gibt keine Staffel mit der Kennung {staffel_id}")
    return gefunden


async def staffel_anlegen(
    sitzung: AsyncSession, konto: uuid.UUID, daten: StaffelAnlegen
) -> Staffel:
    """Sie gehoert dem, der sie anlegt."""
    dienst.name_frei(daten.name, (s.name for s in await staffeln(sitzung, konto)))
    neue = await _staffel_fuer(sitzung, konto, Staffel(**daten.model_dump()))
    await sitzung.refresh(neue)
    return neue


async def _staffel_fuer(sitzung: AsyncSession, konto: uuid.UUID, neue: Staffel) -> Staffel:
    """Anlegen und zuordnen -- beides oder keines. Eine Staffel ohne Konto saehe
    niemand."""
    sitzung.add(neue)
    await sitzung.flush()
    sitzung.add(Staffelkonto(staffel_id=neue.id, benutzer_id=konto))
    await sitzung.flush()
    return neue


async def regeldateien(sitzung: AsyncSession) -> list[Regeldatei]:
    """Alle Regeldateien, nach Namen -- das ist die Ladereihenfolge.

    `10_` vor `20_`: eine `90_eigene.py` kann am Ende gezielt etwas ersetzen.
    """
    ergebnis = await sitzung.execute(select(Regeldatei).order_by(Regeldatei.name))
    return list(ergebnis.scalars())


async def regeldatei(sitzung: AsyncSession, datei_id: uuid.UUID) -> Regeldatei:
    gefunden = await sitzung.get(Regeldatei, datei_id)
    if gefunden is None:
        raise dienst.RegeldateiUnbekannt(f"Es gibt keine Regeldatei mit der Kennung {datei_id}")
    return gefunden


async def regeldatei_setzen(sitzung: AsyncSession, daten: RegeldateiSetzen) -> Regeldatei:
    """Anlegen oder ueberschreiben, am Namen erkannt.

    Ueberschreiben und nicht danebenlegen: zwei Dateien desselben Namens gaebe
    es im Ordner des Pruefdienstes ohnehin nicht, und welche gewaenne, haenge
    an der Reihenfolge des Schreibens.
    """
    vorhanden = await sitzung.execute(select(Regeldatei).where(Regeldatei.name == daten.name))
    ziel = vorhanden.scalars().first()
    if ziel is None:
        ziel = Regeldatei(name=daten.name, inhalt=daten.inhalt, aktiv=daten.aktiv)
        sitzung.add(ziel)
    else:
        ziel.inhalt, ziel.aktiv = daten.inhalt, daten.aktiv
    await sitzung.flush()
    await sitzung.refresh(ziel)
    return ziel


async def vorlagen_uebernehmen(
    sitzung: AsyncSession, daten: VorlagenUebergeben
) -> tuple[list[str], list[str], bool]:
    """Die mitgelieferten Regeln des Pruefdienstes einmalig uebernehmen.

    Gibt zurueck: was angelegt wurde, was schon dastand, und ob die Uebergabe
    frueher schon stattgefunden hat.

    Der Vermerk liegt in derselben Tabelle wie die Einstellungen, unter einem
    Schluessel mit Unterstrich. Nicht im Ordner des Pruefdienstes: der
    ueberlebt kein neues Abbild, die Datenbank schon -- und eine Uebergabe,
    die sich nach jedem Neubau wiederholt, holt geloeschte Regeln zurueck.
    """
    gefunden = await sitzung.execute(
        select(Einstellung.schluessel).where(Einstellung.schluessel == dienst.VORLAGEN_VERMERK)
    )
    schon_geschehen = gefunden.scalars().first() is not None

    vorhanden = set((await sitzung.execute(select(Regeldatei.name))).scalars().all())
    angeboten = {v.name: v.inhalt for v in daten.vorlagen}
    zu_nehmen = dienst.vorlagen_auswaehlen(angeboten, vorhanden, schon_geschehen)

    for name in zu_nehmen:
        # Eingeschaltet: neun stillgelegte Regeln waeren dasselbe wie keine,
        # nur mit mehr Klicks.
        sitzung.add(Regeldatei(name=name, inhalt=angeboten[name], aktiv=True))

    if not schon_geschehen:
        # Vermerkt wird auch, wenn nichts anzulegen war -- sonst bietet der
        # Dienst beim naechsten Lauf wieder an, und die Entscheidung "weg"
        # haelt keinen Neustart aus.
        sitzung.add(Einstellung(schluessel=dienst.VORLAGEN_VERMERK, wert="true"))

    await sitzung.flush()
    uebergangen = sorted(name for name in angeboten if name in vorhanden)
    return zu_nehmen, uebergangen, schon_geschehen


async def regeldatei_aendern(
    sitzung: AsyncSession, datei_id: uuid.UUID, daten: RegeldateiAendern
) -> Regeldatei:
    """Nur die mitgeschickten Felder. Ausgelassene bleiben stehen."""
    ziel = await regeldatei(sitzung, datei_id)
    if daten.inhalt is not None:
        ziel.inhalt = daten.inhalt
    if daten.aktiv is not None:
        ziel.aktiv = daten.aktiv
    await sitzung.flush()
    return ziel


async def regeldatei_loeschen(sitzung: AsyncSession, datei_id: uuid.UUID) -> None:
    """Weg. Der Pruefdienst raeumt sie beim naechsten Lauf aus seinem Ordner.

    Was daran haengt, bleibt: Befunde dieser Regel stehen weiter in der
    Warteschlange. Eine geloeschte Datei heisst "wird nicht mehr geprueft" und
    nicht "ist nie passiert".
    """
    ziel = await regeldatei(sitzung, datei_id)
    await sitzung.delete(ziel)
    await sitzung.flush()


async def ansicht_setzen(
    sitzung: AsyncSession,
    konto: Konto,
    auftrag_id: uuid.UUID,
    art: str,
    bild: bytes,
    schritt: str,
) -> None:
    """Das Abbild zu diesem Auftrag ablegen -- ersetzt, nicht angehaeuft.

    Hoechstens zwei je Auftrag (siehe `modelle.Ansicht`). Ein Band aus Bildern
    waere nach drei Prueflaeufen groesser als die ganze uebrige Datenbank.
    """
    await auftrag(sitzung, konto, auftrag_id)
    vorhanden = await sitzung.execute(
        select(Ansicht).where(Ansicht.auftrag_id == auftrag_id, Ansicht.art == art)
    )
    ziel = vorhanden.scalars().first()
    if ziel is None:
        sitzung.add(Ansicht(auftrag_id=auftrag_id, art=art, bild=bild, schritt=schritt))
    else:
        ziel.bild, ziel.schritt = bild, schritt
    await sitzung.flush()


async def ansicht(sitzung: AsyncSession, konto: Konto, auftrag_id: uuid.UUID, art: str) -> Ansicht:
    """Das Abbild, oder 404. Kein leeres Bild und kein Platzhalter."""
    await auftrag(sitzung, konto, auftrag_id)
    gefunden = await sitzung.execute(
        select(Ansicht).where(Ansicht.auftrag_id == auftrag_id, Ansicht.art == art)
    )
    ziel = gefunden.scalars().first()
    if ziel is None:
        raise dienst.AnsichtUnbekannt(f"Zu diesem Auftrag gibt es keine Ansicht '{art}'")
    return ziel


async def ansicht_arten(sitzung: AsyncSession, konto: Konto, auftrag_id: uuid.UUID) -> list[str]:
    """Welche Abbilder es zu diesem Auftrag gibt.

    Damit die Oberflaeche nicht auf zwei Adressen raten muss, von denen eine
    404 gibt -- ein Fehler im Protokoll des Browsers, den niemand bestellt hat.
    """
    await auftrag(sitzung, konto, auftrag_id)
    gefunden = await sitzung.execute(
        select(Ansicht.art).where(Ansicht.auftrag_id == auftrag_id).order_by(Ansicht.art)
    )
    return [str(a) for a in gefunden.scalars()]


async def staffeln_aus_dfbnet(
    sitzung: AsyncSession, konto: uuid.UUID, eingang: StaffelnAusDfbnet
) -> tuple[int, int, list[str]]:
    """Die Liste "Eigene Staffeln" uebernehmen. Gibt (angelegt, aktualisiert, Namen).

    Abgeglichen wird nur mit den **eigenen** Staffeln. Fuehrt ein anderes
    Konto dieselbe, hat es seine -- und diese hier wird trotzdem angelegt.

    Gesucht wird **zuerst ueber die Kennung** und erst dann ueber den Namen.
    Die Kennung ist das einzig Stabile: die Bezeichnung traegt einen
    Sponsornamen, und wer einmal von Hand "Stadtliga C" eingetippt hat, soll
    beim Abgleich nicht eine zweite Staffel danebengestellt bekommen, sondern
    seine korrigiert.

    **Geloescht wird nichts.** Was nicht in der Liste steht, kann aus einer
    frueheren Saison stammen oder von Hand angelegt sein -- und eine Staffel
    zu entfernen naehme ihre Spielberichte mit.

    `aktiv` bleibt unberuehrt: ob eine Staffel mitlaeuft, entscheidet der
    Staffelleiter und nicht DFBnet.
    """
    vorhanden = await staffeln(sitzung, konto)
    nach_kennung = {s.dfbnet_kennung: s for s in vorhanden if s.dfbnet_kennung}

    def passende(wert: str) -> list[Staffel]:
        """Staffeln, deren Name oder Spielklasse auf dasselbe hinauslaeuft."""
        gesucht = dienst.gefaltet(wert)
        if not gesucht:
            return []
        return [
            s
            for s in vorhanden
            if gesucht in (dienst.gefaltet(s.name), dienst.gefaltet(s.spielklasse))
        ]

    angelegt = aktualisiert = 0
    namen: list[str] = []
    for zeile in eingang.staffeln:
        ziel = nach_kennung.get(zeile.kennung)
        if ziel is None:
            # Name und Spielklasse, beide normalisiert und beide gegen beide:
            # wer "1. Kreisklasse" als Namen eingetragen hat, soll seine
            # Staffel korrigiert bekommen und keine zweite daneben.
            #
            # Nur bei **genau einem** Treffer. Zwei Kandidaten heissen, dass
            # niemand sicher sagen kann, welche gemeint war -- und eine
            # zusammengelegte Staffel, die es nicht war, nimmt die
            # Spielberichte der falschen mit.
            for wert in (zeile.name, zeile.spielklasse):
                treffer = passende(wert)
                if len(treffer) == 1:
                    ziel = treffer[0]
                    break

        if ziel is None:
            await _staffel_fuer(
                sitzung,
                konto,
                Staffel(
                    name=zeile.name,
                    altersklasse=zeile.altersklasse,
                    spielklasse=zeile.spielklasse,
                    saison=zeile.saison,
                    spieltage=zeile.spieltage,
                    dfbnet_kennung=zeile.kennung,
                ),
            )
            angelegt += 1
        else:
            ziel.name = zeile.name
            ziel.altersklasse = zeile.altersklasse
            ziel.spielklasse = zeile.spielklasse
            ziel.dfbnet_kennung = zeile.kennung
            if zeile.saison:
                ziel.saison = zeile.saison
            # Eine 0 heisst *nicht bekannt* und soll eine bekannte Zahl nicht
            # ueberschreiben -- siehe `modelle.Staffel.spieltage`.
            if zeile.spieltage:
                ziel.spieltage = zeile.spieltage
            aktualisiert += 1
        namen.append(zeile.name)

    await sitzung.flush()
    return angelegt, aktualisiert, namen


async def staffel_aendern(
    sitzung: AsyncSession, konto: Konto, staffel_id: uuid.UUID, daten: StaffelAendern
) -> Staffel:
    """Nur die mitgeschickten Felder. Ausgelassene bleiben stehen."""
    gefunden = await staffel(sitzung, konto, staffel_id)
    felder = daten.model_dump(exclude_none=True)
    if "name" in felder:
        uebrige = (s.name for s in await staffeln(sitzung, konto) if s.id != staffel_id)
        dienst.name_frei(felder["name"], uebrige)
    for name, wert in felder.items():
        setattr(gefunden, name, wert)
    await sitzung.flush()
    return gefunden


async def staffel_loeschen(sitzung: AsyncSession, konto: Konto, staffel_id: uuid.UUID) -> None:
    await sitzung.delete(await staffel(sitzung, konto, staffel_id))


async def anzahl_aktiver_staffeln(sitzung: AsyncSession, konto: Konto) -> int:
    ergebnis = await sitzung.execute(
        select(func.count())
        .select_from(Staffel)
        .where(Staffel.aktiv.is_(True), _in_meinen(Staffel.id, konto))
    )
    return int(ergebnis.scalar_one())


# ── Spielberichte ─────────────────────────────────────────────────────────


async def spiele(
    sitzung: AsyncSession, konto: Konto, staffel_id: uuid.UUID | None = None
) -> list[Spielbericht]:
    """Immer mit Befunden.

    Der Aufrufer zaehlt sie -- ohne `selectinload` waere das ein Nachladen
    mitten in der Antwort, und unter async ist das ein `MissingGreenlet`.
    """
    frage = (
        select(Spielbericht)
        .options(selectinload(Spielbericht.befunde))
        .where(_in_meinen(Spielbericht.staffel_id, konto))
        .order_by(Spielbericht.datum.desc(), Spielbericht.heim)
    )
    if staffel_id is not None:
        frage = frage.where(Spielbericht.staffel_id == staffel_id)
    ergebnis = await sitzung.execute(frage)
    return list(ergebnis.scalars())


async def spiel(sitzung: AsyncSession, konto: Konto, spiel_id: uuid.UUID) -> Spielbericht:
    ergebnis = await sitzung.execute(
        select(Spielbericht)
        .options(selectinload(Spielbericht.befunde))
        .where(Spielbericht.id == spiel_id, _in_meinen(Spielbericht.staffel_id, konto))
    )
    gefunden = ergebnis.scalar_one_or_none()
    if gefunden is None:
        raise SpielUnbekannt(f"Es gibt keinen Spielbericht mit der Kennung {spiel_id}")
    return gefunden


async def befund(sitzung: AsyncSession, konto: Konto, befund_id: uuid.UUID) -> Befund:
    ergebnis = await sitzung.execute(
        select(Befund)
        .join(Spielbericht, Spielbericht.id == Befund.spiel_id)
        .where(Befund.id == befund_id, _in_meinen(Spielbericht.staffel_id, konto))
    )
    gefunden = ergebnis.scalar_one_or_none()
    if gefunden is None:
        raise BefundUnbekannt(f"Es gibt keinen Befund mit der Kennung {befund_id}")
    return gefunden


async def einspielen(
    sitzung: AsyncSession, konto: uuid.UUID, auftrag: ImportAuftrag
) -> tuple[int, int, int]:
    """Spielberichte anlegen oder auffrischen. Gibt (angelegt, aktualisiert,
    Befunde) zurueck.

    Ein erneuter Import desselben Spiels ersetzt seine Befunde vollstaendig -
    ein Prueflauf ist die vollstaendige Aussage ueber einen Bericht, nicht ein
    Nachtrag. Getroffene Entscheidungen zu bereits bekannten Befunden bleiben
    dabei erhalten; sie an derselben Regel und derselben Person wiederzufinden
    ist das, was den zweiten Prueflauf ertraeglich macht.
    """
    await staffel(sitzung, konto, auftrag.staffel_id)
    # Vor dem ersten Schreiben und nicht je Spiel: ein halb eingespielter Lauf
    # waere schlimmer als ein abgewiesener.
    werte = await einstellungen(sitzung, konto)
    dienst.beispieldaten_pruefen([s.dfbnet_id for s in auftrag.spiele], werte.beispieldaten)
    angelegt = aktualisiert = befunde_gesamt = 0

    for eingang in auftrag.spiele:
        vorhanden = await sitzung.execute(
            select(Spielbericht)
            .options(selectinload(Spielbericht.befunde))
            .where(
                Spielbericht.staffel_id == auftrag.staffel_id,
                Spielbericht.dfbnet_id == eingang.dfbnet_id,
            )
        )
        bericht = vorhanden.scalar_one_or_none()
        # Was der Staffelleiter zu einem Befund schon entschieden hat, nach
        # Regel und Person. Genau das wiederzufinden macht den zweiten
        # Prueflauf ertraeglich.
        frueher: dict[tuple[str, str], Befund] = {}

        if bericht is None:
            bericht = Spielbericht(
                staffel_id=auftrag.staffel_id,
                dfbnet_id=eingang.dfbnet_id,
                datum=eingang.datum,
                heim=eingang.heim,
                gast=eingang.gast,
                ergebnis=eingang.ergebnis,
                spielnummer=eingang.spielnummer,
                anstoss=eingang.anstoss,
                spielort=eingang.spielort,
                spieltag=eingang.spieltag,
                mannschaftsart=eingang.mannschaftsart,
                wettbewerb=eingang.wettbewerb,
            )
            sitzung.add(bericht)
            await sitzung.flush()
            angelegt += 1
        else:
            bericht.datum = eingang.datum
            bericht.heim = eingang.heim
            bericht.gast = eingang.gast
            bericht.ergebnis = eingang.ergebnis
            # Kopfdaten nur ueberschreiben, wenn der Lauf welche mitbringt:
            # ein Bericht, den DFBnet gerade nicht hergab, soll nicht die
            # Angaben loeschen, die beim letzten Mal ankamen.
            for feld in (
                "spielnummer",
                "anstoss",
                "spielort",
                "spieltag",
                "mannschaftsart",
                "wettbewerb",
            ):
                wert = getattr(eingang, feld)
                if wert:
                    setattr(bericht, feld, wert)
            frueher = {(b.regel, b.person): b for b in bericht.befunde}
            # Ein Prueflauf ist die vollstaendige Aussage ueber einen Bericht:
            # was er nicht mehr meldet, ist keine offene Arbeit mehr.
            await sitzung.execute(delete(Befund).where(Befund.spiel_id == bericht.id))
            aktualisiert += 1

        for rang, b in enumerate(eingang.befunde):
            alt = frueher.get((b.regel, b.person))
            # Ueber die Fremdschluesselspalte und nicht ueber die Beziehung:
            # `bericht.befunde` waere unter async ein Nachladen an einer
            # Stelle, an der nicht await gesagt werden kann.
            sitzung.add(
                Befund(
                    spiel_id=bericht.id,
                    regel=b.regel,
                    schwere=b.schwere,
                    titel=b.titel,
                    text=b.text,
                    person=b.person,
                    mannschaft=b.mannschaft,
                    weg=b.weg,
                    einzelheiten=b.einzelheiten,
                    rang=rang,
                    entscheidung=alt.entscheidung if alt else "offen",
                    grund=alt.grund if alt else "",
                    entschieden_am=alt.entschieden_am if alt else None,
                )
            )
            befunde_gesamt += 1

        # Die Karten desselben Spiels ebenso: ein Prueflauf ist die
        # vollstaendige Aussage ueber einen Bericht. Wuerden sie sich
        # anhaeufen, zaehlte § 58 nach dem dritten Lauf die dreifache Zahl.
        await sitzung.execute(delete(Karte).where(Karte.spielbericht_id == bericht.id))
        for k in eingang.karten:
            sitzung.add(
                Karte(
                    staffel_id=auftrag.staffel_id,
                    spielbericht_id=bericht.id,
                    datum=eingang.datum,
                    wettbewerb=eingang.wettbewerb,
                    person=k.person,
                    pass_nr=k.pass_nr,
                    art=k.art,
                    minute=k.minute,
                    mannschaft=k.mannschaft,
                )
            )
        await sitzung.flush()
        # Die Beziehung haelt sonst den Stand von vor dem Loeschen.
        await sitzung.refresh(bericht, ["befunde"])

    return angelegt, aktualisiert, befunde_gesamt


async def karten(
    sitzung: AsyncSession,
    konto: Konto,
    pass_nr: str,
    wettbewerb: str = "",
    seit: dt.date | None = None,
) -> list[Karte]:
    """Die Karten einer Person, aelteste zuerst.

    Nach Passnummer und nicht nach Namen: dieselbe Person heisst im
    Spielbericht mal "Mueller, Max" und mal "Müller, Max", und zwei Vereine
    haben zwei Maxe.

    `wettbewerb` und `seit` schraenken ein, weil § 58 (2) beides verlangt:
    Pokal und Meisterschaft getrennt, und nach einer verwirkten Sperre faengt
    der Zaehler von vorn an.
    """
    anfrage = select(Karte).where(Karte.pass_nr == pass_nr, _in_meinen(Karte.staffel_id, konto))
    if wettbewerb:
        anfrage = anfrage.where(Karte.wettbewerb == wettbewerb)
    if seit is not None:
        anfrage = anfrage.where(Karte.datum >= seit)
    anfrage = anfrage.order_by(Karte.datum, Karte.minute)
    return list((await sitzung.execute(anfrage)).scalars().all())


async def entscheidung_setzen(
    sitzung: AsyncSession, konto: Konto, befund_id: uuid.UUID, art: str, grund: str
) -> Befund:
    gefunden = await befund(sitzung, konto, befund_id)
    gefunden.entscheidung = art
    gefunden.grund = grund
    gefunden.entschieden_am = dt.datetime.now(dt.UTC)
    await sitzung.flush()
    return gefunden


async def entscheidung_zuruecknehmen(
    sitzung: AsyncSession, konto: Konto, befund_id: uuid.UUID
) -> Befund:
    """Der Befund ist wieder offen - und das Spiel damit nicht mehr abgehakt.

    Den Haken stehen zu lassen waere die eine Zusage dieses Artefakts
    gebrochen: abgehakt heisst, zu jedem Befund liegt eine Entscheidung vor.
    """
    gefunden = await befund(sitzung, konto, befund_id)
    gefunden.entscheidung = "offen"
    gefunden.grund = ""
    gefunden.entschieden_am = None
    bericht = await spiel(sitzung, konto, gefunden.spiel_id)
    bericht.abgehakt = False
    bericht.abgehakt_am = None
    await sitzung.flush()
    return gefunden


async def haken_setzen(
    sitzung: AsyncSession, konto: Konto, spiel_id: uuid.UUID, gesetzt: bool
) -> Spielbericht:
    bericht = await spiel(sitzung, konto, spiel_id)
    bericht.abgehakt = gesetzt
    bericht.abgehakt_am = dt.datetime.now(dt.UTC) if gesetzt else None
    await sitzung.flush()
    return bericht


# ── Einstellungen ─────────────────────────────────────────────────────────


async def einstellungen(sitzung: AsyncSession, konto: uuid.UUID) -> dienst.Einstellungen:
    """Die geprueften Werte, nicht die rohen Zeilen.

    Die Pruefung steht in `dienst.einstellungen_aus` und damit an einer
    Stelle: sonst entscheidet jeder Aufrufer selbst, was eine leere
    Zeichenkette bedeutet.
    """
    ergebnis = await sitzung.execute(
        select(Kontoeinstellung).where(Kontoeinstellung.benutzer_id == konto)
    )
    return dienst.einstellungen_aus({e.schluessel: e.wert for e in ergebnis.scalars()})


async def freigegebene_konten(sitzung: AsyncSession) -> set[uuid.UUID]:
    """Wessen Uebertragungen hinaus duerfen."""
    roh: dict[uuid.UUID, dict[str, str]] = {}
    for e in (await sitzung.execute(select(Kontoeinstellung))).scalars():
        roh.setdefault(e.benutzer_id, {})[e.schluessel] = e.wert
    return dienst.freigegebene(roh)


async def einrichtungsstand(sitzung: AsyncSession, konto: uuid.UUID) -> tuple[bool, int, bool]:
    """Zugang vorhanden, Anzahl aktiver Staffeln, abgehakt.

    Die Entscheidung daraus faellt `dienst.einrichtung_schritt`; hier wird nur
    gelesen.
    """
    gefunden = await _zugang(sitzung, konto)
    anzahl = await anzahl_aktiver_staffeln(sitzung, konto)
    werte = await einstellungen(sitzung, konto)
    return gefunden is not None, anzahl, werte.einrichtung_erledigt


async def einstellungen_setzen(
    sitzung: AsyncSession, konto: uuid.UUID, daten: EinstellungenSetzen
) -> dienst.Einstellungen:
    """Nur die mitgeschickten Felder. Ausgelassene bleiben stehen."""
    ergebnis = await sitzung.execute(
        select(Kontoeinstellung).where(Kontoeinstellung.benutzer_id == konto)
    )
    vorhanden = {e.schluessel: e for e in ergebnis.scalars()}
    for schluessel, wert in daten.model_dump(exclude_none=True).items():
        if schluessel in vorhanden:
            vorhanden[schluessel].wert = str(wert)
        else:
            sitzung.add(Kontoeinstellung(benutzer_id=konto, schluessel=schluessel, wert=str(wert)))
    await sitzung.flush()
    return await einstellungen(sitzung, konto)


# ── Mannschaften ──────────────────────────────────────────────────────────


async def mannschaften(
    sitzung: AsyncSession, konto: Konto, staffel_id: uuid.UUID
) -> list[Mannschaft]:
    await staffel(sitzung, konto, staffel_id)
    ergebnis = await sitzung.execute(
        select(Mannschaft)
        .where(Mannschaft.staffel_id == staffel_id)
        .order_by(Mannschaft.verein, Mannschaft.nummer, Mannschaft.name)
    )
    return list(ergebnis.scalars())


async def mannschaften_setzen(
    sitzung: AsyncSession,
    konto: Konto,
    staffel_id: uuid.UUID,
    eingang: list[MannschaftEingang],
) -> list[Mannschaft]:
    """Die Meldung als Ganzes, nicht als Aenderung.

    Was DFBnet nicht mehr meldet, ist zurueckgezogen. Bestaetigte Zuordnungen
    ueberleben trotzdem: sie an eine Kennung zu binden, die mit der Meldung
    verschwindet, hiesse, jede Handkorrektur beim naechsten Einspielen
    wegzuwerfen -- und genau das ist der Fehler, vor dem die Zuordnung
    schuetzen soll. Der Name traegt sie hinueber.
    """
    alt = {m.name: m for m in await mannschaften(sitzung, konto, staffel_id)}
    geraten = dienst.hoehere_raten([m.name for m in eingang])

    await sitzung.execute(delete(Mannschaft).where(Mannschaft.staffel_id == staffel_id))
    for m in eingang:
        verein, nummer = dienst.verein_und_nummer(m.name)
        vorher = alt.get(m.name)
        # Reihenfolge der Quellen: was jetzt gesagt wurde, sonst was bestaetigt
        # war, sonst der Vorschlag.
        if m.hoehere or m.bestaetigt:
            hoehere, bestaetigt = list(m.hoehere), True
        elif vorher is not None and vorher.bestaetigt:
            hoehere, bestaetigt = list(vorher.hoehere), True
        else:
            hoehere, bestaetigt = geraten.get(m.name, []), False
        sitzung.add(
            Mannschaft(
                staffel_id=staffel_id,
                name=m.name,
                verein=m.verein or verein,
                nummer=m.nummer or nummer,
                ist_sg=m.ist_sg,
                hoehere=hoehere,
                bestaetigt=bestaetigt,
            )
        )
    await sitzung.flush()
    return await mannschaften(sitzung, konto, staffel_id)


# ── Vorgaenge ─────────────────────────────────────────────────────────────


def _vorgaenge(konto: Konto) -> Select[tuple[Vorgang]]:
    """Vorgaenge zu Spielen der eigenen Staffeln."""
    return (
        select(Vorgang)
        .join(Befund, Befund.id == Vorgang.befund_id)
        .join(Spielbericht, Spielbericht.id == Befund.spiel_id)
        .where(_in_meinen(Spielbericht.staffel_id, konto))
    )


async def vorgaenge(
    sitzung: AsyncSession, konto: Konto, zustand: str | None = None
) -> list[Vorgang]:
    frage = _vorgaenge(konto).order_by(Vorgang.aktenzeichen.desc())
    if zustand is not None:
        frage = frage.where(Vorgang.zustand == zustand)
    ergebnis = await sitzung.execute(frage)
    return list(ergebnis.scalars())


async def vorgang(sitzung: AsyncSession, konto: Konto, vorgang_id: uuid.UUID) -> Vorgang:
    ergebnis = await sitzung.execute(_vorgaenge(konto).where(Vorgang.id == vorgang_id))
    gefunden = ergebnis.scalar_one_or_none()
    if gefunden is None:
        raise VorgangUnbekannt(f"Es gibt keinen Vorgang mit der Kennung {vorgang_id}")
    return gefunden


async def vorgang_mit_spiel(
    sitzung: AsyncSession, konto: Konto, vorgang_id: uuid.UUID
) -> tuple[Vorgang, Befund, Spielbericht, Staffel]:
    """Ein Vorgang samt allem, was auf dem Mahnungsformular steht.

    In einer Abfrage statt in vier: das Formular braucht den Befund (welches
    Kreuz), das Spiel (Kopfdaten) und die Staffel (Spielklasse), und jede
    weitere Runde zur Datenbank waere eine, die unter `async` an der falschen
    Stelle nachlaedt.
    """
    ergebnis = await sitzung.execute(
        select(Vorgang, Befund, Spielbericht, Staffel)
        .join(Befund, Befund.id == Vorgang.befund_id)
        .join(Spielbericht, Spielbericht.id == Befund.spiel_id)
        .join(Staffel, Staffel.id == Spielbericht.staffel_id)
        .where(Vorgang.id == vorgang_id, _in_meinen(Spielbericht.staffel_id, konto))
    )
    zeile = ergebnis.first()
    if zeile is None:
        raise VorgangUnbekannt(f"Es gibt keinen Vorgang mit der Kennung {vorgang_id}")
    return zeile[0], zeile[1], zeile[2], zeile[3]


async def vorgang_zu_befund(sitzung: AsyncSession, befund_id: uuid.UUID) -> Vorgang | None:
    ergebnis = await sitzung.execute(select(Vorgang).where(Vorgang.befund_id == befund_id))
    return ergebnis.scalar_one_or_none()


async def anzahl_entwuerfe(sitzung: AsyncSession, konto: Konto) -> int:
    entwuerfe = _vorgaenge(konto).where(Vorgang.zustand == "entwurf").subquery()
    ergebnis = await sitzung.execute(select(func.count()).select_from(entwuerfe))
    return int(ergebnis.scalar_one())


async def _naechstes_aktenzeichen(sitzung: AsyncSession, konto: uuid.UUID, saison: str) -> str:
    """Fortlaufend je Saison und Konto.

    Je Konto: eine Luecke in der eigenen Zaehlung verriete, wie viele Schreiben
    andere verschicken.

    Gezaehlt wird, was schon vergeben ist, und nicht ein Zaehler in einer
    eigenen Zeile: ein geloeschter Vorgang darf keine Luecke lassen.
    """
    kern = saison.strip().replace("/", "-") or "ohne-saison"
    meine = _vorgaenge(konto).where(Vorgang.aktenzeichen.like(f"{kern}-%")).subquery()
    ergebnis = await sitzung.execute(select(func.count()).select_from(meine))
    return dienst.aktenzeichen(saison, int(ergebnis.scalar_one()) + 1)


async def vorgang_anlegen(
    sitzung: AsyncSession, konto: uuid.UUID, befund_id: uuid.UUID, daten: VorgangAnlegen
) -> Vorgang:
    """Aus einem Befund einen Entwurf machen.

    Der Text entsteht hier einmal und wird danach nicht wieder erzeugt: ein
    spaeteres Neuerzeugen wuerde eine Formulierung ueberschreiben, die sich
    jemand ueberlegt hat.

    Dass es zu einem Befund nur einen Vorgang gibt, sichert die Datenbank und
    nicht eine Abfrage davor: die waere ein Rennen zwischen zwei gleichzeitigen
    Anlagen und zugleich eine zweite Stelle, an der dieselbe Regel steht.
    """
    gefunden = await befund(sitzung, konto, befund_id)
    art = dienst.art_aus_weg(gefunden.weg)
    bericht = await spiel(sitzung, konto, gefunden.spiel_id)
    staffel_dazu = await staffel(sitzung, konto, bericht.staffel_id)
    # Name, Verband und Saetze dessen, der das Schreiben anlegt: er schickt es.
    werte = await einstellungen(sitzung, konto)
    eigener = (await kontotexte(sitzung, konto)).get(gefunden.regel)

    anlass = dienst.Anlass(
        staffel=staffel_dazu.name,
        saison=staffel_dazu.saison,
        heim=bericht.heim,
        gast=bericht.gast,
        spieldatum=bericht.datum,
        dfbnet_id=bericht.dfbnet_id,
        titel=gefunden.titel,
        sachverhalt=gefunden.text,
        verein=daten.verein or gefunden.mannschaft,
        betroffener=daten.betroffener or gefunden.person,
        grund=daten.grund or gefunden.titel,
        regel=gefunden.regel,
        einzelheiten=gefunden.einzelheiten or {},
        vorlage=texte.eigene(gefunden.regel, eigener.sachverhalt, eigener.hinweis)
        if eigener is not None
        else None,
    )
    schreiben = dienst.vorgang_entwurf(art, anlass, werte, dt.date.today())

    neuer = Vorgang(
        befund_id=befund_id,
        art=art,
        aktenzeichen=await _naechstes_aktenzeichen(sitzung, konto, staffel_dazu.saison),
        verein=anlass.verein,
        betroffener=anlass.betroffener,
        grund=anlass.grund,
        empfaenger=daten.empfaenger or schreiben.empfaenger,
        betreff=schreiben.betreff,
        text=schreiben.text,
    )
    sitzung.add(neuer)
    try:
        await sitzung.flush()
    except IntegrityError as fehler:
        await sitzung.rollback()
        raise VorgangVergeben(f"Zum Befund {befund_id} gibt es bereits einen Vorgang") from fehler
    await sitzung.refresh(neuer)
    return neuer


async def vorgang_aendern(
    sitzung: AsyncSession, konto: Konto, vorgang_id: uuid.UUID, felder: dict[str, str]
) -> Vorgang:
    gefunden = await vorgang(sitzung, konto, vorgang_id)
    for name, wert in felder.items():
        setattr(gefunden, name, wert)
    await sitzung.flush()
    return gefunden


async def vorgang_zustand(
    sitzung: AsyncSession, konto: Konto, vorgang_id: uuid.UUID, neu: str
) -> Vorgang:
    gefunden = await vorgang(sitzung, konto, vorgang_id)
    gefunden.zustand = dienst.zustand_weiter(gefunden.zustand, neu)
    # Nur beim ersten Mal. Wer ein Schreiben zurueckholt und erneut abschickt,
    # hat es trotzdem an dem Tag versandt, an dem es beim Verein ankam.
    if neu == "versandt" and gefunden.versandt_am is None:
        gefunden.versandt_am = dt.datetime.now(dt.UTC)
    await sitzung.flush()
    return gefunden


async def vorgang_loeschen(sitzung: AsyncSession, konto: Konto, vorgang_id: uuid.UUID) -> None:
    await sitzung.delete(await vorgang(sitzung, konto, vorgang_id))


async def vorgaenge_zu_befunden(
    sitzung: AsyncSession, befund_ids: list[uuid.UUID]
) -> dict[uuid.UUID, uuid.UUID]:
    """Eine Abfrage fuer alle Befunde eines Berichts.

    Je Befund einzeln zu fragen waere bei zwanzig Befunden zwanzig Abfragen
    fuer eine Ansicht -- und genau das faellt erst auf dem Pi auf.
    """
    if not befund_ids:
        return {}
    ergebnis = await sitzung.execute(
        select(Vorgang.befund_id, Vorgang.id).where(Vorgang.befund_id.in_(befund_ids))
    )
    return {befund_id: vorgang_id for befund_id, vorgang_id in ergebnis.all()}


# ── Regelkatalog ──────────────────────────────────────────────────────────


async def beispieldaten_zaehlen(sitzung: AsyncSession, konto: Konto) -> int:
    """Wie viele erfundene Spiele noch in den Listen stehen."""
    ergebnis = await sitzung.execute(
        select(func.count())
        .select_from(Spielbericht)
        .where(
            Spielbericht.dfbnet_id.startswith(dienst.BEISPIEL_PRAEFIX),
            _in_meinen(Spielbericht.staffel_id, konto),
        )
    )
    return int(ergebnis.scalar_one())


async def beispieldaten_loeschen(sitzung: AsyncSession, konto: Konto) -> int:
    """Die erfundenen Spiele der eigenen Staffeln weg, mit allem daran.

    Befunde und Karten gehen am Fremdschluessel mit. Vorgaenge haengen am
    Befund und damit ebenso -- ein Schreiben zu einem Spiel, das es nie gab,
    soll nicht als Waise zurueckbleiben.

    Nur die erfundenen: die Bedingung steht auf dem Praefix und nicht auf
    einem Zeitraum. Ein `DELETE` ohne `WHERE` an dieser Stelle waere die
    Saison.
    """
    # Erst zaehlen, dann loeschen: `rowcount` ist je nach Treiber nicht
    # zugesichert, und die Zahl steht hinterher in der Oberflaeche.
    gefunden = await beispieldaten_zaehlen(sitzung, konto)
    await sitzung.execute(
        delete(Spielbericht).where(
            Spielbericht.dfbnet_id.startswith(dienst.BEISPIEL_PRAEFIX),
            _in_meinen(Spielbericht.staffel_id, konto),
        )
    )
    await sitzung.flush()
    return gefunden


async def regeln(sitzung: AsyncSession) -> list[Regel]:
    ergebnis = await sitzung.execute(select(Regel).order_by(Regel.name))
    return list(ergebnis.scalars())


async def regel(sitzung: AsyncSession, regel_id: uuid.UUID) -> Regel:
    gefunden = await sitzung.get(Regel, regel_id)
    if gefunden is None:
        raise RegelUnbekannt(f"Es gibt keine Regel mit der Kennung {regel_id}")
    return gefunden


async def regelkatalog_setzen(sitzung: AsyncSession, eingang: list[RegelEingang]) -> list[Regel]:
    """Den Katalog als Ganzes uebernehmen, ohne die Schalter zu verlieren.

    `aktiv` gehoert dem Staffelleiter. Wer den Katalog neu einspielt, meldet
    was es gibt -- nicht, was jemand davon sehen will.

    Die Saetze fuer das Schreiben stehen in einer eigenen Tabelle und bleiben
    hier unberuehrt: sie sollen eine Regel ueberleben, die ein Lauf einmal
    nicht gemeldet hat.
    """
    vorher = {r.schluessel: r.aktiv for r in await regeln(sitzung)}
    gemeldet = {r.schluessel for r in eingang}

    await sitzung.execute(delete(Regel).where(Regel.schluessel.notin_(gemeldet or {""})))
    vorhanden = {r.schluessel: r for r in await regeln(sitzung)}

    for r in eingang:
        ziel = vorhanden.get(r.schluessel)
        if ziel is None:
            sitzung.add(
                Regel(**r.model_dump(exclude={"parameter"}), aktiv=vorher.get(r.schluessel, True))
            )
        else:
            ziel.name, ziel.beschreibung = r.name, r.beschreibung
            ziel.schwere, ziel.weg = r.schwere, r.weg

    # Die Parameter kommen mit dem Katalog und gehen mit ihm: ersetzt als
    # Ganzes. Die eigenen Werte stehen in `Regelwahl` und bleiben.
    await sitzung.execute(delete(Regelparameter))
    for r in eingang:
        for stelle, p in enumerate(r.parameter):
            sitzung.add(Regelparameter(regel=r.schluessel, reihenfolge=stelle, **p.model_dump()))
    await sitzung.flush()
    return await regeln(sitzung)


async def regelparameter(sitzung: AsyncSession) -> dict[str, list[Regelparameter]]:
    """Die Parameter aller Regeln, je Regel in der gemeldeten Reihenfolge."""
    ergebnis = await sitzung.execute(
        select(Regelparameter).order_by(Regelparameter.regel, Regelparameter.reihenfolge)
    )
    je_regel: dict[str, list[Regelparameter]] = {}
    for p in ergebnis.scalars():
        je_regel.setdefault(p.regel, []).append(p)
    return je_regel


async def regelwahlen(sitzung: AsyncSession, benutzer_id: uuid.UUID) -> dict[str, Regelwahl]:
    """Der Regelsatz eines Staffelleiters: nur, was er abweichend hat."""
    ergebnis = await sitzung.execute(select(Regelwahl).where(Regelwahl.benutzer_id == benutzer_id))
    return {w.regel: w for w in ergebnis.scalars()}


async def regelwahl_setzen(
    sitzung: AsyncSession,
    benutzer_id: uuid.UUID,
    regel: Regel,
    aktiv: bool | None,
    werte: dict[str, int | str] | None,
) -> Regelwahl:
    """Schalter und Werte eines Staffelleiters an einer Regel.

    `aktiv=None` und `werte=None` lassen stehen, was war. Ob eine Wahl der
    Vorgabe entspricht, hat `dienst.eigene_wahl` vorher entschieden.
    """
    wahl = (await regelwahlen(sitzung, benutzer_id)).get(regel.schluessel)
    if wahl is None:
        wahl = Regelwahl(benutzer_id=benutzer_id, regel=regel.schluessel, aktiv=None, werte={})
        sitzung.add(wahl)
    if aktiv is not None:
        wahl.aktiv = dienst.eigene_wahl(regel.aktiv, aktiv)
    if werte is not None:
        wahl.werte = werte
    await sitzung.flush()
    return wahl


async def regeltext_setzen(
    sitzung: AsyncSession, konto: uuid.UUID, schluessel: str, daten: RegelAendern
) -> Kontotext | None:
    """Die eigenen Saetze zu einer Regel -- jeder fuer sich.

    Was nicht mitgeschickt wurde, bleibt, wie es war. Sonst loeschte ein
    Umschalten die Saetze, die jemand vorher geschrieben hat.
    """
    text = (await kontotexte(sitzung, konto)).get(schluessel)
    if daten.sachverhalt is not None or daten.hinweis is not None:
        if text is None:
            text = Kontotext(benutzer_id=konto, schluessel=schluessel)
            sitzung.add(text)
        if daten.sachverhalt is not None:
            text.sachverhalt = daten.sachverhalt.strip()
        if daten.hinweis is not None:
            text.hinweis = daten.hinweis.strip()
    await sitzung.flush()
    return text


async def kontotexte(sitzung: AsyncSession, konto: uuid.UUID) -> dict[str, Kontotext]:
    """Die eigenen Saetze eines Staffelleiters, alle auf einmal.

    Keine sind der Normalfall: dann gelten die mitgelieferten. Alle auf einmal
    fuer die Liste: vierzig Regeln einzeln nachzuschlagen waeren vierzig
    Abfragen, und das faellt erst auf dem Pi auf.
    """
    ergebnis = await sitzung.execute(select(Kontotext).where(Kontotext.benutzer_id == konto))
    return {t.schluessel: t for t in ergebnis.scalars()}


async def anzeigename(sitzung: AsyncSession, konto: uuid.UUID) -> str:
    ergebnis = await sitzung.execute(select(Benutzer.anzeigename).where(Benutzer.id == konto))
    return ergebnis.scalar_one_or_none() or ""


# ── Alle Befunde auf einmal ───────────────────────────────────────────────


async def alle_befunde(
    sitzung: AsyncSession,
    konto: Konto,
    staffel_id: uuid.UUID | None = None,
    nur_offen: bool = False,
) -> list[tuple[Befund, Spielbericht]]:
    """Jeder Befund mit seinem Spiel, in einer Abfrage.

    Der Verbund und nicht zwei Runden: die Spiele einzeln nachzuladen waere
    bei dreihundert Befunden dreihundert Abfragen -- und das faellt erst auf
    dem Pi auf.
    """
    frage = (
        select(Befund, Spielbericht)
        .join(Spielbericht, Befund.spiel_id == Spielbericht.id)
        .where(_in_meinen(Spielbericht.staffel_id, konto))
        .order_by(Spielbericht.datum.desc(), Spielbericht.heim, Befund.rang)
    )
    if staffel_id is not None:
        frage = frage.where(Spielbericht.staffel_id == staffel_id)
    if nur_offen:
        frage = frage.where(Befund.entscheidung == "offen")
    ergebnis = await sitzung.execute(frage)
    return [(b, s) for b, s in ergebnis.all()]


# ── Auftraege ─────────────────────────────────────────────────────────────


def _auftraege(konto: Konto) -> Select[tuple[Auftrag]]:
    """Auftraege dieses Kontos. Ein Auftrag ohne Anforderer gehoert niemandem
    -- auch der Pruefdienst kann ihn nicht ausfuehren, denn mit wessen Zugang?"""
    return (
        select(Auftrag)
        .join(Auftraggeber, Auftraggeber.auftrag_id == Auftrag.id)
        .where(_von_mir(Auftraggeber.benutzer_id, konto))
    )


async def auftraege(sitzung: AsyncSession, konto: Konto, grenze: int = 50) -> list[Auftrag]:
    """Die juengsten zuerst -- das ist der, nach dem gerade gefragt wird."""
    ergebnis = await sitzung.execute(
        _auftraege(konto).order_by(Auftrag.angelegt.desc()).limit(grenze)
    )
    return list(ergebnis.scalars())


async def auftrag(sitzung: AsyncSession, konto: Konto, auftrag_id: uuid.UUID) -> Auftrag:
    ergebnis = await sitzung.execute(_auftraege(konto).where(Auftrag.id == auftrag_id))
    gefunden = ergebnis.scalar_one_or_none()
    if gefunden is None:
        raise AuftragUnbekannt(f"Es gibt keinen Auftrag mit der Kennung {auftrag_id}")
    return gefunden


async def offener_auftrag(sitzung: AsyncSession, konto: Konto) -> Auftrag | None:
    """Der eine, der gerade laeuft oder wartet -- oder keiner.

    Fuer den Pruefdienst der aelteste von allen.
    """
    ergebnis = await sitzung.execute(
        _auftraege(konto)
        .where(Auftrag.zustand.in_(dienst.OFFENE_ZUSTAENDE))
        .order_by(Auftrag.angelegt)
        .limit(1)
    )
    return ergebnis.scalar_one_or_none()


async def auftraggeber(sitzung: AsyncSession, auftrag_id: uuid.UUID) -> uuid.UUID:
    ergebnis = await sitzung.execute(
        select(Auftraggeber.benutzer_id).where(Auftraggeber.auftrag_id == auftrag_id)
    )
    return ergebnis.scalar_one()


async def auftraege_davor(sitzung: AsyncSession, auftrag: Auftrag) -> int:
    """Wie viele offene Auftraege vor diesem drankommen."""
    davor = (
        _auftraege(None)
        .where(Auftrag.zustand.in_(dienst.OFFENE_ZUSTAENDE), Auftrag.angelegt < auftrag.angelegt)
        .subquery()
    )
    ergebnis = await sitzung.execute(select(func.count()).select_from(davor))
    return int(ergebnis.scalar_one())


async def auftrag_anfordern(
    sitzung: AsyncSession,
    konto: uuid.UUID,
    art: str,
    staffel_id: uuid.UUID | None,
    referenz: str = "",
) -> Auftrag:
    if staffel_id is not None:
        await staffel(sitzung, konto, staffel_id)
    neuer = Auftrag(art=art, staffel_id=staffel_id, referenz=referenz)
    sitzung.add(neuer)
    await sitzung.flush()
    sitzung.add(Auftraggeber(auftrag_id=neuer.id, benutzer_id=konto))
    await sitzung.flush()
    await sitzung.refresh(neuer)
    return neuer


async def auftrag_fortschreiben(
    sitzung: AsyncSession, konto: Konto, auftrag_id: uuid.UUID, daten: Fortschritt
) -> Auftrag:
    """Was der Pruefdienst meldet, waehrend er laeuft.

    Die erste Meldung setzt ihn auf `laeuft`: dass er sich meldet, **ist** der
    Beleg dafuer, dass er angefangen hat. Ein eigener Startaufruf waere eine
    zweite Stelle, an der derselbe Umstand steht.
    """
    gefunden = await auftrag(sitzung, konto, auftrag_id)
    dienst.darf_fortschreiben(gefunden.zustand)
    if gefunden.zustand == "angefordert":
        gefunden.zustand = dienst.auftrag_weiter(gefunden.zustand, "laeuft")
        gefunden.gestartet_am = dt.datetime.now(dt.UTC)

    if daten.schritt is not None:
        gefunden.schritt = daten.schritt
    if daten.fortschritt is not None:
        gefunden.fortschritt = dienst.fortschritt_pruefen(daten.fortschritt)
    if daten.gepruefte is not None:
        gefunden.gepruefte = daten.gepruefte
    if daten.befunde is not None:
        gefunden.befunde = daten.befunde
    if daten.zeile:
        # Eine neue Liste und nicht append: eine JSONB-Spalte merkt sich eine
        # Aenderung in der Liste nicht, die SQLAlchemy nicht gesehen hat.
        jetzt = dt.datetime.now(dt.UTC).isoformat(timespec="seconds")
        gefunden.protokoll = [*gefunden.protokoll, {"zeit": jetzt, "text": daten.zeile}]
    await sitzung.flush()
    return gefunden


async def auftrag_abschliessen(
    sitzung: AsyncSession, konto: Konto, auftrag_id: uuid.UUID, daten: Abschluss
) -> Auftrag:
    gefunden = await auftrag(sitzung, konto, auftrag_id)
    gefunden.zustand = dienst.auftrag_weiter(gefunden.zustand, daten.zustand)
    gefunden.beendet_am = dt.datetime.now(dt.UTC)
    if daten.meldung:
        gefunden.meldung = daten.meldung
    if daten.zustand == "fertig":
        gefunden.fortschritt = 100
    await sitzung.flush()
    return gefunden


# ── Uebertragung nach DFBnet ──────────────────────────────────────────────


def _uebertragungen(konto: Konto) -> Select[tuple[Uebertragung]]:
    """Was zu Spielen der eigenen Staffeln vorgemerkt ist."""
    return (
        select(Uebertragung)
        .join(Spielbericht, Spielbericht.id == Uebertragung.spiel_id)
        .join(Staffelkonto, Staffelkonto.staffel_id == Spielbericht.staffel_id)
        .where(_von_mir(Staffelkonto.benutzer_id, konto))
    )


async def uebertragungen(sitzung: AsyncSession, konto: Konto) -> list[Uebertragung]:
    ergebnis = await sitzung.execute(_uebertragungen(konto).order_by(Uebertragung.angelegt.desc()))
    return list(ergebnis.scalars())


async def uebertragung(
    sitzung: AsyncSession, konto: Konto, uebertragung_id: uuid.UUID
) -> Uebertragung:
    ergebnis = await sitzung.execute(
        _uebertragungen(konto).where(Uebertragung.id == uebertragung_id)
    )
    gefunden = ergebnis.scalar_one_or_none()
    if gefunden is None:
        raise UebertragungUnbekannt(f"Es gibt keine Uebertragung mit der Kennung {uebertragung_id}")
    return gefunden


async def uebertragungskonto(sitzung: AsyncSession, uebertragung_id: uuid.UUID) -> uuid.UUID:
    """Mit wessen Zugang sie hinausgeht: dem dessen, dem die Staffel gehoert."""
    ergebnis = await sitzung.execute(
        select(Staffelkonto.benutzer_id)
        .join(Spielbericht, Spielbericht.staffel_id == Staffelkonto.staffel_id)
        .join(Uebertragung, Uebertragung.spiel_id == Spielbericht.id)
        .where(Uebertragung.id == uebertragung_id)
    )
    return ergebnis.scalar_one()


async def uebertragung_stand(sitzung: AsyncSession, konto: Konto) -> dict[str, int]:
    """Die Zahlen je Zustand, in einer Abfrage."""
    meine = _uebertragungen(konto).subquery()
    ergebnis = await sitzung.execute(
        select(meine.c.zustand, func.count()).group_by(meine.c.zustand)
    )
    gezaehlt = {zustand: int(anzahl) for zustand, anzahl in ergebnis.all()}
    return {z: gezaehlt.get(z, 0) for z in ("offen", "laeuft", "fertig", "fehler")}


async def freigegeben_offen(sitzung: AsyncSession) -> int:
    """Wie viele offene hinaus duerfen -- die Zahl fuer den Pruefdienst."""
    darf = await freigegebene_konten(sitzung)
    offene = (
        _uebertragungen(None)
        .where(Uebertragung.zustand == "offen", Staffelkonto.benutzer_id.in_(darf))
        .subquery()
    )
    ergebnis = await sitzung.execute(select(func.count()).select_from(offene))
    return int(ergebnis.scalar_one())


async def uebertragung_einreihen(
    sitzung: AsyncSession, aktion: str, referenz: uuid.UUID, spiel_id: uuid.UUID
) -> Uebertragung:
    """Idempotent ueber (aktion, referenz).

    Eine gescheiterte Zeile wird dabei zurueckgesetzt: das zweite Abhaken ist
    der Staffelleiter, der es noch einmal versucht.

    Das Spiel gehoert dazu: an ihm haengt, mit wessen Zugang sie hinausgeht.
    """
    ergebnis = await sitzung.execute(
        select(Uebertragung).where(
            Uebertragung.aktion == aktion, Uebertragung.referenz == str(referenz)
        )
    )
    vorhanden = ergebnis.scalar_one_or_none()
    if vorhanden is not None:
        if vorhanden.zustand == "fehler":
            vorhanden.zustand = "offen"
            vorhanden.letzter_fehler = ""
        await sitzung.flush()
        return vorhanden

    neue = Uebertragung(aktion=aktion, referenz=str(referenz), spiel_id=spiel_id)
    sitzung.add(neue)
    await sitzung.flush()
    await sitzung.refresh(neue)
    return neue


async def uebertragung_wiederholen(
    sitzung: AsyncSession, konto: Konto, uebertragung_id: uuid.UUID | None
) -> int:
    """Gescheitertes zurueck in die Schlange. Gibt zurueck, wie viele.

    Ohne Kennung alle -- nach einem Netzausfall stehen dort zwanzig Zeilen mit
    demselben Fehler, und die einzeln anzuklicken ist keine Arbeit, sondern
    eine Strafe.
    """
    if uebertragung_id is not None:
        gefunden = await uebertragung(sitzung, konto, uebertragung_id)
        dienst.darf_wiederholt_werden(gefunden.zustand)
        gefunden.zustand = "offen"
        gefunden.letzter_fehler = ""
        await sitzung.flush()
        return 1

    ergebnis = await sitzung.execute(_uebertragungen(konto).where(Uebertragung.zustand == "fehler"))
    betroffen = list(ergebnis.scalars())
    for zeile in betroffen:
        zeile.zustand = "offen"
        zeile.letzter_fehler = ""
    await sitzung.flush()
    return len(betroffen)


async def uebertragung_uebernehmen(sitzung: AsyncSession, konto: Konto) -> Uebertragung | None:
    """Die naechste offene Zeile - und sie gehoert dann dem Aufrufer.

    Uebernehmen und nicht nur lesen: sonst greifen zwei Dienste nach derselben
    Zeile und tragen dieselbe Freigabe zweimal in DFBnet ein. `FOR UPDATE SKIP
    LOCKED` laesst den zweiten die naechste nehmen, statt zu warten.

    Nur Zeilen von Konten, die ihre Uebertragung freigegeben haben.
    """
    darf = await freigegebene_konten(sitzung)
    ergebnis = await sitzung.execute(
        _uebertragungen(konto)
        .where(Uebertragung.zustand == "offen", Staffelkonto.benutzer_id.in_(darf))
        .order_by(Uebertragung.angelegt)
        .limit(1)
        .with_for_update(of=Uebertragung, skip_locked=True)
    )
    gefunden = ergebnis.scalar_one_or_none()
    if gefunden is None:
        return None
    gefunden.zustand = dienst.uebertragung_weiter(gefunden.zustand, "laeuft")
    await sitzung.flush()
    return gefunden


async def uebertragung_abschliessen(
    sitzung: AsyncSession,
    konto: Konto,
    uebertragung_id: uuid.UUID,
    daten: UebertragungAbschluss,
) -> Uebertragung:
    gefunden = await uebertragung(sitzung, konto, uebertragung_id)
    gefunden.zustand = dienst.uebertragung_weiter(gefunden.zustand, daten.zustand)
    gefunden.versuche += 1
    gefunden.letzter_fehler = daten.meldung if daten.zustand == "fehler" else ""
    gefunden.erledigt_am = dt.datetime.now(dt.UTC) if daten.zustand == "fertig" else None

    # Die Nummer, die DFBnet dem Fall gegeben hat, gehoert an den Vorgang und
    # nicht in eine Meldungszeile: aus ihr entsteht die Mail an den
    # Sportrichter, und eine Zeile im Protokoll laesst sich nicht abschicken.
    if daten.aktenzeichen and gefunden.aktion == "fallanlage":
        ziel = await sitzung.get(Vorgang, uuid.UUID(gefunden.referenz))
        if ziel is not None:
            ziel.dfbnet_aktenzeichen = daten.aktenzeichen

    await sitzung.flush()
    return gefunden


# ── DFBnet-Zugang ─────────────────────────────────────────────────────────


async def _zugang(sitzung: AsyncSession, konto: uuid.UUID) -> Kontozugang | None:
    ergebnis = await sitzung.execute(select(Kontozugang).where(Kontozugang.benutzer_id == konto))
    return ergebnis.scalar_one_or_none()


def schluessel_vorhanden() -> bool:
    return bool(os.environ.get(dienst.SCHLUESSEL_VARIABLE, "").strip())


def dienstkonto() -> str:
    """Welches Konto der Pruefdienst ist. Leer: keines."""
    return os.environ.get(dienst.DIENSTKONTO_VARIABLE, "")


async def zugang_stand(sitzung: AsyncSession, konto: uuid.UUID) -> tuple[bool, str]:
    """Ob etwas hinterlegt ist und fuer wen. Nie das Passwort."""
    gefunden = await _zugang(sitzung, konto)
    return (gefunden is not None, gefunden.benutzer if gefunden else "")


async def zugang_setzen(sitzung: AsyncSession, konto: uuid.UUID, daten: ZugangSetzen) -> None:
    schluessel = dienst.schluessel_aus(os.environ)
    token = dienst.verschluesseln(daten.passwort, schluessel)
    gefunden = await _zugang(sitzung, konto)
    if gefunden is None:
        sitzung.add(Kontozugang(benutzer_id=konto, benutzer=daten.benutzer, geheimnis=token))
    else:
        gefunden.benutzer = daten.benutzer
        gefunden.geheimnis = token
    await sitzung.flush()


async def zugang_loeschen(sitzung: AsyncSession, konto: uuid.UUID) -> None:
    gefunden = await _zugang(sitzung, konto)
    if gefunden is not None:
        await sitzung.delete(gefunden)
        await sitzung.flush()


async def zugang_abholen(sitzung: AsyncSession, konto: uuid.UUID) -> tuple[str, str]:
    """Der einzige Ort, an dem das Passwort wieder herauskommt."""
    gefunden = await _zugang(sitzung, konto)
    if gefunden is None:
        raise KeinZugang("Es ist kein DFBnet-Zugang hinterlegt")
    schluessel = dienst.schluessel_aus(os.environ)
    return gefunden.benutzer, dienst.entschluesseln(gefunden.geheimnis, schluessel)
