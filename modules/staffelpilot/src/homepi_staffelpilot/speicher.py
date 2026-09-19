"""Datenbankzugriff. Hier faellt I/O an, hier stehen keine Entscheidungen."""

from __future__ import annotations

import datetime as dt
import os
import uuid

from sqlalchemy import delete, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from . import dienst
from .dienst import (
    AuftragUnbekannt,
    BefundUnbekannt,
    KeinZugang,
    RegelUnbekannt,
    SpielUnbekannt,
    StaffelUnbekannt,
    StaffelVergeben,
    UebertragungUnbekannt,
    VorgangUnbekannt,
    VorgangVergeben,
)
from .modelle import (
    Auftrag,
    Befund,
    Einstellung,
    Mannschaft,
    Regel,
    Spielbericht,
    Staffel,
    Uebertragung,
    Vorgang,
    Zugang,
)
from .schemas import (
    Abschluss,
    EinstellungenSetzen,
    Fortschritt,
    ImportAuftrag,
    MannschaftEingang,
    RegelEingang,
    StaffelAendern,
    StaffelAnlegen,
    UebertragungAbschluss,
    UebertragungEinreihen,
    VorgangAnlegen,
    ZugangSetzen,
)

# ── Staffeln ──────────────────────────────────────────────────────────────


async def staffeln(sitzung: AsyncSession) -> list[Staffel]:
    ergebnis = await sitzung.execute(select(Staffel).order_by(Staffel.name))
    return list(ergebnis.scalars())


async def staffel(sitzung: AsyncSession, staffel_id: uuid.UUID) -> Staffel:
    gefunden = await sitzung.get(Staffel, staffel_id)
    if gefunden is None:
        raise StaffelUnbekannt(f"Es gibt keine Staffel mit der Kennung {staffel_id}")
    return gefunden


async def staffel_anlegen(sitzung: AsyncSession, daten: StaffelAnlegen) -> Staffel:
    neue = Staffel(**daten.model_dump())
    sitzung.add(neue)
    try:
        await sitzung.flush()
    except IntegrityError as fehler:
        await sitzung.rollback()
        # Die Datenbank ist die einzige Stelle, die das zuverlaessig weiss.
        raise StaffelVergeben(f"Eine Staffel namens '{daten.name}' gibt es bereits") from fehler
    await sitzung.refresh(neue)
    return neue


async def staffel_aendern(
    sitzung: AsyncSession, staffel_id: uuid.UUID, daten: StaffelAendern
) -> Staffel:
    """Nur die mitgeschickten Felder. Ausgelassene bleiben stehen."""
    gefunden = await staffel(sitzung, staffel_id)
    felder = daten.model_dump(exclude_none=True)
    for name, wert in felder.items():
        setattr(gefunden, name, wert)
    try:
        await sitzung.flush()
    except IntegrityError as fehler:
        await sitzung.rollback()
        raise StaffelVergeben(
            f"Eine Staffel namens '{felder.get('name')}' gibt es bereits"
        ) from fehler
    return gefunden


async def staffel_loeschen(sitzung: AsyncSession, staffel_id: uuid.UUID) -> None:
    await sitzung.delete(await staffel(sitzung, staffel_id))


async def anzahl_aktiver_staffeln(sitzung: AsyncSession) -> int:
    ergebnis = await sitzung.execute(
        select(func.count()).select_from(Staffel).where(Staffel.aktiv.is_(True))
    )
    return int(ergebnis.scalar_one())


# ── Spielberichte ─────────────────────────────────────────────────────────


async def spiele(sitzung: AsyncSession, staffel_id: uuid.UUID | None = None) -> list[Spielbericht]:
    """Immer mit Befunden.

    Der Aufrufer zaehlt sie -- ohne `selectinload` waere das ein Nachladen
    mitten in der Antwort, und unter async ist das ein `MissingGreenlet`.
    """
    frage = (
        select(Spielbericht)
        .options(selectinload(Spielbericht.befunde))
        .order_by(Spielbericht.datum.desc(), Spielbericht.heim)
    )
    if staffel_id is not None:
        frage = frage.where(Spielbericht.staffel_id == staffel_id)
    ergebnis = await sitzung.execute(frage)
    return list(ergebnis.scalars())


async def spiel(sitzung: AsyncSession, spiel_id: uuid.UUID) -> Spielbericht:
    ergebnis = await sitzung.execute(
        select(Spielbericht)
        .options(selectinload(Spielbericht.befunde))
        .where(Spielbericht.id == spiel_id)
    )
    gefunden = ergebnis.scalar_one_or_none()
    if gefunden is None:
        raise SpielUnbekannt(f"Es gibt keinen Spielbericht mit der Kennung {spiel_id}")
    return gefunden


async def befund(sitzung: AsyncSession, befund_id: uuid.UUID) -> Befund:
    gefunden = await sitzung.get(Befund, befund_id)
    if gefunden is None:
        raise BefundUnbekannt(f"Es gibt keinen Befund mit der Kennung {befund_id}")
    return gefunden


async def einspielen(sitzung: AsyncSession, auftrag: ImportAuftrag) -> tuple[int, int, int]:
    """Spielberichte anlegen oder auffrischen. Gibt (angelegt, aktualisiert,
    Befunde) zurueck.

    Ein erneuter Import desselben Spiels ersetzt seine Befunde vollstaendig -
    ein Prueflauf ist die vollstaendige Aussage ueber einen Bericht, nicht ein
    Nachtrag. Getroffene Entscheidungen zu bereits bekannten Befunden bleiben
    dabei erhalten; sie an derselben Regel und derselben Person wiederzufinden
    ist das, was den zweiten Prueflauf ertraeglich macht.
    """
    await staffel(sitzung, auftrag.staffel_id)
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
            )
            sitzung.add(bericht)
            await sitzung.flush()
            angelegt += 1
        else:
            bericht.datum = eingang.datum
            bericht.heim = eingang.heim
            bericht.gast = eingang.gast
            bericht.ergebnis = eingang.ergebnis
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
                    rang=rang,
                    entscheidung=alt.entscheidung if alt else "offen",
                    grund=alt.grund if alt else "",
                    entschieden_am=alt.entschieden_am if alt else None,
                )
            )
            befunde_gesamt += 1
        await sitzung.flush()
        # Die Beziehung haelt sonst den Stand von vor dem Loeschen.
        await sitzung.refresh(bericht, ["befunde"])

    return angelegt, aktualisiert, befunde_gesamt


async def entscheidung_setzen(
    sitzung: AsyncSession, befund_id: uuid.UUID, art: str, grund: str
) -> Befund:
    gefunden = await befund(sitzung, befund_id)
    gefunden.entscheidung = art
    gefunden.grund = grund
    gefunden.entschieden_am = dt.datetime.now(dt.UTC)
    await sitzung.flush()
    return gefunden


async def entscheidung_zuruecknehmen(sitzung: AsyncSession, befund_id: uuid.UUID) -> Befund:
    """Der Befund ist wieder offen - und das Spiel damit nicht mehr abgehakt.

    Den Haken stehen zu lassen waere die eine Zusage dieses Artefakts
    gebrochen: abgehakt heisst, zu jedem Befund liegt eine Entscheidung vor.
    """
    gefunden = await befund(sitzung, befund_id)
    gefunden.entscheidung = "offen"
    gefunden.grund = ""
    gefunden.entschieden_am = None
    bericht = await spiel(sitzung, gefunden.spiel_id)
    bericht.abgehakt = False
    bericht.abgehakt_am = None
    await sitzung.flush()
    return gefunden


async def haken_setzen(sitzung: AsyncSession, spiel_id: uuid.UUID, gesetzt: bool) -> Spielbericht:
    bericht = await spiel(sitzung, spiel_id)
    bericht.abgehakt = gesetzt
    bericht.abgehakt_am = dt.datetime.now(dt.UTC) if gesetzt else None
    await sitzung.flush()
    return bericht


# ── Einstellungen ─────────────────────────────────────────────────────────


async def einstellungen(sitzung: AsyncSession) -> dienst.Einstellungen:
    """Die geprueften Werte, nicht die rohen Zeilen.

    Die Pruefung steht in `dienst.einstellungen_aus` und damit an einer
    Stelle: sonst entscheidet jeder Aufrufer selbst, was eine leere
    Zeichenkette bedeutet.
    """
    ergebnis = await sitzung.execute(select(Einstellung))
    return dienst.einstellungen_aus({e.schluessel: e.wert for e in ergebnis.scalars()})


async def einstellungen_setzen(
    sitzung: AsyncSession, daten: EinstellungenSetzen
) -> dienst.Einstellungen:
    """Nur die mitgeschickten Felder. Ausgelassene bleiben stehen."""
    vorhanden = {e.schluessel: e for e in (await sitzung.execute(select(Einstellung))).scalars()}
    for schluessel, wert in daten.model_dump(exclude_none=True).items():
        if schluessel in vorhanden:
            vorhanden[schluessel].wert = str(wert)
        else:
            sitzung.add(Einstellung(schluessel=schluessel, wert=str(wert)))
    await sitzung.flush()
    return await einstellungen(sitzung)


# ── Mannschaften ──────────────────────────────────────────────────────────


async def mannschaften(sitzung: AsyncSession, staffel_id: uuid.UUID) -> list[Mannschaft]:
    await staffel(sitzung, staffel_id)
    ergebnis = await sitzung.execute(
        select(Mannschaft)
        .where(Mannschaft.staffel_id == staffel_id)
        .order_by(Mannschaft.verein, Mannschaft.nummer, Mannschaft.name)
    )
    return list(ergebnis.scalars())


async def mannschaften_setzen(
    sitzung: AsyncSession, staffel_id: uuid.UUID, eingang: list[MannschaftEingang]
) -> list[Mannschaft]:
    """Die Meldung als Ganzes, nicht als Aenderung.

    Was DFBnet nicht mehr meldet, ist zurueckgezogen. Bestaetigte Zuordnungen
    ueberleben trotzdem: sie an eine Kennung zu binden, die mit der Meldung
    verschwindet, hiesse, jede Handkorrektur beim naechsten Einspielen
    wegzuwerfen -- und genau das ist der Fehler, vor dem die Zuordnung
    schuetzen soll. Der Name traegt sie hinueber.
    """
    alt = {m.name: m for m in await mannschaften(sitzung, staffel_id)}
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
    return await mannschaften(sitzung, staffel_id)


# ── Vorgaenge ─────────────────────────────────────────────────────────────


async def vorgaenge(sitzung: AsyncSession, zustand: str | None = None) -> list[Vorgang]:
    frage = select(Vorgang).order_by(Vorgang.aktenzeichen.desc())
    if zustand is not None:
        frage = frage.where(Vorgang.zustand == zustand)
    ergebnis = await sitzung.execute(frage)
    return list(ergebnis.scalars())


async def vorgang(sitzung: AsyncSession, vorgang_id: uuid.UUID) -> Vorgang:
    gefunden = await sitzung.get(Vorgang, vorgang_id)
    if gefunden is None:
        raise VorgangUnbekannt(f"Es gibt keinen Vorgang mit der Kennung {vorgang_id}")
    return gefunden


async def vorgang_zu_befund(sitzung: AsyncSession, befund_id: uuid.UUID) -> Vorgang | None:
    ergebnis = await sitzung.execute(select(Vorgang).where(Vorgang.befund_id == befund_id))
    return ergebnis.scalar_one_or_none()


async def anzahl_entwuerfe(sitzung: AsyncSession) -> int:
    ergebnis = await sitzung.execute(
        select(func.count()).select_from(Vorgang).where(Vorgang.zustand == "entwurf")
    )
    return int(ergebnis.scalar_one())


async def _naechstes_aktenzeichen(sitzung: AsyncSession, saison: str) -> str:
    """Fortlaufend je Saison.

    Gezaehlt wird, was schon vergeben ist, und nicht ein Zaehler in einer
    eigenen Zeile: ein geloeschter Vorgang darf keine Luecke lassen, die beim
    naechsten Anlegen zur Kollision wird. Die Eindeutigkeit steht ohnehin in
    der Datenbank -- zwei gleichzeitige Anlagen scheitern dort und nicht hier.
    """
    kern = saison.strip().replace("/", "-") or "ohne-saison"
    ergebnis = await sitzung.execute(
        select(func.count()).select_from(Vorgang).where(Vorgang.aktenzeichen.like(f"{kern}-%"))
    )
    return dienst.aktenzeichen(saison, int(ergebnis.scalar_one()) + 1)


async def vorgang_anlegen(
    sitzung: AsyncSession, befund_id: uuid.UUID, daten: VorgangAnlegen
) -> Vorgang:
    """Aus einem Befund einen Entwurf machen.

    Der Text entsteht hier einmal und wird danach nicht wieder erzeugt: ein
    spaeteres Neuerzeugen wuerde eine Formulierung ueberschreiben, die sich
    jemand ueberlegt hat.

    Dass es zu einem Befund nur einen Vorgang gibt, sichert die Datenbank und
    nicht eine Abfrage davor: die waere ein Rennen zwischen zwei gleichzeitigen
    Anlagen und zugleich eine zweite Stelle, an der dieselbe Regel steht.
    """
    gefunden = await befund(sitzung, befund_id)
    art = dienst.art_aus_weg(gefunden.weg)
    bericht = await spiel(sitzung, gefunden.spiel_id)
    staffel_dazu = await staffel(sitzung, bericht.staffel_id)
    werte = await einstellungen(sitzung)

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
    )
    schreiben = dienst.vorgang_entwurf(art, anlass, werte, dt.date.today())

    neuer = Vorgang(
        befund_id=befund_id,
        art=art,
        aktenzeichen=await _naechstes_aktenzeichen(sitzung, staffel_dazu.saison),
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
    sitzung: AsyncSession, vorgang_id: uuid.UUID, felder: dict[str, str]
) -> Vorgang:
    gefunden = await vorgang(sitzung, vorgang_id)
    for name, wert in felder.items():
        setattr(gefunden, name, wert)
    await sitzung.flush()
    return gefunden


async def vorgang_zustand(sitzung: AsyncSession, vorgang_id: uuid.UUID, neu: str) -> Vorgang:
    gefunden = await vorgang(sitzung, vorgang_id)
    gefunden.zustand = dienst.zustand_weiter(gefunden.zustand, neu)
    # Nur beim ersten Mal. Wer ein Schreiben zurueckholt und erneut abschickt,
    # hat es trotzdem an dem Tag versandt, an dem es beim Verein ankam.
    if neu == "versandt" and gefunden.versandt_am is None:
        gefunden.versandt_am = dt.datetime.now(dt.UTC)
    await sitzung.flush()
    return gefunden


async def vorgang_loeschen(sitzung: AsyncSession, vorgang_id: uuid.UUID) -> None:
    await sitzung.delete(await vorgang(sitzung, vorgang_id))


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
    """
    vorher = {r.schluessel: r.aktiv for r in await regeln(sitzung)}
    gemeldet = {r.schluessel for r in eingang}

    await sitzung.execute(delete(Regel).where(Regel.schluessel.notin_(gemeldet or {""})))
    vorhanden = {r.schluessel: r for r in await regeln(sitzung)}

    for r in eingang:
        ziel = vorhanden.get(r.schluessel)
        if ziel is None:
            sitzung.add(Regel(**r.model_dump(), aktiv=vorher.get(r.schluessel, True)))
        else:
            ziel.name, ziel.beschreibung = r.name, r.beschreibung
            ziel.schwere, ziel.weg = r.schwere, r.weg
    await sitzung.flush()
    return await regeln(sitzung)


async def regel_umschalten(sitzung: AsyncSession, regel_id: uuid.UUID, aktiv: bool) -> Regel:
    gefunden = await regel(sitzung, regel_id)
    gefunden.aktiv = aktiv
    await sitzung.flush()
    return gefunden


# ── Alle Befunde auf einmal ───────────────────────────────────────────────


async def alle_befunde(
    sitzung: AsyncSession,
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
        .order_by(Spielbericht.datum.desc(), Spielbericht.heim, Befund.rang)
    )
    if staffel_id is not None:
        frage = frage.where(Spielbericht.staffel_id == staffel_id)
    if nur_offen:
        frage = frage.where(Befund.entscheidung == "offen")
    ergebnis = await sitzung.execute(frage)
    return [(b, s) for b, s in ergebnis.all()]


# ── Auftraege ─────────────────────────────────────────────────────────────


async def auftraege(sitzung: AsyncSession, grenze: int = 50) -> list[Auftrag]:
    """Die juengsten zuerst -- das ist der, nach dem gerade gefragt wird."""
    ergebnis = await sitzung.execute(
        select(Auftrag).order_by(Auftrag.angelegt.desc()).limit(grenze)
    )
    return list(ergebnis.scalars())


async def auftrag(sitzung: AsyncSession, auftrag_id: uuid.UUID) -> Auftrag:
    gefunden = await sitzung.get(Auftrag, auftrag_id)
    if gefunden is None:
        raise AuftragUnbekannt(f"Es gibt keinen Auftrag mit der Kennung {auftrag_id}")
    return gefunden


async def offener_auftrag(sitzung: AsyncSession) -> Auftrag | None:
    """Der eine, der gerade laeuft oder wartet -- oder keiner."""
    ergebnis = await sitzung.execute(
        select(Auftrag)
        .where(Auftrag.zustand.in_(dienst.OFFENE_ZUSTAENDE))
        .order_by(Auftrag.angelegt)
        .limit(1)
    )
    return ergebnis.scalar_one_or_none()


async def auftrag_anfordern(
    sitzung: AsyncSession, art: str, staffel_id: uuid.UUID | None
) -> Auftrag:
    if staffel_id is not None:
        await staffel(sitzung, staffel_id)
    neuer = Auftrag(art=art, staffel_id=staffel_id)
    sitzung.add(neuer)
    await sitzung.flush()
    await sitzung.refresh(neuer)
    return neuer


async def auftrag_fortschreiben(
    sitzung: AsyncSession, auftrag_id: uuid.UUID, daten: Fortschritt
) -> Auftrag:
    """Was der Pruefdienst meldet, waehrend er laeuft.

    Die erste Meldung setzt ihn auf `laeuft`: dass er sich meldet, **ist** der
    Beleg dafuer, dass er angefangen hat. Ein eigener Startaufruf waere eine
    zweite Stelle, an der derselbe Umstand steht.
    """
    gefunden = await auftrag(sitzung, auftrag_id)
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
    sitzung: AsyncSession, auftrag_id: uuid.UUID, daten: Abschluss
) -> Auftrag:
    gefunden = await auftrag(sitzung, auftrag_id)
    gefunden.zustand = dienst.auftrag_weiter(gefunden.zustand, daten.zustand)
    gefunden.beendet_am = dt.datetime.now(dt.UTC)
    if daten.meldung:
        gefunden.meldung = daten.meldung
    if daten.zustand == "fertig":
        gefunden.fortschritt = 100
    await sitzung.flush()
    return gefunden


# ── Uebertragung nach DFBnet ──────────────────────────────────────────────


async def uebertragungen(sitzung: AsyncSession) -> list[Uebertragung]:
    ergebnis = await sitzung.execute(select(Uebertragung).order_by(Uebertragung.angelegt.desc()))
    return list(ergebnis.scalars())


async def uebertragung(sitzung: AsyncSession, uebertragung_id: uuid.UUID) -> Uebertragung:
    gefunden = await sitzung.get(Uebertragung, uebertragung_id)
    if gefunden is None:
        raise UebertragungUnbekannt(f"Es gibt keine Uebertragung mit der Kennung {uebertragung_id}")
    return gefunden


async def uebertragung_stand(sitzung: AsyncSession) -> dict[str, int]:
    """Die Zahlen je Zustand, in einer Abfrage."""
    ergebnis = await sitzung.execute(
        select(Uebertragung.zustand, func.count()).group_by(Uebertragung.zustand)
    )
    gezaehlt = {zustand: int(anzahl) for zustand, anzahl in ergebnis.all()}
    return {z: gezaehlt.get(z, 0) for z in ("offen", "laeuft", "fertig", "fehler")}


async def uebertragung_einreihen(
    sitzung: AsyncSession, daten: UebertragungEinreihen
) -> Uebertragung:
    """Idempotent ueber (aktion, referenz).

    Eine gescheiterte Zeile wird dabei zurueckgesetzt: das zweite Abhaken ist
    der Staffelleiter, der es noch einmal versucht.
    """
    ergebnis = await sitzung.execute(
        select(Uebertragung).where(
            Uebertragung.aktion == daten.aktion, Uebertragung.referenz == daten.referenz
        )
    )
    vorhanden = ergebnis.scalar_one_or_none()
    if vorhanden is not None:
        if vorhanden.zustand == "fehler":
            vorhanden.zustand = "offen"
            vorhanden.letzter_fehler = ""
        await sitzung.flush()
        return vorhanden

    neue = Uebertragung(aktion=daten.aktion, referenz=daten.referenz, spiel_id=daten.spiel_id)
    sitzung.add(neue)
    await sitzung.flush()
    await sitzung.refresh(neue)
    return neue


async def uebertragung_wiederholen(sitzung: AsyncSession, uebertragung_id: uuid.UUID | None) -> int:
    """Gescheitertes zurueck in die Schlange. Gibt zurueck, wie viele.

    Ohne Kennung alle -- nach einem Netzausfall stehen dort zwanzig Zeilen mit
    demselben Fehler, und die einzeln anzuklicken ist keine Arbeit, sondern
    eine Strafe.
    """
    if uebertragung_id is not None:
        gefunden = await uebertragung(sitzung, uebertragung_id)
        dienst.darf_wiederholt_werden(gefunden.zustand)
        gefunden.zustand = "offen"
        gefunden.letzter_fehler = ""
        await sitzung.flush()
        return 1

    ergebnis = await sitzung.execute(select(Uebertragung).where(Uebertragung.zustand == "fehler"))
    betroffen = list(ergebnis.scalars())
    for zeile in betroffen:
        zeile.zustand = "offen"
        zeile.letzter_fehler = ""
    await sitzung.flush()
    return len(betroffen)


async def uebertragung_abschliessen(
    sitzung: AsyncSession, uebertragung_id: uuid.UUID, daten: UebertragungAbschluss
) -> Uebertragung:
    gefunden = await uebertragung(sitzung, uebertragung_id)
    gefunden.zustand = dienst.uebertragung_weiter(gefunden.zustand, daten.zustand)
    gefunden.versuche += 1
    gefunden.letzter_fehler = daten.meldung if daten.zustand == "fehler" else ""
    gefunden.erledigt_am = dt.datetime.now(dt.UTC) if daten.zustand == "fertig" else None
    await sitzung.flush()
    return gefunden


# ── DFBnet-Zugang ─────────────────────────────────────────────────────────

#: Es gibt genau einen je Installation.
DIENST = "dfbnet"


async def _zugang(sitzung: AsyncSession) -> Zugang | None:
    ergebnis = await sitzung.execute(select(Zugang).where(Zugang.dienst == DIENST))
    return ergebnis.scalar_one_or_none()


def schluessel_vorhanden() -> bool:
    return bool(os.environ.get(dienst.SCHLUESSEL_VARIABLE, "").strip())


async def zugang_stand(sitzung: AsyncSession) -> tuple[bool, str]:
    """Ob etwas hinterlegt ist und fuer wen. Nie das Passwort."""
    gefunden = await _zugang(sitzung)
    return (gefunden is not None, gefunden.benutzer if gefunden else "")


async def zugang_setzen(sitzung: AsyncSession, daten: ZugangSetzen) -> None:
    schluessel = dienst.schluessel_aus(os.environ)
    token = dienst.verschluesseln(daten.passwort, schluessel)
    gefunden = await _zugang(sitzung)
    if gefunden is None:
        sitzung.add(Zugang(dienst=DIENST, benutzer=daten.benutzer, geheimnis=token))
    else:
        gefunden.benutzer = daten.benutzer
        gefunden.geheimnis = token
    await sitzung.flush()


async def zugang_loeschen(sitzung: AsyncSession) -> None:
    gefunden = await _zugang(sitzung)
    if gefunden is not None:
        await sitzung.delete(gefunden)
        await sitzung.flush()


async def zugang_abholen(sitzung: AsyncSession) -> tuple[str, str]:
    """Der einzige Ort, an dem das Passwort wieder herauskommt."""
    gefunden = await _zugang(sitzung)
    if gefunden is None:
        raise KeinZugang("Es ist kein DFBnet-Zugang hinterlegt")
    schluessel = dienst.schluessel_aus(os.environ)
    return gefunden.benutzer, dienst.entschluesseln(gefunden.geheimnis, schluessel)
