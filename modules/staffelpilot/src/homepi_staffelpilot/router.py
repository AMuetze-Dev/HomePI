"""HTTP-Schicht. Uebersetzt zwischen Anfrage und Fachlichkeit, sonst nichts.

Zur Reihenfolge der Routen: alle Pfade hier beginnen mit einem festen Wort
(`staffeln`, `spiele`, `befunde`, `import`, `zusammenfassung`). Es gibt keine
Route `/{id}` auf oberster Ebene - genau die waere der Fall, in dem FastAPI
`zusammenfassung` als UUID zu lesen versucht und mit 422 antwortet.
"""

from __future__ import annotations

import datetime as dt
import uuid
from dataclasses import asdict
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request, Response, status
from homepi_core.auth import AktuellerBenutzer, Rolle, erfordert
from homepi_core.auth import speicher as auth_speicher
from homepi_core.auth.dienst import darf
from homepi_core.deps import DbSitzung

from . import dienst, mahnung, speicher, sportrichtermail, texte
from .dienst import (
    BefundSicht,
    Blick,
    Einstellungen,
    NochOffeneBefunde,
    SpielSicht,
    ansicht_pruefen,
    auswerten,
    betreff_fuer,
    darf_abgehakt_werden,
    darf_angefordert_werden,
    darf_zurueckgenommen_werden,
    einrichtung_schritt,
    entscheidung_pruefen,
    fall_pruefen,
    hoehere_vorschlaege,
    ist_faellig,
    konto_von,
    mannschaft_unsicher,
    mannschaftsart_fuer,
    sortiert,
    zusammenfassen,
)
from .modelle import (
    Auftrag,
    Befund,
    Kontotext,
    Mannschaft,
    Regel,
    Regeldatei,
    Regelparameter,
    Regelwahl,
    Spielbericht,
    Staffel,
    Uebertragung,
    Vorgang,
)
from .schemas import (
    Abschluss,
    Ansichten,
    AuftragAnfordern,
    AuftragAusgabe,
    AuftragZeile,
    Auswertung,
    BefundAusgabe,
    BefundZeile,
    Beispieldatenstand,
    Einrichtungsstand,
    EinstellungenAusgabe,
    EinstellungenSetzen,
    EntscheidungSetzen,
    Fortschritt,
    ImportAuftrag,
    ImportErgebnis,
    KarteAusgabe,
    MailEntwurf,
    MannschaftAusgabe,
    MannschaftenSetzen,
    ParameterAusgabe,
    Pause,
    Posten,
    RegelAendern,
    RegelAusgabe,
    RegeldateiAendern,
    RegeldateiAusgabe,
    RegeldateiInhalt,
    RegeldateiSetzen,
    RegelkatalogSetzen,
    RegelsatzAusgabe,
    SpielAusgabe,
    SpielZeile,
    StaffelAendern,
    StaffelAnlegen,
    StaffelAusgabe,
    StaffelnAusDfbnet,
    StaffelnUebernommen,
    UebertragungAbschluss,
    UebertragungAusgabe,
    UebertragungEinreihen,
    UebertragungStand,
    VorgangAendern,
    VorgangAnlegen,
    VorgangAusgabe,
    VorgangZeile,
    VorlagenStand,
    VorlagenUebergeben,
    ZugangGeheim,
    ZugangSetzen,
    ZugangStand,
    Zusammenfassung,
    ZustandSetzen,
)

router = APIRouter()

NUTZER = [erfordert("staffelpilot", Rolle.NUTZER)]
NUR_VERWALTER = [erfordert("staffelpilot", Rolle.VERWALTER)]


# ── Wer was sieht ─────────────────────────────────────────────────────────


async def _blick(
    benutzer: AktuellerBenutzer,
    konto: Annotated[
        uuid.UUID | None,
        Query(description="Für welches Konto. Nur für den Prüfdienst."),
    ] = None,
) -> Blick:
    """Mit wessen Augen diese Anfrage sieht.

    Hängt an **jeder** Route, die etwas liest oder schreibt, das jemandem
    gehört. Der Speicher verlangt das Konto als Pflichtangabe — eine Route, die
    es vergisst, scheitert am Typprüfer und nicht erst im Betrieb.
    """
    verwalter = darf(auth_speicher.rechte_von(benutzer), "staffelpilot", Rolle.VERWALTER)
    return dienst.blick_fuer(
        ich=benutzer.id,
        ist_dienst=dienst.ist_dienstkonto(
            benutzer.name, verwalter=verwalter, dienstkonto=speicher.dienstkonto()
        ),
        konto=konto,
    )


HierBlick = Annotated[Blick, Depends(_blick)]


async def _nur_pruefdienst(blick: HierBlick) -> None:
    if not blick.dienst:
        raise dienst.NurPruefdienst("Das darf nur das Konto des Prüfdienstes.")


NUR_PRUEFDIENST = [Depends(_nur_pruefdienst)]


def _sicht(befund: Befund) -> BefundSicht:
    return BefundSicht(
        schwere=befund.schwere,
        entscheidung=befund.entscheidung,
        regel=befund.regel,
        titel=befund.titel,
        schluessel=str(befund.id),
    )


def _befund(befund: Befund, vorgang_id: uuid.UUID | None) -> BefundAusgabe:
    return BefundAusgabe(
        id=befund.id,
        regel=befund.regel,
        schwere=befund.schwere,  # type: ignore[arg-type]
        titel=befund.titel,
        text=befund.text,
        person=befund.person,
        mannschaft=befund.mannschaft,
        entscheidung=befund.entscheidung,  # type: ignore[arg-type]
        grund=befund.grund,
        weg=befund.weg,  # type: ignore[arg-type]
        vorgang_id=vorgang_id,
    )


def _mannschaft(m: Mannschaft) -> MannschaftAusgabe:
    return MannschaftAusgabe(
        id=m.id,
        name=m.name,
        verein=m.verein,
        nummer=m.nummer,
        ist_sg=m.ist_sg,
        hoehere=list(m.hoehere),
        bestaetigt=m.bestaetigt,
        unsicher=mannschaft_unsicher(m.ist_sg, m.bestaetigt),
        vorschlaege=hoehere_vorschlaege(m.name, m.ist_sg),
    )


def _vorgang(v: Vorgang, spiel_id: uuid.UUID | None = None) -> VorgangAusgabe:
    """Die Ausgabe eines Vorgangs, mit dem Spiel dahinter, wenn es da ist.

    `spiel_id` kommt von aussen und nicht aus einer nachgeladenen Beziehung:
    die Route hat es meistens schon, und ein zweiter Abruf je Vorgang waere in
    einer Liste ein Abruf je Zeile.
    """
    ausgabe = VorgangAusgabe.model_validate(v)
    if spiel_id is not None:
        ausgabe = ausgabe.model_copy(update={"spiel_id": spiel_id})
    return ausgabe


# ── Warteschlange und Kachel ──────────────────────────────────────────────


@router.get("/", summary="Warteschlange der Spielberichte")
async def warteschlange(
    sitzung: DbSitzung,
    blick: HierBlick,
    staffel_id: Annotated[uuid.UUID | None, Query(description="Nur diese Staffel")] = None,
    nur_faellig: Annotated[bool, Query(description="Nur Spiele im Prüfzeitraum")] = False,
) -> list[SpielZeile]:
    """Die tägliche Liste.

    `faellig` steht an jeder Zeile und wird nicht gespeichert: der
    Prüfzeitraum verschiebt sich mit jedem Tag, und ein geschriebener Wert
    wäre am Morgen darauf falsch.
    """
    berichte = await speicher.spiele(sitzung, blick.konto, staffel_id)
    tage = (await speicher.einstellungen(sitzung, konto_von(blick))).pruefzeitraum_tage
    heute = dt.date.today()

    zeilen = [
        SpielZeile(
            id=b.id,
            dfbnet_id=b.dfbnet_id,
            datum=b.datum,
            heim=b.heim,
            gast=b.gast,
            ergebnis=b.ergebnis,
            abgehakt=b.abgehakt,
            offene_befunde=sum(1 for x in b.befunde if x.entscheidung == "offen"),
            kritische_befunde=sum(
                1 for x in b.befunde if x.schwere == "kritisch" and x.entscheidung == "offen"
            ),
            faellig=ist_faellig(b.datum, heute, tage),
        )
        for b in berichte
    ]
    return [z for z in zeilen if z.faellig] if nur_faellig else zeilen


@router.get("/zusammenfassung", summary="Überblick für die Kachel")
async def uebersicht(sitzung: DbSitzung, blick: HierBlick) -> Zusammenfassung:
    berichte = await speicher.spiele(sitzung, blick.konto)
    return zusammenfassen(
        (SpielSicht(abgehakt=b.abgehakt, befunde=[_sicht(x) for x in b.befunde]) for b in berichte),
        staffeln_aktiv=await speicher.anzahl_aktiver_staffeln(sitzung, blick.konto),
        vorgaenge_entwurf=await speicher.anzahl_entwuerfe(sitzung, blick.konto),
    )


@router.get("/ergebnisse", summary="Auswertung der Saison")
async def ergebnisse(
    sitzung: DbSitzung,
    blick: HierBlick,
    staffel_id: Annotated[uuid.UUID | None, Query(description="Nur diese Staffel")] = None,
) -> Auswertung:
    """Was aufgelaufen ist — gruppiert nach Schwere, Regel, Mannschaft, Monat.

    Gezählt wird in `dienst.auswerten` und nicht in SQL: vier
    `GROUP BY`-Abfragen wären dieselbe Entscheidung an vier Stellen, und keine
    davon ließe sich in Millisekunden prüfen.
    """
    paare = await speicher.alle_befunde(sitzung, blick.konto, staffel_id)
    werte = auswerten(
        BefundSicht(
            schwere=b.schwere,
            entscheidung=b.entscheidung,
            regel=b.regel,
            titel=b.titel,
            mannschaft=b.mannschaft,
            monat=s.datum.strftime("%Y-%m"),
        )
        for b, s in paare
    )
    berichte = await speicher.spiele(sitzung, blick.konto, staffel_id)
    return Auswertung(
        befunde=werte.befunde,
        offen=werte.offen,
        spiele=len(berichte),
        abgehakt=sum(1 for b in berichte if b.abgehakt),
        vorgaenge=len(await speicher.vorgaenge(sitzung, blick.konto)),
        # asdict und nicht vars: `Posten` hat slots und damit kein __dict__.
        nach_schwere=[Posten(**asdict(p)) for p in werte.nach_schwere],
        nach_regel=[Posten(**asdict(p)) for p in werte.nach_regel],
        nach_mannschaft=[Posten(**asdict(p)) for p in werte.nach_mannschaft],
        nach_monat=[Posten(**asdict(p)) for p in werte.nach_monat],
    )


# ── Staffeln ──────────────────────────────────────────────────────────────


@router.get("/staffeln", summary="Die eigenen Staffeln")
async def staffeln(sitzung: DbSitzung, blick: HierBlick) -> list[StaffelAusgabe]:
    """Staffeln gehören dem, der sie anlegt. Wer wie viele hat, ist egal."""
    return [StaffelAusgabe.model_validate(s) for s in await speicher.staffeln(sitzung, blick.konto)]


@router.post(
    "/staffeln",
    status_code=status.HTTP_201_CREATED,
    summary="Staffel anlegen",
    dependencies=NUTZER,
)
async def staffel_anlegen(
    daten: StaffelAnlegen, sitzung: DbSitzung, blick: HierBlick
) -> StaffelAusgabe:
    """Sie gehört dem, der sie anlegt."""
    return StaffelAusgabe.model_validate(
        await speicher.staffel_anlegen(sitzung, konto_von(blick), daten)
    )


@router.patch("/staffeln/{staffel_id}", summary="Staffel ändern")
async def staffel_aendern(
    staffel_id: uuid.UUID, daten: StaffelAendern, sitzung: DbSitzung, blick: HierBlick
) -> StaffelAusgabe:
    """Nur die mitgeschickten Felder. Ausgelassene bleiben stehen.

    Ein Dialog, der offen stand, während woanders geschrieben wurde, schreibt
    sonst einen alten Wert zurück.
    """
    return StaffelAusgabe.model_validate(
        await speicher.staffel_aendern(sitzung, blick.konto, staffel_id, daten)
    )


@router.delete(
    "/staffeln/{staffel_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Staffel mit allen Spielberichten entfernen",
)
async def staffel_entfernen(staffel_id: uuid.UUID, sitzung: DbSitzung, blick: HierBlick) -> None:
    await speicher.staffel_loeschen(sitzung, blick.konto, staffel_id)


# ── Einspielen ────────────────────────────────────────────────────────────


@router.post("/import", summary="Geprüfte Spielberichte einspielen")
async def einspielen(
    auftrag: ImportAuftrag, sitzung: DbSitzung, blick: HierBlick
) -> ImportErgebnis:
    """Der Weg, auf dem Daten hereinkommen.

    Die DFBnet-Automation laeuft als eigener Dienst (docs/06-artefakte.md) und
    schiebt hier herein. Dass sie das noch nicht tut, aendert an diesem
    Endpunkt nichts - er ist die Naht, an der sie spaeter ansetzt.
    """
    angelegt, aktualisiert, befunde = await speicher.einspielen(sitzung, konto_von(blick), auftrag)
    return ImportErgebnis(angelegt=angelegt, aktualisiert=aktualisiert, befunde=befunde)


@router.get("/beispieldaten", summary="Stecken erfundene Spiele in den Listen?")
async def beispieldaten(sitzung: DbSitzung, blick: HierBlick) -> Beispieldatenstand:
    return Beispieldatenstand(anzahl=await speicher.beispieldaten_zaehlen(sitzung, blick.konto))


@router.delete(
    "/beispieldaten",
    summary="Erfundene Spiele entfernen",
    dependencies=NUTZER,
)
async def beispieldaten_loeschen(sitzung: DbSitzung, blick: HierBlick) -> Beispieldatenstand:
    """Aus den eigenen Staffeln alles weg, was mit der Attrappe hereinkam.

    Echte Spiele bleiben: die Bedingung steht auf der Kennung, die der
    Prüfdienst seinen erfundenen Spielen gibt.
    """
    return Beispieldatenstand(entfernt=await speicher.beispieldaten_loeschen(sitzung, blick.konto))


# ── Ein Spielbericht ──────────────────────────────────────────────────────


@router.get("/spiele/{spiel_id}", summary="Ein Spielbericht mit seinen Befunden")
async def spiel(spiel_id: uuid.UUID, sitzung: DbSitzung, blick: HierBlick) -> SpielAusgabe:
    bericht = await speicher.spiel(sitzung, blick.konto, spiel_id)
    geordnet = sortiert([_sicht(b) for b in bericht.befunde])
    # Die Reihenfolge kommt aus der Fachlichkeit, die Daten aus der Tabelle.
    # Ueber die Kennung und nicht ueber (regel, titel): zwei Spieler ohne Foto
    # in einem Spiel teilen sich beides.
    nach_schluessel = {str(b.id): b for b in bericht.befunde}
    zu_vorgang = await speicher.vorgaenge_zu_befunden(sitzung, [b.id for b in bericht.befunde])
    # Aus dem Datensatz und nicht Feld fuer Feld: aufgezaehlt fehlten hier alle
    # sechs Kopfdaten (Spielnummer, Anstoss, Spielort, Spieltag,
    # Mannschaftsart, Wettbewerb). In der Datenbank standen sie, ueber die
    # Schnittstelle kamen sie leer -- und weil die Spielnummer der
    # Suchschluessel des DFBnet-Formulars ist, waere jede Fallanlage an "Es
    # fehlt noch: Spielkennung" gescheitert, obwohl nichts fehlte. Gefunden am
    # 26.10.2026 mit `tools/nachsehen.py faelle`.
    #
    # Nur die Befunde werden gesetzt: ihre Reihenfolge kommt aus der
    # Fachlichkeit und nicht aus der Tabelle.
    return SpielAusgabe.model_validate(bericht).model_copy(
        update={
            "befunde": [
                _befund(b := nach_schluessel[s.schluessel], zu_vorgang.get(b.id)) for s in geordnet
            ]
        }
    )


@router.post("/spiele/{spiel_id}/haken", summary="Spielbericht abhaken")
async def abhaken(spiel_id: uuid.UUID, sitzung: DbSitzung, blick: HierBlick) -> SpielAusgabe:
    """Die eine Zusage des Artefakts: abgehakt wird erst, wenn zu jedem Befund
    eine Entscheidung vorliegt."""
    bericht = await speicher.spiel(sitzung, blick.konto, spiel_id)

    entscheidung = darf_abgehakt_werden([_sicht(b) for b in bericht.befunde])
    if not entscheidung.erlaubt:
        raise NochOffeneBefunde(
            entscheidung.grund, spiel_id=str(spiel_id), offen=entscheidung.offen
        )

    await speicher.haken_setzen(sitzung, blick.konto, spiel_id, True)
    # Ein abgehakter Bericht ist in DFBnet freizugeben. Vorgemerkt, nicht
    # getan: eingetragen wird es vom DFBnet-Dienst, und der arbeitet nur, wenn
    # die Uebertragung nicht pausiert ist.
    await speicher.uebertragung_einreihen(sitzung, "prueferfreigabe", spiel_id, spiel_id)
    return await spiel(spiel_id, sitzung, blick)


@router.delete("/spiele/{spiel_id}/haken", summary="Haken wieder entfernen")
async def haken_entfernen(
    spiel_id: uuid.UUID, sitzung: DbSitzung, blick: HierBlick
) -> SpielAusgabe:
    await speicher.haken_setzen(sitzung, blick.konto, spiel_id, False)
    return await spiel(spiel_id, sitzung, blick)


# ── Ein Befund ────────────────────────────────────────────────────────────


@router.post("/befunde/{befund_id}/entscheidung", summary="Befund entscheiden")
async def entscheiden(
    befund_id: uuid.UUID, daten: EntscheidungSetzen, sitzung: DbSitzung, blick: HierBlick
) -> BefundAusgabe:
    grund = entscheidung_pruefen(daten.art, daten.grund)
    gefunden = await speicher.entscheidung_setzen(sitzung, blick.konto, befund_id, daten.art, grund)
    vorhanden = await speicher.vorgang_zu_befund(sitzung, befund_id)
    return _befund(gefunden, vorhanden.id if vorhanden else None)


@router.delete("/befunde/{befund_id}/entscheidung", summary="Entscheidung zurücknehmen")
async def entscheidung_zuruecknehmen(
    befund_id: uuid.UUID, sitzung: DbSitzung, blick: HierBlick
) -> BefundAusgabe:
    """Der Befund ist wieder offen — und das Spiel damit nicht mehr abgehakt.

    Wer sich vertippt hat, soll das geradeziehen können, ohne den Bericht neu
    einzuspielen. Nur wenn zu dem Befund schon ein Schreiben **hinaus** ist,
    geht es nicht: der Verein hat es, und ein Befund, der hier wieder „offen"
    heißt, wäre eine Akte, die dem widerspricht.
    """
    # Zuerst: ob es ihn für den Aufrufer gibt. Sonst verriete die Antwort, dass
    # zu einem fremden Befund ein Schreiben hinausging.
    await speicher.befund(sitzung, blick.konto, befund_id)
    vorhanden = await speicher.vorgang_zu_befund(sitzung, befund_id)
    darf_zurueckgenommen_werden(vorhanden.zustand if vorhanden else None)
    gefunden = await speicher.entscheidung_zuruecknehmen(sitzung, blick.konto, befund_id)
    return _befund(gefunden, vorhanden.id if vorhanden else None)


@router.get("/befunde", summary="Alle Befunde, flach")
async def alle_befunde(
    sitzung: DbSitzung,
    blick: HierBlick,
    staffel_id: Annotated[uuid.UUID | None, Query(description="Nur diese Staffel")] = None,
    nur_offen: Annotated[bool, Query(description="Nur unentschiedene")] = False,
) -> list[BefundZeile]:
    """Die andere Frage: was ist in dieser Saison alles aufgelaufen.

    Die Warteschlange geht Spiel für Spiel; hier steht jeder Befund einzeln,
    mit dem Spiel an der Zeile — sonst wäre eine Zeile nicht zuzuordnen.
    """
    paare = await speicher.alle_befunde(sitzung, blick.konto, staffel_id, nur_offen)
    zu_vorgang = await speicher.vorgaenge_zu_befunden(sitzung, [b.id for b, _ in paare])
    return [
        BefundZeile(
            id=b.id,
            spiel_id=s.id,
            staffel_id=s.staffel_id,
            dfbnet_id=s.dfbnet_id,
            datum=s.datum,
            heim=s.heim,
            gast=s.gast,
            regel=b.regel,
            schwere=b.schwere,  # type: ignore[arg-type]
            titel=b.titel,
            person=b.person,
            mannschaft=b.mannschaft,
            entscheidung=b.entscheidung,  # type: ignore[arg-type]
            grund=b.grund,
            weg=b.weg,  # type: ignore[arg-type]
            vorgang_id=zu_vorgang.get(b.id),
        )
        for b, s in paare
    ]


# ── Einstellungen ─────────────────────────────────────────────────────────


@router.get("/karten", summary="Karten einer Person")
async def karten(
    sitzung: DbSitzung,
    blick: HierBlick,
    pass_nr: Annotated[str, Query(min_length=1, max_length=40)],
    wettbewerb: Annotated[str, Query(max_length=120)] = "",
    seit: dt.date | None = None,
) -> list[KarteAusgabe]:
    """Was in dieser Saison an Karten zusammengekommen ist.

    Gezaehlt wird hier **nicht**: die Schwellen (die fuenfte Verwarnung, im
    Pokal die zweite) stehen in den Regeldateien des Staffelleiters. Dieses
    Artefakt gibt heraus, was es weiss, und mischt sich nicht in die
    Spielordnung ein.
    """
    return [
        KarteAusgabe.model_validate(k)
        for k in await speicher.karten(sitzung, blick.konto, pass_nr, wettbewerb, seit)
    ]


def _einstellungen(werte: Einstellungen) -> EinstellungenAusgabe:
    """Die Einstellungen, und dazu der mitgelieferte Folgesatz.

    Als Platzhalter und nicht als Inhalt -- siehe `_regel`.
    """
    return EinstellungenAusgabe(**asdict(werte), vorgabe_folgesatz=texte.folgesatz())


@router.get("/einstellungen", summary="Die eigenen Einstellungen")
async def einstellungen(sitzung: DbSitzung, blick: HierBlick) -> EinstellungenAusgabe:
    return _einstellungen(await speicher.einstellungen(sitzung, konto_von(blick)))


@router.put("/einstellungen", summary="Einstellungen ändern")
async def einstellungen_setzen(
    daten: EinstellungenSetzen, sitzung: DbSitzung, blick: HierBlick
) -> EinstellungenAusgabe:
    """Nur die mitgeschickten Felder. Ausgelassene bleiben stehen."""
    return _einstellungen(await speicher.einstellungen_setzen(sitzung, konto_von(blick), daten))


# ── Mannschaften einer Staffel ────────────────────────────────────────────


@router.get("/staffeln/{staffel_id}/mannschaften", summary="Mannschaften einer Staffel")
async def mannschaften(
    staffel_id: uuid.UUID, sitzung: DbSitzung, blick: HierBlick
) -> list[MannschaftAusgabe]:
    return [_mannschaft(m) for m in await speicher.mannschaften(sitzung, blick.konto, staffel_id)]


@router.put("/staffeln/{staffel_id}/mannschaften", summary="Mannschaften einer Staffel setzen")
async def mannschaften_setzen(
    staffel_id: uuid.UUID, daten: MannschaftenSetzen, sitzung: DbSitzung, blick: HierBlick
) -> list[MannschaftAusgabe]:
    """Die Meldung als Ganzes.

    Wer die hoeheren Mannschaften mitschickt, bestaetigt sie damit -- ein
    spaeteres Einspielen aus DFBnet ueberschreibt sie dann nicht mehr.
    """
    gesetzt = await speicher.mannschaften_setzen(
        sitzung, blick.konto, staffel_id, daten.mannschaften
    )
    return [_mannschaft(m) for m in gesetzt]


# ── Vorgänge: Mahnung und Sportgerichtsfall ───────────────────────────────


@router.get("/vorgaenge", summary="Alle Vorgänge")
async def vorgaenge(
    sitzung: DbSitzung,
    blick: HierBlick,
    zustand: Annotated[str | None, Query(description="Nur dieser Zustand")] = None,
) -> list[VorgangZeile]:
    return [
        VorgangZeile.model_validate(v)
        for v in await speicher.vorgaenge(sitzung, blick.konto, zustand)
    ]


@router.get("/vorgaenge/{vorgang_id}", summary="Ein Vorgang mit seinem Text")
async def vorgang(vorgang_id: uuid.UUID, sitzung: DbSitzung, blick: HierBlick) -> VorgangAusgabe:
    gefunden, _, spiel, _ = await speicher.vorgang_mit_spiel(sitzung, blick.konto, vorgang_id)
    return _vorgang(gefunden, spiel.id)


def _formular(
    vorgang: Vorgang,
    befund: Befund,
    spiel: Spielbericht,
    staffel: Staffel,
    staffelleiter: str,
) -> mahnung.Mahnung:
    """Der Vordruck, gefüllt aus dem, was das Artefakt weiß."""
    return mahnung.Mahnung(
        mannschaftsart=mannschaftsart_fuer(staffel.altersklasse, spiel.mannschaftsart),
        spielklasse=staffel.spielklasse,
        spieltag=spiel.spieltag,
        staffelleiter=staffelleiter,
        spielnummer=spiel.spielnummer,
        datum=spiel.datum.strftime("%d.%m.%Y"),
        uhrzeit=spiel.anstoss,
        wettkampftyp=spiel.wettbewerb,
        heim=spiel.heim,
        gast=spiel.gast,
        spielort=spiel.spielort,
        verein=vorgang.verein or befund.mannschaft,
        kreuze=mahnung.kreuze_fuer([befund.regel]),
    )


@router.post(
    "/vorgaenge/{vorgang_id}/fallanlage",
    summary="Einen Sportgerichtsfall in DFBnet vormerken",
    status_code=status.HTTP_201_CREATED,
    dependencies=NUTZER,
)
async def vorgang_fallanlage(
    vorgang_id: uuid.UUID, sitzung: DbSitzung, blick: HierBlick
) -> UebertragungAusgabe:
    """Einen Fall beim Sportgericht vormerken.

    **Das eröffnet ein Verfahren gegen eine benannte Person.** Deshalb hängt es
    an einem eigenen Knopf und passiert nie nebenbei, weil jemand einen
    Spielbericht abgehakt hat — anders als die Prüferfreigabe.

    Vorgemerkt, nicht getan: angelegt wird es vom DFBnet-Dienst, und der
    arbeitet nur, wenn die Übertragung nicht pausiert ist. Fehlt eine
    Pflichtangabe, wird hier abgewiesen statt draußen am Formular.
    """
    vorgang, befund, spiel, staffel = await speicher.vorgang_mit_spiel(
        sitzung, blick.konto, vorgang_id
    )
    fall_pruefen(
        vorgang.art,
        staffel.sportgericht,
        spiel.spielnummer,
        vorgang.grund or befund.text,
    )
    return UebertragungAusgabe.model_validate(
        await speicher.uebertragung_einreihen(sitzung, "fallanlage", vorgang_id, spiel.id)
    )


@router.post(
    "/vorgaenge/{vorgang_id}/fallprobe",
    summary="Die Fallanlage proben, ohne etwas anzulegen",
    status_code=status.HTTP_201_CREATED,
    dependencies=NUTZER,
)
async def vorgang_fallprobe(
    vorgang_id: uuid.UUID, sitzung: DbSitzung, blick: HierBlick
) -> AuftragAusgabe:
    """Denselben Weg gehen und **nicht** speichern.

    **Ein Aktenzeichen ist dauerhaft.** Wer die Fallanlage ausprobieren will,
    legt sonst ein Verfahren gegen eine benannte Person an — und löscht es
    nicht wieder. Die Probe geht bis vor das Speichern: Menü, Suche, Treffer,
    Formular, Felder. Passt alles, sagt sie das; passt etwas nicht, sagt sie
    genau was.

    Dieselben Pflichtangaben wie beim Anlegen. Eine Probe, die mehr durchlässt
    als die Sache selbst, prüft die falsche Sache.

    Ein **Auftrag** und keine Übertragung: die Übertragung ist die Liste
    dessen, was wirklich hinaus soll, und eine Probe gehört nicht hinein.
    """
    vorgang, befund, spiel, staffel = await speicher.vorgang_mit_spiel(
        sitzung, blick.konto, vorgang_id
    )
    fall_pruefen(
        vorgang.art,
        staffel.sportgericht,
        spiel.spielnummer,
        vorgang.grund or befund.text,
    )
    darf_angefordert_werden(1 if await speicher.offener_auftrag(sitzung, blick.konto) else 0)
    return await _auftrag(
        sitzung,
        await speicher.auftrag_anfordern(
            sitzung, konto_von(blick), art="fallprobe", staffel_id=None, referenz=str(vorgang_id)
        ),
    )


@router.get(
    "/vorgaenge/{vorgang_id}/mahnung.pdf",
    summary="Das ausgefüllte Mahnungsformular",
    response_class=Response,
    responses={200: {"content": {"application/pdf": {}}}},
)
async def vorgang_mahnung(vorgang_id: uuid.UUID, sitzung: DbSitzung, blick: HierBlick) -> Response:
    """Der Vordruck des Verbandes, gefüllt aus Spiel, Befund und Einstellungen.

    **Verschickt wird nichts.** Das PDF geht an den Staffelleiter, der es
    prüft und selbst verschickt.

    Was nicht bekannt ist, bleibt leer -- die fehlenden Felder stehen im Kopf
    `X-Fehlende-Felder`, damit die Oberfläche sie nennen kann, ohne das PDF zu
    lesen. Ein Schriftstück an einen Verein trägt keine erfundenen Angaben.
    """
    vorgang, befund, spiel, staffel = await speicher.vorgang_mit_spiel(
        sitzung, blick.konto, vorgang_id
    )
    werte = await speicher.einstellungen(sitzung, konto_von(blick))

    formular = _formular(vorgang, befund, spiel, staffel, werte.staffelleiter)
    inhalt = mahnung.als_pdf(formular)
    name = f"Mahnung_{vorgang.aktenzeichen.replace('/', '-')}.pdf"
    return Response(
        content=inhalt,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="{name}"',
            "X-Fehlende-Felder": ", ".join(formular.fehlende_felder()),
        },
    )


@router.get("/vorgaenge/{vorgang_id}/mail", summary="Der Mailentwurf zu einem Vorgang")
async def vorgang_mail(vorgang_id: uuid.UUID, sitzung: DbSitzung, blick: HierBlick) -> MailEntwurf:
    """Betreff und Text, fertig zum Einfügen -- und wer als Empfänger passt.

    **Abgeschickt wird hier nichts**, und es gibt auch keinen Weg dorthin.
    Der Staffelleiter wählt den Empfänger und schickt in seinem Mailprogramm.

    Der Text ist der des Vorgangs: aus einer Vorlage entstanden, Wort für Wort
    vorhersagbar, ohne erzeugte Sprache.
    """
    vorgang, befund, spiel, staffel = await speicher.vorgang_mit_spiel(
        sitzung, blick.konto, vorgang_id
    )
    werte = await speicher.einstellungen(sitzung, konto_von(blick))

    if vorgang.art == "mahnung":
        return MailEntwurf(
            empfaenger=vorgang.empfaenger,
            betreff=vorgang.betreff
            or betreff_fuer(vorgang.aktenzeichen, spiel.heim, spiel.gast, spiel.datum),
            text=vorgang.text,
            anhang=f"/staffelpilot/vorgaenge/{vorgang_id}/mahnung.pdf",
            fehlende_felder=_formular(
                vorgang, befund, spiel, staffel, werte.staffelleiter
            ).fehlende_felder(),
        )

    # Ein Sportgerichtsfall. Zwei Schreiben, je nachdem, ob die Akte schon
    # existiert:
    #
    #   * **Vorher** der Antrag an das Sportgericht -- der Text des Vorgangs,
    #     aus der Vorlage entstanden.
    #   * **Nachher** die Mail an den Sportrichter, die sich auf das
    #     Aktenzeichen aus DFBnet beruft. Vorher gibt es keines, und eines zu
    #     erfinden hiesse, eine Akte zu nennen, die es nicht gibt.
    #
    # Was in beiden Faellen fehlt, steht in `fehlende_felder` -- ein Schreiben
    # mit Luecke ist besser als eines mit erfundener Angabe, aber nur, wenn
    # die Luecke auffaellt.
    fall = sportrichtermail.Fall(
        aktenzeichen=vorgang.dfbnet_aktenzeichen,
        verein=vorgang.verein,
        angeklagter=vorgang.betroffener,
        grund=vorgang.grund,
        anlagen=vorgang.anlagen,
        hinweis=vorgang.hinweis,
    )
    if not vorgang.dfbnet_aktenzeichen.strip():
        return MailEntwurf(
            empfaenger=vorgang.empfaenger,
            betreff=vorgang.betreff
            or betreff_fuer(vorgang.aktenzeichen, spiel.heim, spiel.gast, spiel.datum),
            text=vorgang.text,
            anhang="",
            fehlende_felder=fall.fehlende_felder(),
        )

    return MailEntwurf(
        empfaenger=vorgang.empfaenger,
        betreff=sportrichtermail.betreff(fall),
        text=sportrichtermail.text(fall),
        # Der Sonderbericht des Schiedsrichters liegt in DFBnet, nicht hier.
        anhang="",
        fehlende_felder=fall.fehlende_felder(),
    )


@router.patch("/vorgaenge/{vorgang_id}", summary="Text oder Empfänger eines Vorgangs ändern")
async def vorgang_aendern(
    vorgang_id: uuid.UUID, daten: VorgangAendern, sitzung: DbSitzung, blick: HierBlick
) -> VorgangAusgabe:
    felder = daten.model_dump(exclude_none=True)
    return _vorgang(await speicher.vorgang_aendern(sitzung, blick.konto, vorgang_id, felder))


@router.post("/vorgaenge/{vorgang_id}/zustand", summary="Vorgang weiterstellen")
async def vorgang_zustand(
    vorgang_id: uuid.UUID, daten: ZustandSetzen, sitzung: DbSitzung, blick: HierBlick
) -> VorgangAusgabe:
    """'versandt' heisst: ein Mensch hat es abgeschickt.

    Dieses Programm verschickt nichts und hat auch keinen Weg dorthin. Der
    Zustand haelt fest, was ausserhalb passiert ist.
    """
    return _vorgang(await speicher.vorgang_zustand(sitzung, blick.konto, vorgang_id, daten.zustand))


@router.delete(
    "/vorgaenge/{vorgang_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Vorgang verwerfen",
)
async def vorgang_loeschen(vorgang_id: uuid.UUID, sitzung: DbSitzung, blick: HierBlick) -> None:
    await speicher.vorgang_loeschen(sitzung, blick.konto, vorgang_id)


@router.post(
    "/befunde/{befund_id}/vorgang",
    status_code=status.HTTP_201_CREATED,
    summary="Aus einem Befund einen Entwurf machen",
)
async def vorgang_anlegen(
    befund_id: uuid.UUID, daten: VorgangAnlegen, sitzung: DbSitzung, blick: HierBlick
) -> VorgangAusgabe:
    """Erzeugt den Entwurf aus der Vorlage -- und verschickt ihn nicht.

    Die Art ergibt sich aus dem Weg des Befundes; ein Befund ohne Weg bekommt
    keinen Vorgang. Der Text entsteht genau einmal: wer ihn danach umschreibt,
    behaelt seine Fassung.
    """
    return _vorgang(await speicher.vorgang_anlegen(sitzung, konto_von(blick), befund_id, daten))


# ── Regelkatalog ──────────────────────────────────────────────────────────


def _sichten(parameter: list[Regelparameter]) -> list[dienst.ParameterSicht]:
    return [
        dienst.ParameterSicht(
            schluessel=p.schluessel,
            name=p.name,
            art=p.art,
            vorgabe=p.vorgabe,
            kleinst=p.kleinst,
            groesst=p.groesst,
        )
        for p in parameter
    ]


def _regel(
    r: Regel,
    eigener: Kontotext | None = None,
    parameter: list[Regelparameter] | None = None,
    wahl: Regelwahl | None = None,
) -> RegelAusgabe:
    """Der Katalogeintrag, wie er fuer diesen Staffelleiter gilt.

    Die Vorgabe wird **mitgeschickt und nicht eingesetzt** -- bei den Saetzen
    wie bei den Parametern: die Oberflaeche zeigt sie als Platzhalter, und das
    leere Feld bleibt leer. Wuerde sie hineingeschrieben, haette der erste
    Klick auf Speichern den heutigen Stand eingefroren.
    """
    vorgabe = texte.vorlage_fuer(r.schluessel)
    parameter = parameter or []
    eigen_aktiv = wahl.aktiv if wahl else None
    eigene = dienst.gueltige_werte(_sichten(parameter), wahl.werte if wahl else {})
    return RegelAusgabe.model_validate(r).model_copy(
        update={
            "aktiv": dienst.wirksam_aktiv(r.aktiv, eigen_aktiv),
            "sachverhalt": eigener.sachverhalt if eigener else "",
            "hinweis": eigener.hinweis if eigener else "",
            "vorgabe_sachverhalt": vorgabe.sachverhalt,
            "vorgabe_hinweis": vorgabe.hinweis,
            "parameter": [
                ParameterAusgabe.model_validate(
                    {
                        "schluessel": p.schluessel,
                        "name": p.name,
                        "art": p.art,
                        "vorgabe": p.vorgabe,
                        "kleinst": p.kleinst,
                        "groesst": p.groesst,
                        "erklaerung": p.erklaerung,
                        "wert": eigene.get(p.schluessel),
                    }
                )
                for p in parameter
            ],
            "angepasst": dienst.ist_angepasst(eigen_aktiv, eigene, _sichten(parameter)),
        }
    )


async def _katalog_fuer(sitzung: DbSitzung, benutzer_id: uuid.UUID) -> list[RegelAusgabe]:
    eigene = await speicher.kontotexte(sitzung, benutzer_id)
    parameter = await speicher.regelparameter(sitzung)
    wahl = await speicher.regelwahlen(sitzung, benutzer_id)
    return [
        _regel(r, eigene.get(r.schluessel), parameter.get(r.schluessel), wahl.get(r.schluessel))
        for r in await speicher.regeln(sitzung)
    ]


# ── Regeldateien ──────────────────────────────────────────────────────────
#
# Der Quelltext der Prüfungen. **Das ist ausführbarer Code**: er läuft im
# Prüfdienst, in dessen Container, mit dessen Rechten. Lesen darf jeder, der
# das Artefakt sieht; schreiben nur ein Verwalter — das ist der ganze Grund,
# warum diese vier Routen eine eigene Abhängigkeit tragen.


def _zeilen(inhalt: str) -> int:
    return inhalt.count("\n") + 1 if inhalt else 0


def _regeldatei(d: Regeldatei) -> RegeldateiAusgabe:
    """Die Zeile fuer die Liste -- ohne Quelltext."""
    return RegeldateiAusgabe(
        id=d.id,
        name=d.name,
        aktiv=d.aktiv,
        zeilen=_zeilen(d.inhalt),
        geaendert=d.geaendert,
    )


def _regeldatei_mit_inhalt(d: Regeldatei) -> RegeldateiInhalt:
    """Dieselbe Zeile samt Quelltext -- beim Oeffnen zum Bearbeiten."""
    return RegeldateiInhalt(
        id=d.id,
        name=d.name,
        aktiv=d.aktiv,
        zeilen=_zeilen(d.inhalt),
        geaendert=d.geaendert,
        inhalt=d.inhalt,
    )


@router.get("/regeldateien", summary="Die Regeldateien dieser Installation")
async def regeldateien(sitzung: DbSitzung) -> list[RegeldateiAusgabe]:
    """Ohne Quelltext. Dreißig Dateien mit je zweihundert Zeilen wären ein
    Viertelmegabyte für eine Liste."""
    return [_regeldatei(d) for d in await speicher.regeldateien(sitzung)]


@router.get("/regeldateien/{datei_id}", summary="Eine Regeldatei mit Quelltext")
async def regeldatei(datei_id: uuid.UUID, sitzung: DbSitzung) -> RegeldateiInhalt:
    return _regeldatei_mit_inhalt(await speicher.regeldatei(sitzung, datei_id))


@router.put(
    "/regeldateien",
    summary="Eine Regeldatei anlegen oder überschreiben",
    dependencies=NUR_VERWALTER,
)
async def regeldatei_setzen(daten: RegeldateiSetzen, sitzung: DbSitzung) -> RegeldateiAusgabe:
    """Hochladen oder ändern — am Dateinamen erkannt.

    **Nur Verwalter.** Was hier ankommt, führt der Prüfdienst aus.

    Der Name wird zu einem Pfad in seinem Ordner; das Muster lässt deshalb nur
    Ziffern, Buchstaben, Unterstrich und `.py` zu. Ein `../` darin wäre ein
    Weg aus dem Ordner heraus.
    """
    return _regeldatei(await speicher.regeldatei_setzen(sitzung, daten))


@router.post(
    "/regeldateien/vorlagen",
    summary="Die mitgelieferten Regeln des Prüfdienstes übernehmen",
    dependencies=NUR_VERWALTER,
)
async def vorlagen_uebernehmen(daten: VorlagenUebergeben, sitzung: DbSitzung) -> VorlagenStand:
    """Einmalig. Der Prüfdienst bietet an, das Artefakt entscheidet.

    Die neun mitgelieferten Prüfungen lagen bisher nur in seinem Ordner: die
    Oberfläche zeigte „Keine eigenen Regeldateien", obwohl neun liefen — und
    zu bearbeiten gab es nichts.

    **Einmal**, denn wer eine Regel löscht, soll sie los sein. **Und nie über
    etwas drüber**: was schon dasteht, bleibt stehen, auch wenn eine neuere
    Fassung die Vorlage geändert hat.
    """
    uebernommen, uebergangen, schon = await speicher.vorlagen_uebernehmen(sitzung, daten)
    return VorlagenStand(uebernommen=uebernommen, uebergangen=uebergangen, schon_geschehen=schon)


@router.patch(
    "/regeldateien/{datei_id}",
    summary="Eine Regeldatei ändern oder stilllegen",
    dependencies=NUR_VERWALTER,
)
async def regeldatei_aendern(
    datei_id: uuid.UUID, daten: RegeldateiAendern, sitzung: DbSitzung
) -> RegeldateiAusgabe:
    return _regeldatei(await speicher.regeldatei_aendern(sitzung, datei_id, daten))


@router.delete(
    "/regeldateien/{datei_id}",
    summary="Eine Regeldatei entfernen",
    status_code=status.HTTP_204_NO_CONTENT,
    response_class=Response,
    dependencies=NUR_VERWALTER,
)
async def regeldatei_loeschen(datei_id: uuid.UUID, sitzung: DbSitzung) -> Response:
    """Weg — der Prüfdienst räumt sie beim nächsten Lauf aus seinem Ordner.

    Befunde dieser Regel bleiben stehen: gelöscht heißt „wird nicht mehr
    geprüft" und nicht „ist nie passiert".
    """
    await speicher.regeldatei_loeschen(sitzung, datei_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/regeln", summary="Was geprüft wird -- im eigenen Regelsatz")
async def regeln(sitzung: DbSitzung, blick: HierBlick) -> list[RegelAusgabe]:
    return await _katalog_fuer(sitzung, konto_von(blick))


@router.get("/regelsatz", summary="Der eigene Regelsatz, aufgelöst")
async def regelsatz(sitzung: DbSitzung, blick: HierBlick) -> RegelsatzAusgabe:
    """Für den Prüflauf: der Satz dessen, der ihn angefordert hat.

    Die Werte stehen vollständig da; der Prüfdienst soll nicht wissen müssen,
    was hier Vorgabe ist.
    """
    konto = konto_von(blick)
    wahl = await speicher.regelwahlen(sitzung, konto)
    parameter = await speicher.regelparameter(sitzung)
    aus, werte = dienst.regelsatz_aus(
        [(r.schluessel, r.aktiv) for r in await speicher.regeln(sitzung)],
        {k: _sichten(v) for k, v in parameter.items()},
        {k: (w.aktiv, w.werte) for k, w in wahl.items()},
    )
    return RegelsatzAusgabe(
        staffelleiter=await speicher.anzeigename(sitzung, konto), aus=aus, werte=werte
    )


@router.put(
    "/staffeln/aus-dfbnet",
    summary="Die eigenen Staffeln aus DFBnet uebernehmen",
    dependencies=NUR_PRUEFDIENST,
)
async def staffeln_aus_dfbnet(
    daten: StaffelnAusDfbnet, sitzung: DbSitzung, blick: HierBlick
) -> StaffelnUebernommen:
    """Was DFBnet unter „Eigene Staffeln" fuehrt, hierher.

    Das ersetzt das Abschreiben von Hand -- und genau daran war die Prüfung
    gescheitert: eine Spielklasse, die DFBnet nicht kennt, und eine
    Altersklasse, die nicht zur Mannschaftsart passte.

    Abgeglichen wird über die Kennung, dann über den Namen, dann über die
    Spielklasse. **Gelöscht wird nichts**, und `aktiv` bleibt, wie es war: ob
    eine Staffel mitläuft, entscheidet der Staffelleiter und nicht DFBnet.
    """
    angelegt, aktualisiert, namen = await speicher.staffeln_aus_dfbnet(
        sitzung, konto_von(blick), daten
    )
    return StaffelnUebernommen(angelegt=angelegt, aktualisiert=aktualisiert, namen=namen)


@router.put(
    "/regeln",
    summary="Den Regelkatalog einspielen",
    # Der Katalog gehoert niemandem: wer ihn ersetzt, ersetzt ihn fuer alle.
    dependencies=NUR_VERWALTER,
)
async def regelkatalog_setzen(
    daten: RegelkatalogSetzen, sitzung: DbSitzung, blick: HierBlick
) -> list[RegelAusgabe]:
    """Der Prüfdienst meldet, was es gibt.

    Was er nicht mehr meldet, verschwindet -- ein Schalter für eine Regel, die
    niemand mehr prüft, verspricht etwas, das nicht passiert. Die Schalter der
    übrigen bleiben stehen: `aktiv` gehört dem Staffelleiter, nicht dem
    Katalog.
    """
    await speicher.regelkatalog_setzen(sitzung, daten.regeln)
    return await _katalog_fuer(sitzung, konto_von(blick))


@router.patch(
    "/regeln/{regel_id}",
    summary="Eine Regel umschalten, einstellen oder umformulieren",
    dependencies=NUTZER,
)
async def regel_aendern(
    regel_id: uuid.UUID, daten: RegelAendern, sitzung: DbSitzung, blick: HierBlick
) -> RegelAusgabe:
    """Was an einer Regel dem Staffelleiter gehört: der Schalter und die Sätze.

    Geprüft wird trotzdem im Prüfdienst -- der liest hier nach, was er melden
    soll. Dass eine abgeschaltete Regel keine Befunde mehr erzeugt, passiert
    dort und nicht hier.

    Die Sätze dagegen wirken hier: sie stehen im nächsten Schreiben, das aus
    einem Befund dieser Regel entsteht. **Schon abgeschickte Schreiben ändern
    sich nicht** -- ihr Text liegt am Vorgang und nicht an dieser Zeile.

    Alles drei gilt **nur fuer den, der es setzt**: Schalter und Werte in den
    Laeufen, die er anfordert, die Saetze in den Schreiben, die er anlegt.
    """
    konto = konto_von(blick)
    regel = await speicher.regel(sitzung, regel_id)
    text = await speicher.regeltext_setzen(sitzung, konto, regel.schluessel, daten)
    parameter = (await speicher.regelparameter(sitzung)).get(regel.schluessel, [])
    werte = None
    if daten.werte is not None:
        werte = dienst.eigene_werte(_sichten(parameter), daten.werte)
    wahl = await speicher.regelwahl_setzen(sitzung, konto, regel, daten.aktiv, werte)
    return _regel(regel, text, parameter, wahl)


# ── Aufträge: Prüflauf und Initialisierung ────────────────────────────────
#
# Der Prüflauf fährt minutenlang einen echten Browser und läuft deshalb in
# einem eigenen Dienst (docs/06-artefakte.md). Was hier steht, ist der Auftrag
# dafür — ein Datensatz, kein laufender Prozess. Das Gateway darf neu starten,
# ohne dass jemand vor einer Anzeige sitzt, die nie wieder weiterzählt.
#
# **Hier passiert nichts von selbst.** Solange kein Prüfdienst läuft, bleibt
# ein Auftrag auf „angefordert" stehen. Kein Klick in dieser Oberfläche meldet
# sich irgendwo an oder trägt irgendwo etwas ein.


async def _auftrag(sitzung: DbSitzung, a: Auftrag) -> AuftragAusgabe:
    offen = a.zustand in dienst.OFFENE_ZUSTAENDE
    return AuftragAusgabe.model_validate(a).model_copy(
        update={
            "konto": await speicher.auftraggeber(sitzung, a.id),
            "vor_dir": await speicher.auftraege_davor(sitzung, a) if offen else 0,
        }
    )


@router.get("/auftraege", summary="Prüfläufe und Initialisierungen")
async def auftraege(sitzung: DbSitzung, blick: HierBlick) -> list[AuftragZeile]:
    return [AuftragZeile.model_validate(a) for a in await speicher.auftraege(sitzung, blick.konto)]


@router.get("/auftraege/offen", summary="Der Auftrag, der gerade läuft")
async def auftrag_offen(sitzung: DbSitzung, blick: HierBlick) -> AuftragAusgabe | None:
    """`null`, wenn keiner unterwegs ist.

    Die Oberfläche fragt das im Sekundentakt ab; ein 404 wäre dort ein Fehler
    und kein Ergebnis, und die Konsole liefe damit voll.
    """
    offen = await speicher.offener_auftrag(sitzung, blick.konto)
    return await _auftrag(sitzung, offen) if offen else None


@router.post(
    "/auftraege",
    status_code=status.HTTP_201_CREATED,
    summary="Auftrag anfordern",
    dependencies=NUTZER,
)
async def auftrag_anfordern(
    daten: AuftragAnfordern, sitzung: DbSitzung, blick: HierBlick
) -> AuftragAusgabe:
    """Je Konto einer nach dem anderen.

    Zwei Läufe gleichzeitig hießen zwei Browser an derselben Anmeldung, und der
    zweite wirft den ersten hinaus — mitten in einem halb gelesenen
    Spielbericht. Verschiedene Konten stehen einander nicht im Weg: der
    Prüfdienst arbeitet ihre Aufträge der Reihe nach ab.
    """
    darf_angefordert_werden(1 if await speicher.offener_auftrag(sitzung, blick.konto) else 0)
    return await _auftrag(
        sitzung,
        await speicher.auftrag_anfordern(sitzung, konto_von(blick), daten.art, daten.staffel_id),
    )


@router.get("/auftraege/{auftrag_id}", summary="Ein Auftrag mit seinem Protokoll")
async def auftrag(auftrag_id: uuid.UUID, sitzung: DbSitzung, blick: HierBlick) -> AuftragAusgabe:
    return await _auftrag(sitzung, await speicher.auftrag(sitzung, blick.konto, auftrag_id))


@router.post("/auftraege/{auftrag_id}/fortschritt", summary="Fortschritt melden")
async def auftrag_fortschritt(
    auftrag_id: uuid.UUID, daten: Fortschritt, sitzung: DbSitzung, blick: HierBlick
) -> AuftragAusgabe:
    """Vom Prüfdienst aufgerufen, nicht von der Oberfläche.

    Die erste Meldung setzt den Auftrag auf „läuft": dass er sich meldet,
    **ist** der Beleg dafür, dass er angefangen hat.
    """
    return await _auftrag(
        sitzung, await speicher.auftrag_fortschreiben(sitzung, blick.konto, auftrag_id, daten)
    )


@router.put(
    "/auftraege/{auftrag_id}/ansicht/{art}",
    summary="Ein Abbild der Seite ablegen",
    status_code=status.HTTP_204_NO_CONTENT,
    response_class=Response,
)
async def ansicht_setzen(
    auftrag_id: uuid.UUID, art: str, sitzung: DbSitzung, blick: HierBlick, anfrage: Request
) -> Response:
    """Vom Prüfdienst aufgerufen, nicht von der Oberfläche.

    Der Rumpf ist das JPEG selbst und kein JSON mit Base64 darin: das wäre ein
    Drittel mehr Bytes für nichts.

    Es gibt genau zwei Arten. `aktuell` veraltet im Sekundentakt, `fehler` ist
    der Beweis, woran es lag — und wird deshalb beim nächsten Schritt **nicht**
    überschrieben.
    """
    bild = await anfrage.body()
    ansicht_pruefen(art, bild)
    schritt = anfrage.headers.get("X-Schritt", "")[:200]
    await speicher.ansicht_setzen(sitzung, blick.konto, auftrag_id, art, bild, schritt)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/auftraege/{auftrag_id}/ansichten", summary="Welche Abbilder es gibt")
async def ansichten(auftrag_id: uuid.UUID, sitzung: DbSitzung, blick: HierBlick) -> Ansichten:
    return Ansichten(arten=await speicher.ansicht_arten(sitzung, blick.konto, auftrag_id))


@router.get(
    "/auftraege/{auftrag_id}/ansicht/{art}",
    summary="Das Abbild der Seite",
    response_class=Response,
    responses={200: {"content": {"image/jpeg": {}}}},
)
async def ansicht(
    auftrag_id: uuid.UUID, art: str, sitzung: DbSitzung, blick: HierBlick
) -> Response:
    """Was der Prüfdienst zuletzt vor sich hatte.

    **Nicht zwischenspeichern.** Dasselbe Bild unter derselben Adresse ändert
    sich im Sekundentakt; ein Browser, der es behält, zeigt eine Ansicht von
    vor zwei Minuten und sieht dabei aus wie eine aktuelle.
    """
    gefunden = await speicher.ansicht(sitzung, blick.konto, auftrag_id, art)
    return Response(
        content=gefunden.bild,
        media_type="image/jpeg",
        headers={
            "Cache-Control": "no-store",
            "X-Schritt": gefunden.schritt,
        },
    )


@router.post("/auftraege/{auftrag_id}/abschluss", summary="Auftrag beenden")
async def auftrag_abschliessen(
    auftrag_id: uuid.UUID, daten: Abschluss, sitzung: DbSitzung, blick: HierBlick
) -> AuftragAusgabe:
    """Vom Prüfdienst — oder von der Oberfläche mit `abgebrochen`."""
    return await _auftrag(
        sitzung, await speicher.auftrag_abschliessen(sitzung, blick.konto, auftrag_id, daten)
    )


# ── Übertragung nach DFBnet ───────────────────────────────────────────────
#
# **Hier wird nichts übertragen.** Diese Endpunkte führen eine Liste dessen,
# was in DFBnet einzutragen wäre. Eintragen würde es der DFBnet-Dienst — und
# der arbeitet nur, wenn die Übertragung nicht pausiert ist. Auf einer
# frischen Installation ist sie das: eine Freigabe in DFBnet ist eine Handlung
# nach außen, und die soll nicht passieren, weil jemand die Software zum
# ersten Mal gestartet hat.


async def _uebertragung(sitzung: DbSitzung, u: Uebertragung) -> UebertragungAusgabe:
    return UebertragungAusgabe.model_validate(u).model_copy(
        update={"konto": await speicher.uebertragungskonto(sitzung, u.id)}
    )


@router.get("/uebertragungen", summary="Was nach DFBnet hinaus soll")
async def uebertragungen(sitzung: DbSitzung, blick: HierBlick) -> UebertragungStand:
    """Was man selbst vorgemerkt hat.

    Dem Prüfdienst ohne Konto zählt `offen` nur, was hinaus **darf**: jeder
    Staffelleiter gibt für sich frei, und was niemand freigegeben hat, geht ihn
    nichts an.
    """
    zahlen = await speicher.uebertragung_stand(sitzung, blick.konto)
    if blick.konto is None:
        zahlen["offen"] = await speicher.freigegeben_offen(sitzung)
        pausiert = zahlen["offen"] == 0
    else:
        pausiert = (await speicher.einstellungen(sitzung, blick.konto)).uebertragung_pausiert
    alle = await speicher.uebertragungen(sitzung, blick.konto)
    return UebertragungStand(
        pausiert=pausiert,
        **zahlen,
        # Nur die gescheiterten ausgeschrieben: sie sind das Einzige, wozu
        # jemand etwas tun muss.
        fehlerhafte=[UebertragungAusgabe.model_validate(u) for u in alle if u.zustand == "fehler"],
    )


@router.post(
    "/uebertragungen",
    status_code=status.HTTP_201_CREATED,
    summary="Etwas zur Übertragung vormerken",
)
async def uebertragung_einreihen(
    daten: UebertragungEinreihen, sitzung: DbSitzung, blick: HierBlick
) -> UebertragungAusgabe:
    """Vormerken, nicht ausführen — und nur, was einem gehört.

    Idempotent über `(aktion, referenz)`: abhaken, Haken entfernen und wieder
    abhaken darf keine zwei Freigaben erzeugen.
    """
    bezug = dienst.kennung_aus_referenz(daten.referenz)
    if daten.aktion == "fallanlage":
        _, _, dazu, _ = await speicher.vorgang_mit_spiel(sitzung, blick.konto, bezug)
    else:
        dazu = await speicher.spiel(sitzung, blick.konto, bezug)
    return UebertragungAusgabe.model_validate(
        await speicher.uebertragung_einreihen(sitzung, daten.aktion, bezug, dazu.id)
    )


@router.post("/uebertragungen/pause", summary="Übertragung anhalten oder weiterlaufen lassen")
async def uebertragung_pause(
    daten: Pause, sitzung: DbSitzung, blick: HierBlick
) -> UebertragungStand:
    """Der eine Schalter, der entscheidet, ob draußen etwas passiert."""
    await speicher.einstellungen_setzen(
        sitzung, konto_von(blick), EinstellungenSetzen(uebertragung_pausiert=daten.pausiert)
    )
    return await uebertragungen(sitzung, blick)


@router.post("/uebertragungen/wiederholen", summary="Gescheitertes zurück in die Schlange")
async def uebertragung_wiederholen(
    sitzung: DbSitzung,
    blick: HierBlick,
    uebertragung_id: Annotated[
        uuid.UUID | None, Query(description="Nur diese; ohne Angabe alle gescheiterten")
    ] = None,
) -> UebertragungStand:
    """Nach einem Netzausfall stehen dort zwanzig Zeilen mit demselben Fehler.
    Die einzeln anzuklicken ist keine Arbeit, sondern eine Strafe."""
    await speicher.uebertragung_wiederholen(sitzung, blick.konto, uebertragung_id)
    return await uebertragungen(sitzung, blick)


@router.post("/uebertragungen/naechste", summary="Die nächste offene übernehmen")
async def uebertragung_uebernehmen(
    sitzung: DbSitzung, blick: HierBlick
) -> UebertragungAusgabe | None:
    """Vom Prüfdienst aufgerufen. `null`, wenn nichts offen ist.

    Übernehmen und nicht nur lesen: sonst greifen zwei Dienste nach derselben
    Zeile und tragen dieselbe Freigabe zweimal in DFBnet ein.

    **Nur, was sein Staffelleiter freigegeben hat.** Die Zeile nennt sein
    Konto: mit dessen Zugang geht sie hinaus. Mit `?konto=` kommen nur Zeilen
    dieses Kontos, damit sich der Dienst nicht nach jeder ummelden muss.
    """
    gefunden = await speicher.uebertragung_uebernehmen(sitzung, blick.konto)
    return await _uebertragung(sitzung, gefunden) if gefunden else None


@router.post("/uebertragungen/{uebertragung_id}/abschluss", summary="Ergebnis melden")
async def uebertragung_abschliessen(
    uebertragung_id: uuid.UUID, daten: UebertragungAbschluss, sitzung: DbSitzung, blick: HierBlick
) -> UebertragungAusgabe:
    """Vom DFBnet-Dienst aufgerufen, nicht von der Oberfläche."""
    return UebertragungAusgabe.model_validate(
        await speicher.uebertragung_abschliessen(sitzung, blick.konto, uebertragung_id, daten)
    )


# ── DFBnet-Zugang ─────────────────────────────────────────────────────────
#
# Das Passwort liegt verschlüsselt, mit einem Schlüssel aus der Umgebung
# (`STAFFELPILOT_SCHLUESSEL`) und nicht aus der Datenbank — ein Abzug allein
# ist damit wertlos. Es kommt an genau einer Stelle wieder heraus, und die
# antwortet nur dem Konto des Prüfdienstes — auch keinem Verwalter.
#
# Jeder Staffelleiter hat seinen eigenen.
#
# Ohne Schlüssel wird **nichts** abgelegt. Lieber gar nicht speichern als ein
# Passwort im Klartext.


@router.get("/zugang", summary="Ist ein DFBnet-Zugang hinterlegt?")
async def zugang_stand(sitzung: DbSitzung, blick: HierBlick) -> ZugangStand:
    """Ein Ja oder Nein und der Benutzername. Mehr verrät diese Antwort nicht."""
    gespeichert, benutzer = await speicher.zugang_stand(sitzung, konto_von(blick))
    return ZugangStand(
        gespeichert=gespeichert,
        benutzer=benutzer,
        schluessel_vorhanden=speicher.schluessel_vorhanden(),
    )


@router.get("/einrichtung", summary="Wo die Einrichtung steht")
async def einrichtung(sitzung: DbSitzung, blick: HierBlick) -> Einrichtungsstand:
    """Zugang, Staffeln, abgehakt — in einer Antwort.

    Die Oberfläche fragt das beim Betreten des Artefakts: ohne DFBnet-Zugang
    und ohne Staffel bleibt jede Liste leer, und ohne diesen Ruf stünde dort
    „keine Spielberichte" statt „hier fehlt noch etwas".
    """
    zugang, staffeln, erledigt = await speicher.einrichtungsstand(sitzung, konto_von(blick))
    return Einrichtungsstand(
        schritt=einrichtung_schritt(zugang=zugang, staffeln=staffeln, erledigt=erledigt),
        zugang=zugang,
        staffeln=staffeln,
        erledigt=erledigt,
        schluessel_vorhanden=speicher.schluessel_vorhanden(),
    )


@router.put(
    "/zugang",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=NUTZER,
    summary="DFBnet-Zugang hinterlegen",
)
async def zugang_setzen(daten: ZugangSetzen, sitzung: DbSitzung, blick: HierBlick) -> Response:
    """Das Passwort wird verschlüsselt abgelegt und kommt hier nie zurück.

    Fehlt der Schlüssel in der Umgebung, wird nichts gespeichert — die Antwort
    ist dann 503, weil das ein Betriebsproblem ist und kein Tippfehler.
    """
    await speicher.zugang_setzen(sitzung, konto_von(blick), daten)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.delete(
    "/zugang",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=NUTZER,
    summary="DFBnet-Zugang entfernen",
)
async def zugang_loeschen(sitzung: DbSitzung, blick: HierBlick) -> Response:
    await speicher.zugang_loeschen(sitzung, konto_von(blick))
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post(
    "/zugang/abholen",
    dependencies=NUR_PRUEFDIENST,
    summary="Zugangsdaten für den Prüfdienst",
)
async def zugang_abholen(sitzung: DbSitzung, blick: HierBlick) -> ZugangGeheim:
    """Der einzige Ort, an dem das Passwort wieder herauskommt.

    `POST` und nicht `GET`: ein Geheimnis gehört nicht in eine Adresse, die
    ein Zwischenspeicher oder ein Protokoll mitschreibt.
    """
    benutzer, passwort = await speicher.zugang_abholen(sitzung, konto_von(blick))
    return ZugangGeheim(benutzer=benutzer, passwort=passwort)
