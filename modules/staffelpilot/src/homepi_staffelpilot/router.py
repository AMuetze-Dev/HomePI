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

from fastapi import APIRouter, Query, Response, status
from homepi_core.auth import Rolle, erfordert
from homepi_core.deps import DbSitzung

from . import mahnung, speicher
from .dienst import (
    BefundSicht,
    NochOffeneBefunde,
    SpielSicht,
    auswerten,
    betreff_fuer,
    darf_abgehakt_werden,
    darf_angefordert_werden,
    darf_zurueckgenommen_werden,
    entscheidung_pruefen,
    ist_faellig,
    mannschaft_unsicher,
    mannschaftsart_fuer,
    sortiert,
    zusammenfassen,
)
from .modelle import Befund, Mannschaft, Regel, Spielbericht, Staffel, Vorgang
from .schemas import (
    Abschluss,
    AuftragAnfordern,
    AuftragAusgabe,
    AuftragZeile,
    Auswertung,
    BefundAusgabe,
    BefundZeile,
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
    Pause,
    Posten,
    RegelAusgabe,
    RegelkatalogSetzen,
    RegelUmschalten,
    SpielAusgabe,
    SpielZeile,
    StaffelAendern,
    StaffelAnlegen,
    StaffelAusgabe,
    UebertragungAbschluss,
    UebertragungAusgabe,
    UebertragungEinreihen,
    UebertragungStand,
    VorgangAendern,
    VorgangAnlegen,
    VorgangAusgabe,
    VorgangZeile,
    ZugangGeheim,
    ZugangSetzen,
    ZugangStand,
    Zusammenfassung,
    ZustandSetzen,
)

router = APIRouter()


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
    )


def _vorgang(v: Vorgang) -> VorgangAusgabe:
    return VorgangAusgabe.model_validate(v)


# ── Warteschlange und Kachel ──────────────────────────────────────────────


@router.get("/", summary="Warteschlange der Spielberichte")
async def warteschlange(
    sitzung: DbSitzung,
    staffel_id: Annotated[uuid.UUID | None, Query(description="Nur diese Staffel")] = None,
    nur_faellig: Annotated[bool, Query(description="Nur Spiele im Prüfzeitraum")] = False,
) -> list[SpielZeile]:
    """Die tägliche Liste.

    `faellig` steht an jeder Zeile und wird nicht gespeichert: der
    Prüfzeitraum verschiebt sich mit jedem Tag, und ein geschriebener Wert
    wäre am Morgen darauf falsch.
    """
    berichte = await speicher.spiele(sitzung, staffel_id)
    tage = (await speicher.einstellungen(sitzung)).pruefzeitraum_tage
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
async def uebersicht(sitzung: DbSitzung) -> Zusammenfassung:
    berichte = await speicher.spiele(sitzung)
    return zusammenfassen(
        (SpielSicht(abgehakt=b.abgehakt, befunde=[_sicht(x) for x in b.befunde]) for b in berichte),
        staffeln_aktiv=await speicher.anzahl_aktiver_staffeln(sitzung),
        vorgaenge_entwurf=await speicher.anzahl_entwuerfe(sitzung),
    )


@router.get("/ergebnisse", summary="Auswertung der Saison")
async def ergebnisse(
    sitzung: DbSitzung,
    staffel_id: Annotated[uuid.UUID | None, Query(description="Nur diese Staffel")] = None,
) -> Auswertung:
    """Was aufgelaufen ist — gruppiert nach Schwere, Regel, Mannschaft, Monat.

    Gezählt wird in `dienst.auswerten` und nicht in SQL: vier
    `GROUP BY`-Abfragen wären dieselbe Entscheidung an vier Stellen, und keine
    davon ließe sich in Millisekunden prüfen.
    """
    paare = await speicher.alle_befunde(sitzung, staffel_id)
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
    berichte = await speicher.spiele(sitzung, staffel_id)
    return Auswertung(
        befunde=werte.befunde,
        offen=werte.offen,
        spiele=len(berichte),
        abgehakt=sum(1 for b in berichte if b.abgehakt),
        vorgaenge=len(await speicher.vorgaenge(sitzung)),
        # asdict und nicht vars: `Posten` hat slots und damit kein __dict__.
        nach_schwere=[Posten(**asdict(p)) for p in werte.nach_schwere],
        nach_regel=[Posten(**asdict(p)) for p in werte.nach_regel],
        nach_mannschaft=[Posten(**asdict(p)) for p in werte.nach_mannschaft],
        nach_monat=[Posten(**asdict(p)) for p in werte.nach_monat],
    )


# ── Staffeln ──────────────────────────────────────────────────────────────


@router.get("/staffeln", summary="Alle Staffeln")
async def staffeln(sitzung: DbSitzung) -> list[StaffelAusgabe]:
    return [StaffelAusgabe.model_validate(s) for s in await speicher.staffeln(sitzung)]


@router.post("/staffeln", status_code=status.HTTP_201_CREATED, summary="Staffel anlegen")
async def staffel_anlegen(daten: StaffelAnlegen, sitzung: DbSitzung) -> StaffelAusgabe:
    return StaffelAusgabe.model_validate(await speicher.staffel_anlegen(sitzung, daten))


@router.patch("/staffeln/{staffel_id}", summary="Staffel ändern")
async def staffel_aendern(
    staffel_id: uuid.UUID, daten: StaffelAendern, sitzung: DbSitzung
) -> StaffelAusgabe:
    """Nur die mitgeschickten Felder. Ausgelassene bleiben stehen.

    Ein Dialog, der offen stand, während woanders geschrieben wurde, schreibt
    sonst einen alten Wert zurück.
    """
    return StaffelAusgabe.model_validate(await speicher.staffel_aendern(sitzung, staffel_id, daten))


@router.delete(
    "/staffeln/{staffel_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Staffel mit allen Spielberichten entfernen",
)
async def staffel_entfernen(staffel_id: uuid.UUID, sitzung: DbSitzung) -> None:
    await speicher.staffel_loeschen(sitzung, staffel_id)


# ── Einspielen ────────────────────────────────────────────────────────────


@router.post("/import", summary="Geprüfte Spielberichte einspielen")
async def einspielen(auftrag: ImportAuftrag, sitzung: DbSitzung) -> ImportErgebnis:
    """Der Weg, auf dem Daten hereinkommen.

    Die DFBnet-Automation laeuft als eigener Dienst (docs/06-artefakte.md) und
    schiebt hier herein. Dass sie das noch nicht tut, aendert an diesem
    Endpunkt nichts - er ist die Naht, an der sie spaeter ansetzt.
    """
    angelegt, aktualisiert, befunde = await speicher.einspielen(sitzung, auftrag)
    return ImportErgebnis(angelegt=angelegt, aktualisiert=aktualisiert, befunde=befunde)


# ── Ein Spielbericht ──────────────────────────────────────────────────────


@router.get("/spiele/{spiel_id}", summary="Ein Spielbericht mit seinen Befunden")
async def spiel(spiel_id: uuid.UUID, sitzung: DbSitzung) -> SpielAusgabe:
    bericht = await speicher.spiel(sitzung, spiel_id)
    geordnet = sortiert([_sicht(b) for b in bericht.befunde])
    # Die Reihenfolge kommt aus der Fachlichkeit, die Daten aus der Tabelle.
    # Ueber die Kennung und nicht ueber (regel, titel): zwei Spieler ohne Foto
    # in einem Spiel teilen sich beides.
    nach_schluessel = {str(b.id): b for b in bericht.befunde}
    zu_vorgang = await speicher.vorgaenge_zu_befunden(sitzung, [b.id for b in bericht.befunde])
    return SpielAusgabe(
        id=bericht.id,
        staffel_id=bericht.staffel_id,
        dfbnet_id=bericht.dfbnet_id,
        datum=bericht.datum,
        heim=bericht.heim,
        gast=bericht.gast,
        ergebnis=bericht.ergebnis,
        abgehakt=bericht.abgehakt,
        abgehakt_am=bericht.abgehakt_am,
        befunde=[
            _befund(b := nach_schluessel[s.schluessel], zu_vorgang.get(b.id)) for s in geordnet
        ],
    )


@router.post("/spiele/{spiel_id}/haken", summary="Spielbericht abhaken")
async def abhaken(spiel_id: uuid.UUID, sitzung: DbSitzung) -> SpielAusgabe:
    """Die eine Zusage des Artefakts: abgehakt wird erst, wenn zu jedem Befund
    eine Entscheidung vorliegt."""
    bericht = await speicher.spiel(sitzung, spiel_id)

    entscheidung = darf_abgehakt_werden([_sicht(b) for b in bericht.befunde])
    if not entscheidung.erlaubt:
        raise NochOffeneBefunde(
            entscheidung.grund, spiel_id=str(spiel_id), offen=entscheidung.offen
        )

    await speicher.haken_setzen(sitzung, spiel_id, True)
    # Ein abgehakter Bericht ist in DFBnet freizugeben. Vorgemerkt, nicht
    # getan: eingetragen wird es vom DFBnet-Dienst, und der arbeitet nur, wenn
    # die Uebertragung nicht pausiert ist.
    await speicher.uebertragung_einreihen(
        sitzung,
        UebertragungEinreihen(aktion="prueferfreigabe", referenz=str(spiel_id), spiel_id=spiel_id),
    )
    return await spiel(spiel_id, sitzung)


@router.delete("/spiele/{spiel_id}/haken", summary="Haken wieder entfernen")
async def haken_entfernen(spiel_id: uuid.UUID, sitzung: DbSitzung) -> SpielAusgabe:
    await speicher.haken_setzen(sitzung, spiel_id, False)
    return await spiel(spiel_id, sitzung)


# ── Ein Befund ────────────────────────────────────────────────────────────


@router.post("/befunde/{befund_id}/entscheidung", summary="Befund entscheiden")
async def entscheiden(
    befund_id: uuid.UUID, daten: EntscheidungSetzen, sitzung: DbSitzung
) -> BefundAusgabe:
    grund = entscheidung_pruefen(daten.art, daten.grund)
    gefunden = await speicher.entscheidung_setzen(sitzung, befund_id, daten.art, grund)
    vorhanden = await speicher.vorgang_zu_befund(sitzung, befund_id)
    return _befund(gefunden, vorhanden.id if vorhanden else None)


@router.delete("/befunde/{befund_id}/entscheidung", summary="Entscheidung zurücknehmen")
async def entscheidung_zuruecknehmen(befund_id: uuid.UUID, sitzung: DbSitzung) -> BefundAusgabe:
    """Der Befund ist wieder offen — und das Spiel damit nicht mehr abgehakt.

    Wer sich vertippt hat, soll das geradeziehen können, ohne den Bericht neu
    einzuspielen. Nur wenn zu dem Befund schon ein Schreiben **hinaus** ist,
    geht es nicht: der Verein hat es, und ein Befund, der hier wieder „offen"
    heißt, wäre eine Akte, die dem widerspricht.
    """
    vorhanden = await speicher.vorgang_zu_befund(sitzung, befund_id)
    darf_zurueckgenommen_werden(vorhanden.zustand if vorhanden else None)
    gefunden = await speicher.entscheidung_zuruecknehmen(sitzung, befund_id)
    return _befund(gefunden, vorhanden.id if vorhanden else None)


@router.get("/befunde", summary="Alle Befunde, flach")
async def alle_befunde(
    sitzung: DbSitzung,
    staffel_id: Annotated[uuid.UUID | None, Query(description="Nur diese Staffel")] = None,
    nur_offen: Annotated[bool, Query(description="Nur unentschiedene")] = False,
) -> list[BefundZeile]:
    """Die andere Frage: was ist in dieser Saison alles aufgelaufen.

    Die Warteschlange geht Spiel für Spiel; hier steht jeder Befund einzeln,
    mit dem Spiel an der Zeile — sonst wäre eine Zeile nicht zuzuordnen.
    """
    paare = await speicher.alle_befunde(sitzung, staffel_id, nur_offen)
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
        for k in await speicher.karten(sitzung, pass_nr, wettbewerb, seit)
    ]


@router.get("/einstellungen", summary="Einstellungen dieser Installation")
async def einstellungen(sitzung: DbSitzung) -> EinstellungenAusgabe:
    werte = await speicher.einstellungen(sitzung)
    return EinstellungenAusgabe(**asdict(werte))


@router.put("/einstellungen", summary="Einstellungen ändern")
async def einstellungen_setzen(
    daten: EinstellungenSetzen, sitzung: DbSitzung
) -> EinstellungenAusgabe:
    """Nur die mitgeschickten Felder. Ausgelassene bleiben stehen."""
    werte = await speicher.einstellungen_setzen(sitzung, daten)
    return EinstellungenAusgabe(**asdict(werte))


# ── Mannschaften einer Staffel ────────────────────────────────────────────


@router.get("/staffeln/{staffel_id}/mannschaften", summary="Mannschaften einer Staffel")
async def mannschaften(staffel_id: uuid.UUID, sitzung: DbSitzung) -> list[MannschaftAusgabe]:
    return [_mannschaft(m) for m in await speicher.mannschaften(sitzung, staffel_id)]


@router.put("/staffeln/{staffel_id}/mannschaften", summary="Mannschaften einer Staffel setzen")
async def mannschaften_setzen(
    staffel_id: uuid.UUID, daten: MannschaftenSetzen, sitzung: DbSitzung
) -> list[MannschaftAusgabe]:
    """Die Meldung als Ganzes.

    Wer die hoeheren Mannschaften mitschickt, bestaetigt sie damit -- ein
    spaeteres Einspielen aus DFBnet ueberschreibt sie dann nicht mehr.
    """
    gesetzt = await speicher.mannschaften_setzen(sitzung, staffel_id, daten.mannschaften)
    return [_mannschaft(m) for m in gesetzt]


# ── Vorgänge: Mahnung und Sportgerichtsfall ───────────────────────────────


@router.get("/vorgaenge", summary="Alle Vorgänge")
async def vorgaenge(
    sitzung: DbSitzung,
    zustand: Annotated[str | None, Query(description="Nur dieser Zustand")] = None,
) -> list[VorgangZeile]:
    return [VorgangZeile.model_validate(v) for v in await speicher.vorgaenge(sitzung, zustand)]


@router.get("/vorgaenge/{vorgang_id}", summary="Ein Vorgang mit seinem Text")
async def vorgang(vorgang_id: uuid.UUID, sitzung: DbSitzung) -> VorgangAusgabe:
    return _vorgang(await speicher.vorgang(sitzung, vorgang_id))


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


@router.get(
    "/vorgaenge/{vorgang_id}/mahnung.pdf",
    summary="Das ausgefüllte Mahnungsformular",
    response_class=Response,
    responses={200: {"content": {"application/pdf": {}}}},
)
async def vorgang_mahnung(vorgang_id: uuid.UUID, sitzung: DbSitzung) -> Response:
    """Der Vordruck des Verbandes, gefüllt aus Spiel, Befund und Einstellungen.

    **Verschickt wird nichts.** Das PDF geht an den Staffelleiter, der es
    prüft und selbst verschickt.

    Was nicht bekannt ist, bleibt leer -- die fehlenden Felder stehen im Kopf
    `X-Fehlende-Felder`, damit die Oberfläche sie nennen kann, ohne das PDF zu
    lesen. Ein Schriftstück an einen Verein trägt keine erfundenen Angaben.
    """
    vorgang, befund, spiel, staffel = await speicher.vorgang_mit_spiel(sitzung, vorgang_id)
    werte = await speicher.einstellungen(sitzung)

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
async def vorgang_mail(vorgang_id: uuid.UUID, sitzung: DbSitzung) -> MailEntwurf:
    """Betreff und Text, fertig zum Einfügen -- und wer als Empfänger passt.

    **Abgeschickt wird hier nichts**, und es gibt auch keinen Weg dorthin.
    Der Staffelleiter wählt den Empfänger und schickt in seinem Mailprogramm.

    Der Text ist der des Vorgangs: aus einer Vorlage entstanden, Wort für Wort
    vorhersagbar, ohne erzeugte Sprache.
    """
    vorgang, befund, spiel, staffel = await speicher.vorgang_mit_spiel(sitzung, vorgang_id)
    werte = await speicher.einstellungen(sitzung)

    fehlt: list[str] = []
    if vorgang.art == "mahnung":
        fehlt = _formular(vorgang, befund, spiel, staffel, werte.staffelleiter).fehlende_felder()

    return MailEntwurf(
        empfaenger=vorgang.empfaenger,
        betreff=vorgang.betreff
        or betreff_fuer(vorgang.aktenzeichen, spiel.heim, spiel.gast, spiel.datum),
        text=vorgang.text,
        anhang=f"/staffelpilot/vorgaenge/{vorgang_id}/mahnung.pdf"
        if vorgang.art == "mahnung"
        else "",
        fehlende_felder=fehlt,
    )


@router.patch("/vorgaenge/{vorgang_id}", summary="Text oder Empfänger eines Vorgangs ändern")
async def vorgang_aendern(
    vorgang_id: uuid.UUID, daten: VorgangAendern, sitzung: DbSitzung
) -> VorgangAusgabe:
    felder = daten.model_dump(exclude_none=True)
    return _vorgang(await speicher.vorgang_aendern(sitzung, vorgang_id, felder))


@router.post("/vorgaenge/{vorgang_id}/zustand", summary="Vorgang weiterstellen")
async def vorgang_zustand(
    vorgang_id: uuid.UUID, daten: ZustandSetzen, sitzung: DbSitzung
) -> VorgangAusgabe:
    """'versandt' heisst: ein Mensch hat es abgeschickt.

    Dieses Programm verschickt nichts und hat auch keinen Weg dorthin. Der
    Zustand haelt fest, was ausserhalb passiert ist.
    """
    return _vorgang(await speicher.vorgang_zustand(sitzung, vorgang_id, daten.zustand))


@router.delete(
    "/vorgaenge/{vorgang_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Vorgang verwerfen",
)
async def vorgang_loeschen(vorgang_id: uuid.UUID, sitzung: DbSitzung) -> None:
    await speicher.vorgang_loeschen(sitzung, vorgang_id)


@router.post(
    "/befunde/{befund_id}/vorgang",
    status_code=status.HTTP_201_CREATED,
    summary="Aus einem Befund einen Entwurf machen",
)
async def vorgang_anlegen(
    befund_id: uuid.UUID, daten: VorgangAnlegen, sitzung: DbSitzung
) -> VorgangAusgabe:
    """Erzeugt den Entwurf aus der Vorlage -- und verschickt ihn nicht.

    Die Art ergibt sich aus dem Weg des Befundes; ein Befund ohne Weg bekommt
    keinen Vorgang. Der Text entsteht genau einmal: wer ihn danach umschreibt,
    behaelt seine Fassung.
    """
    return _vorgang(await speicher.vorgang_anlegen(sitzung, befund_id, daten))


# ── Regelkatalog ──────────────────────────────────────────────────────────


def _regel(r: Regel) -> RegelAusgabe:
    return RegelAusgabe.model_validate(r)


@router.get("/regeln", summary="Was geprüft wird")
async def regeln(sitzung: DbSitzung) -> list[RegelAusgabe]:
    return [_regel(r) for r in await speicher.regeln(sitzung)]


@router.put("/regeln", summary="Den Regelkatalog einspielen")
async def regelkatalog_setzen(daten: RegelkatalogSetzen, sitzung: DbSitzung) -> list[RegelAusgabe]:
    """Der Prüfdienst meldet, was es gibt.

    Was er nicht mehr meldet, verschwindet -- ein Schalter für eine Regel, die
    niemand mehr prüft, verspricht etwas, das nicht passiert. Die Schalter der
    übrigen bleiben stehen: `aktiv` gehört dem Staffelleiter, nicht dem
    Katalog.
    """
    return [_regel(r) for r in await speicher.regelkatalog_setzen(sitzung, daten.regeln)]


@router.patch("/regeln/{regel_id}", summary="Eine Regel an- oder abschalten")
async def regel_umschalten(
    regel_id: uuid.UUID, daten: RegelUmschalten, sitzung: DbSitzung
) -> RegelAusgabe:
    """Die eine Entscheidung, die dem Staffelleiter gehört.

    Geprüft wird trotzdem im Prüfdienst -- der liest hier nach, was er melden
    soll. Dass eine abgeschaltete Regel keine Befunde mehr erzeugt, passiert
    dort und nicht hier.
    """
    return _regel(await speicher.regel_umschalten(sitzung, regel_id, daten.aktiv))


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


@router.get("/auftraege", summary="Prüfläufe und Initialisierungen")
async def auftraege(sitzung: DbSitzung) -> list[AuftragZeile]:
    return [AuftragZeile.model_validate(a) for a in await speicher.auftraege(sitzung)]


@router.get("/auftraege/offen", summary="Der Auftrag, der gerade läuft")
async def auftrag_offen(sitzung: DbSitzung) -> AuftragAusgabe | None:
    """`null`, wenn keiner unterwegs ist.

    Die Oberfläche fragt das im Sekundentakt ab; ein 404 wäre dort ein Fehler
    und kein Ergebnis, und die Konsole liefe damit voll.
    """
    offen = await speicher.offener_auftrag(sitzung)
    return AuftragAusgabe.model_validate(offen) if offen else None


@router.post("/auftraege", status_code=status.HTTP_201_CREATED, summary="Auftrag anfordern")
async def auftrag_anfordern(daten: AuftragAnfordern, sitzung: DbSitzung) -> AuftragAusgabe:
    """Einer nach dem anderen.

    Es gibt genau eine DFBnet-Sitzung. Zwei Läufe gleichzeitig hießen zwei
    Browser an derselben Anmeldung, und der zweite wirft den ersten hinaus —
    mitten in einem halb gelesenen Spielbericht.
    """
    darf_angefordert_werden(1 if await speicher.offener_auftrag(sitzung) else 0)
    return AuftragAusgabe.model_validate(
        await speicher.auftrag_anfordern(sitzung, daten.art, daten.staffel_id)
    )


@router.get("/auftraege/{auftrag_id}", summary="Ein Auftrag mit seinem Protokoll")
async def auftrag(auftrag_id: uuid.UUID, sitzung: DbSitzung) -> AuftragAusgabe:
    return AuftragAusgabe.model_validate(await speicher.auftrag(sitzung, auftrag_id))


@router.post("/auftraege/{auftrag_id}/fortschritt", summary="Fortschritt melden")
async def auftrag_fortschritt(
    auftrag_id: uuid.UUID, daten: Fortschritt, sitzung: DbSitzung
) -> AuftragAusgabe:
    """Vom Prüfdienst aufgerufen, nicht von der Oberfläche.

    Die erste Meldung setzt den Auftrag auf „läuft": dass er sich meldet,
    **ist** der Beleg dafür, dass er angefangen hat.
    """
    return AuftragAusgabe.model_validate(
        await speicher.auftrag_fortschreiben(sitzung, auftrag_id, daten)
    )


@router.post("/auftraege/{auftrag_id}/abschluss", summary="Auftrag beenden")
async def auftrag_abschliessen(
    auftrag_id: uuid.UUID, daten: Abschluss, sitzung: DbSitzung
) -> AuftragAusgabe:
    """Vom Prüfdienst — oder von der Oberfläche mit `abgebrochen`."""
    return AuftragAusgabe.model_validate(
        await speicher.auftrag_abschliessen(sitzung, auftrag_id, daten)
    )


# ── Übertragung nach DFBnet ───────────────────────────────────────────────
#
# **Hier wird nichts übertragen.** Diese Endpunkte führen eine Liste dessen,
# was in DFBnet einzutragen wäre. Eintragen würde es der DFBnet-Dienst — und
# der arbeitet nur, wenn die Übertragung nicht pausiert ist. Auf einer
# frischen Installation ist sie das: eine Freigabe in DFBnet ist eine Handlung
# nach außen, und die soll nicht passieren, weil jemand die Software zum
# ersten Mal gestartet hat.


@router.get("/uebertragungen", summary="Was nach DFBnet hinaus soll")
async def uebertragungen(sitzung: DbSitzung) -> UebertragungStand:
    werte = await speicher.einstellungen(sitzung)
    zahlen = await speicher.uebertragung_stand(sitzung)
    alle = await speicher.uebertragungen(sitzung)
    return UebertragungStand(
        pausiert=werte.uebertragung_pausiert,
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
    daten: UebertragungEinreihen, sitzung: DbSitzung
) -> UebertragungAusgabe:
    """Vormerken, nicht ausführen.

    Idempotent über `(aktion, referenz)`: abhaken, Haken entfernen und wieder
    abhaken darf keine zwei Freigaben erzeugen.
    """
    return UebertragungAusgabe.model_validate(await speicher.uebertragung_einreihen(sitzung, daten))


@router.post("/uebertragungen/pause", summary="Übertragung anhalten oder weiterlaufen lassen")
async def uebertragung_pause(daten: Pause, sitzung: DbSitzung) -> UebertragungStand:
    """Der eine Schalter, der entscheidet, ob draußen etwas passiert."""
    await speicher.einstellungen_setzen(
        sitzung, EinstellungenSetzen(uebertragung_pausiert=daten.pausiert)
    )
    return await uebertragungen(sitzung)


@router.post("/uebertragungen/wiederholen", summary="Gescheitertes zurück in die Schlange")
async def uebertragung_wiederholen(
    sitzung: DbSitzung,
    uebertragung_id: Annotated[
        uuid.UUID | None, Query(description="Nur diese; ohne Angabe alle gescheiterten")
    ] = None,
) -> UebertragungStand:
    """Nach einem Netzausfall stehen dort zwanzig Zeilen mit demselben Fehler.
    Die einzeln anzuklicken ist keine Arbeit, sondern eine Strafe."""
    await speicher.uebertragung_wiederholen(sitzung, uebertragung_id)
    return await uebertragungen(sitzung)


@router.post("/uebertragungen/naechste", summary="Die nächste offene übernehmen")
async def uebertragung_uebernehmen(sitzung: DbSitzung) -> UebertragungAusgabe | None:
    """Vom Prüfdienst aufgerufen. `null`, wenn nichts offen ist.

    Übernehmen und nicht nur lesen: sonst greifen zwei Dienste nach derselben
    Zeile und tragen dieselbe Freigabe zweimal in DFBnet ein.

    **Die Pause wird hier nicht geprüft.** Ob übertragen werden darf, steht im
    Stand, und der Dienst liest ihn — eine zweite Prüfung an dieser Stelle
    wäre dieselbe Regel an zwei Orten.
    """
    gefunden = await speicher.uebertragung_uebernehmen(sitzung)
    return UebertragungAusgabe.model_validate(gefunden) if gefunden else None


@router.post("/uebertragungen/{uebertragung_id}/abschluss", summary="Ergebnis melden")
async def uebertragung_abschliessen(
    uebertragung_id: uuid.UUID, daten: UebertragungAbschluss, sitzung: DbSitzung
) -> UebertragungAusgabe:
    """Vom DFBnet-Dienst aufgerufen, nicht von der Oberfläche."""
    return UebertragungAusgabe.model_validate(
        await speicher.uebertragung_abschliessen(sitzung, uebertragung_id, daten)
    )


# ── DFBnet-Zugang ─────────────────────────────────────────────────────────
#
# Das Passwort liegt verschlüsselt, mit einem Schlüssel aus der Umgebung
# (`STAFFELPILOT_SCHLUESSEL`) und nicht aus der Datenbank — ein Abzug allein
# ist damit wertlos. Es kommt an genau einer Stelle wieder heraus, und die
# verlangt die Rolle `verwalter`.
#
# Ohne Schlüssel wird **nichts** abgelegt. Lieber gar nicht speichern als ein
# Passwort im Klartext.

#: Nur wer die Staffel verwaltet, fasst die Zugangsdaten an. Ein Leser sieht
#: Spielberichte - er meldet sich nicht für die ganze Installation bei DFBnet
#: an.
NUR_VERWALTER = [erfordert("staffelpilot", Rolle.VERWALTER)]


@router.get("/zugang", summary="Ist ein DFBnet-Zugang hinterlegt?")
async def zugang_stand(sitzung: DbSitzung) -> ZugangStand:
    """Ein Ja oder Nein und der Benutzername. Mehr verrät diese Antwort nicht."""
    gespeichert, benutzer = await speicher.zugang_stand(sitzung)
    return ZugangStand(
        gespeichert=gespeichert,
        benutzer=benutzer,
        schluessel_vorhanden=speicher.schluessel_vorhanden(),
    )


@router.put(
    "/zugang",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=NUR_VERWALTER,
    summary="DFBnet-Zugang hinterlegen",
)
async def zugang_setzen(daten: ZugangSetzen, sitzung: DbSitzung) -> Response:
    """Das Passwort wird verschlüsselt abgelegt und kommt hier nie zurück.

    Fehlt der Schlüssel in der Umgebung, wird nichts gespeichert — die Antwort
    ist dann 503, weil das ein Betriebsproblem ist und kein Tippfehler.
    """
    await speicher.zugang_setzen(sitzung, daten)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.delete(
    "/zugang",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=NUR_VERWALTER,
    summary="DFBnet-Zugang entfernen",
)
async def zugang_loeschen(sitzung: DbSitzung) -> Response:
    await speicher.zugang_loeschen(sitzung)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post(
    "/zugang/abholen",
    dependencies=NUR_VERWALTER,
    summary="Zugangsdaten für den Prüfdienst",
)
async def zugang_abholen(sitzung: DbSitzung) -> ZugangGeheim:
    """Der einzige Ort, an dem das Passwort wieder herauskommt.

    `POST` und nicht `GET`: ein Geheimnis gehört nicht in eine Adresse, die
    ein Zwischenspeicher oder ein Protokoll mitschreibt.
    """
    benutzer, passwort = await speicher.zugang_abholen(sitzung)
    return ZugangGeheim(benutzer=benutzer, passwort=passwort)
