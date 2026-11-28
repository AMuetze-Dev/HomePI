"""HTTP-Schicht. Uebersetzt zwischen Anfrage und Fachlichkeit, sonst nichts.

Dieses Artefakt ist ``Zugang.OEFFENTLICH``: Mitspieler brauchen kein Konto,
genau wie die Besucher der Tischtennis-Tafel. Damit haengt die Pruefung NICHT
am Router, und jeder Endpunkt der Leitung traegt sein eigenes ``erfordert``.
``tests/unit/test_anmeldung.py`` geht alle Routen durch und kennt die offenen
namentlich - ein neuer Endpunkt ohne Pruefung macht die CI rot.

Spieler weisen sich mit einem Token im Cookie aus, eines je Runde:

* beim Beitritt erzeugt, 256 Bit aus ``secrets`` wie ein Sitzungstoken,
* ``httponly`` - ein XSS-Fund liefert es nicht,
* in der Datenbank nur als SHA-256.

Wer das Cookie verliert, bekommt von der Leitung einen Wiederkehrcode und
damit seinen Namen zurueck. Ueber den Namen allein kommt niemand hinein.

Weitere Regeln, die hier gelten:
  - summary= bei jedem Endpunkt: die generische Ansicht im Frontend zeigt ihn
  - feste Pfade VOR parametrisierten, sonst liest FastAPI das Wort als UUID
  - Fehler ueber eigene ServiceError-Klassen, nie HTTPException
  - Rueckgabetypen annotieren, sonst fehlt das OpenAPI-Schema
"""

from __future__ import annotations

import datetime as dt
import uuid
from dataclasses import dataclass
from typing import Annotated

from fastapi import APIRouter, Depends, Request, Response, status
from homepi_core.auth import Rolle, erfordert
from homepi_core.auth.dienst import neues_token
from homepi_core.auth.passwoerter import hashe_token
from homepi_core.deps import DbSitzung, Einstellungen
from pydantic import TypeAdapter

from . import dienst, speicher
from .modelle import Frage, Runde, Spieler
from .schemas import (
    AntwortEingabe,
    AntwortSicht,
    Beitritt,
    BildSichtbar,
    BuzzerSicht,
    BuzzerUrteil,
    EigeneAntwort,
    FrageAusgabe,
    FrageDaten,
    FrageEingabe,
    FrageWaehlen,
    Ich,
    KatalogAusgabe,
    KatalogDetail,
    KatalogEingabe,
    Korrektur,
    Phase,
    Platz,
    PunkteSetzen,
    Reihenfolge,
    RundeAnlegen,
    RundeAusgabe,
    Rundenstand,
    Rundenstatus,
    SpielerSicht,
    Steuerung,
    Uebersicht,
    Wiederkehrcode,
    Zeigen,
)

ARTEFAKT = "quiz"

#: Kataloge und laufende Runden ansehen.
LESEN = erfordert(ARTEFAKT, Rolle.LESER)
#: Fragen schreiben, Runden leiten - die eigentliche Arbeit am Quizabend.
LEITEN = erfordert(ARTEFAKT, Rolle.NUTZER)
#: Einen ganzen Katalog wegwerfen.
VERWALTEN = erfordert(ARTEFAKT, Rolle.VERWALTER)

COOKIE_PRAEFIX = "homepi_quiz_"
#: Ein Quizabend, nicht ein Konto: zwei Tage reichen fuer jede Runde, die
#: ueber Mitternacht geht.
COOKIE_DAUER = dt.timedelta(days=2)

_FRAGEDATEN: TypeAdapter[FrageDaten] = TypeAdapter(FrageDaten)

router = APIRouter()


def _jetzt() -> dt.datetime:
    return dt.datetime.now(dt.UTC)


# ------------------------------------------------------------- Spielertoken


@dataclass(slots=True)
class Zugriff:
    runde: Runde
    spieler: Spieler | None


def _cookie(code: str) -> str:
    return f"{COOKIE_PRAEFIX}{code}"


async def hole_zugriff(code: str, request: Request, sitzung: DbSitzung) -> Zugriff:
    """Die Runde zum Code und, falls das Cookie passt, der Spieler dazu."""
    runde = await speicher.runde_mit_code(sitzung, dienst.normalisiere_code(code))
    token = request.cookies.get(_cookie(runde.code))
    spieler = (
        await speicher.spieler_mit_token(sitzung, runde.id, hashe_token(token)) if token else None
    )
    return Zugriff(runde, spieler)


async def hole_spieler(zugriff: Annotated[Zugriff, Depends(hole_zugriff)]) -> Zugriff:
    if zugriff.spieler is None:
        raise dienst.NichtBeigetreten("Du bist dieser Runde noch nicht beigetreten.")
    return zugriff


RundenZugriff = Annotated[Zugriff, Depends(hole_zugriff)]
SpielerZugriff = Annotated[Zugriff, Depends(hole_spieler)]


def _setze_cookie(antwort: Response, code: str, token: str, einstellungen: Einstellungen) -> None:
    antwort.set_cookie(
        _cookie(code),
        token,
        max_age=int(COOKIE_DAUER.total_seconds()),
        httponly=True,
        secure=einstellungen.ist_produktion,
        samesite="lax",
        path="/",
    )


# ------------------------------------------------------------- Uebersetzung


def _frage_ausgabe(frage: Frage, bilder: set[uuid.UUID]) -> FrageAusgabe:
    return FrageAusgabe(
        id=frage.id,
        position=frage.position,
        text=frage.text,
        kategorie=frage.kategorie,
        punkte=frage.punkte,
        zeitlimit=frage.zeitlimit,
        hat_bild=frage.id in bilder,
        daten=_FRAGEDATEN.validate_python(frage.daten),
    )


async def _fragen(sitzung: DbSitzung, katalog_id: uuid.UUID) -> list[FrageAusgabe]:
    alle = await speicher.fragen(sitzung, katalog_id)
    bilder = await speicher.mit_bild(sitzung, [f.id for f in alle])
    return [_frage_ausgabe(f, bilder) for f in alle]


async def _katalog_detail(sitzung: DbSitzung, katalog_id: uuid.UUID) -> KatalogDetail:
    eintrag = await speicher.katalog(sitzung, katalog_id)
    fragen = await _fragen(sitzung, katalog_id)
    return KatalogDetail(
        id=eintrag.id,
        titel=eintrag.titel,
        beschreibung=eintrag.beschreibung,
        anzahl_fragen=len(fragen),
        geaendert=eintrag.geaendert,
        fragen=fragen,
    )


async def _runde_ausgabe(sitzung: DbSitzung, runde: Runde) -> RundeAusgabe:
    katalog = await speicher.katalog(sitzung, runde.katalog_id)
    return RundeAusgabe(
        id=runde.id,
        code=runde.code,
        katalog_id=runde.katalog_id,
        katalog_titel=katalog.titel,
        status=_status(runde),
        anzahl_spieler=await speicher.anzahl_spieler(sitzung, runde.id),
        angelegt=runde.angelegt,
    )


def _status(runde: Runde) -> Rundenstatus:
    return runde.status  # type: ignore[return-value]


def _phase(runde: Runde) -> Phase:
    return runde.phase  # type: ignore[return-value]


def _aktuelle(fragen: list[FrageAusgabe], runde: Runde) -> tuple[int, FrageAusgabe] | None:
    return next(((i, f) for i, f in enumerate(fragen) if f.id == runde.frage_id), None)


async def _rangliste(sitzung: DbSitzung, runde: Runde) -> tuple[list[Spieler], list[dienst.Rang]]:
    leute = await speicher.spieler_der_runde(sitzung, runde.id)
    punkte = await speicher.punktestaende(sitzung, runde.id)
    return leute, dienst.rangliste((s.id, s.name, punkte.get(s.id, 0)) for s in leute)


async def _steuerung(sitzung: DbSitzung, runde: Runde) -> Steuerung:
    jetzt = _jetzt()
    fragen = await _fragen(sitzung, runde.katalog_id)
    aktuell = _aktuelle(fragen, runde)
    leute, plaetze = await _rangliste(sitzung, runde)
    namen = {s.id: s.name for s in leute}
    gesehen = {s.id: s.zuletzt_gesehen for s in leute}

    antworten: list[AntwortSicht] = []
    buzzer: list[BuzzerSicht] = []
    if aktuell is not None:
        _, frage = aktuell
        for eintrag in await speicher.antworten(sitzung, runde.id, frage.id):
            antworten.append(
                AntwortSicht(
                    id=eintrag.id,
                    spieler_id=eintrag.spieler_id,
                    spieler=namen.get(eintrag.spieler_id, "?"),
                    anzeige=dienst.anzeige(frage.daten, eintrag.wert, frage.id),
                    eingeloggt=eintrag.eingeloggt,
                    punkte=eintrag.punkte,
                    richtig=eintrag.richtig,
                    wert=eintrag.wert,
                )
            )
        antworten.sort(key=lambda a: a.spieler.casefold())
        for position, druck in enumerate(
            await speicher.druecke(sitzung, runde.id, frage.id), start=1
        ):
            buzzer.append(
                BuzzerSicht(
                    spieler_id=druck.spieler_id,
                    spieler=namen.get(druck.spieler_id, "?"),
                    position=position,
                    urteil=druck.urteil,  # type: ignore[arg-type]
                )
            )

    return Steuerung(
        runde=await _runde_ausgabe(sitzung, runde),
        phase=_phase(runde),
        frage=aktuell[1] if aktuell else None,
        fragen=fragen,
        beantwortet=[uuid.UUID(f) for f in runde.erledigt],
        bild_sichtbar=runde.bild_sichtbar,
        frist=runde.frist,
        jetzt=jetzt,
        spieler=[
            SpielerSicht(
                id=platz.schluessel,  # type: ignore[arg-type]
                name=platz.name,
                punkte=platz.punkte,
                rang=platz.rang,
                zuletzt_gesehen=gesehen[platz.schluessel],  # type: ignore[index]
                verbunden=dienst.verbunden(gesehen[platz.schluessel], jetzt),  # type: ignore[index]
            )
            for platz in plaetze
        ],
        antworten=antworten,
        buzzer=buzzer,
    )


async def _rundenstand(sitzung: DbSitzung, runde: Runde, spieler: Spieler | None) -> Rundenstand:
    fragen = await _fragen(sitzung, runde.katalog_id)
    aktuell = _aktuelle(fragen, runde)
    _, plaetze = await _rangliste(sitzung, runde)
    phase = _phase(runde)

    sicht = None
    anzahl_antworten = 0
    dran: str | None = None
    druecke: list[tuple[uuid.UUID, str]] = []
    if aktuell is not None:
        index, frage = aktuell
        sicht = dienst.oeffentliche_frage(frage, index, len(fragen), phase)
        anzahl_antworten = await speicher.anzahl_antworten(sitzung, runde.id, frage.id)
        druecke = [
            (d.spieler_id, d.urteil) for d in await speicher.druecke(sitzung, runde.id, frage.id)
        ]
        wer = dienst.buzzer_dran(druecke)
        dran = next((p.name for p in plaetze if p.schluessel == wer), None)

    ich = None
    if spieler is not None:
        mein = next(p for p in plaetze if p.schluessel == spieler.id)
        antwort = None
        if aktuell is not None:
            eintrag = await speicher.antwort_von(sitzung, spieler.id, aktuell[1].id)
            if eintrag is not None:
                antwort = EigeneAntwort(
                    wert=eintrag.wert,
                    eingeloggt=eintrag.eingeloggt,
                    punkte=eintrag.punkte,
                    richtig=eintrag.richtig,
                )
        position = next(
            (i for i, (sid, _) in enumerate(druecke, start=1) if sid == spieler.id), None
        )
        ich = Ich(
            name=spieler.name,
            punkte=mein.punkte,
            rang=mein.rang,
            antwort=antwort,
            buzzer_position=position,
            buzzer_urteil=druecke[position - 1][1] if position else None,  # type: ignore[arg-type]
        )

    return Rundenstand(
        code=runde.code,
        titel=(await speicher.katalog(sitzung, runde.katalog_id)).titel,
        status=_status(runde),
        phase=phase,
        frage=sicht,
        bild_sichtbar=dienst.bild_oeffentlich(phase, runde.bild_sichtbar),
        frist=runde.frist,
        jetzt=_jetzt(),
        rangliste=[Platz(name=p.name, punkte=p.punkte, rang=p.rang) for p in plaetze],
        anzahl_antworten=anzahl_antworten,
        buzzer=dran,
        ich=ich,
    )


async def _aktuelle_frage(sitzung: DbSitzung, runde: Runde) -> FrageAusgabe:
    if runde.frage_id is None:
        raise dienst.AktionNichtMoeglich("Es ist noch keine Frage gewählt.")
    frage = await speicher.frage(sitzung, runde.frage_id)
    return _frage_ausgabe(frage, await speicher.mit_bild(sitzung, [frage.id]))


async def _auswerten(sitzung: DbSitzung, runde: Runde, frage: FrageAusgabe) -> None:
    eintraege = await speicher.antworten(sitzung, runde.id, frage.id)
    bewertungen = dienst.bewerte(
        frage.daten, frage.punkte, {e.id: e.wert for e in eintraege}, frage.id
    )
    for eintrag in eintraege:
        bewertung = bewertungen.get(eintrag.id)
        if bewertung is not None:
            eintrag.punkte, eintrag.richtig = bewertung.punkte, bewertung.richtig
    _erledigen(runde, frage.id)


def _erledigen(runde: Runde, frage_id: uuid.UUID) -> None:
    if str(frage_id) not in runde.erledigt:
        # Neue Liste statt append: SQLAlchemy bemerkt Aenderungen in einer
        # JSONB-Liste sonst nicht und schriebe nichts.
        runde.erledigt = [*runde.erledigt, str(frage_id)]


# ===================================================== offen: Spieler und Tafel


@router.get("/", summary="Überblick für die Kachel")
async def uebersicht(sitzung: DbSitzung) -> Uebersicht:
    return Uebersicht(laufende_runden=await speicher.anzahl_laufend(sitzung))


@router.get("/runden/{code}", summary="Stand der Runde für Spieler und Anzeigetafel")
async def rundenstand(zugriff: RundenZugriff, sitzung: DbSitzung) -> Rundenstand:
    if zugriff.spieler is not None and dienst.gesehen_aktualisieren(
        zugriff.spieler.zuletzt_gesehen, _jetzt()
    ):
        zugriff.spieler.zuletzt_gesehen = _jetzt()
    return await _rundenstand(sitzung, zugriff.runde, zugriff.spieler)


@router.get(
    "/runden/{code}/bild",
    summary="Bild der gezeigten Frage",
    response_class=Response,
    responses={200: {"content": {"image/*": {}}}},
)
async def oeffentliches_bild(zugriff: RundenZugriff, sitzung: DbSitzung) -> Response:
    runde = zugriff.runde
    if runde.frage_id is None or not dienst.bild_oeffentlich(_phase(runde), runde.bild_sichtbar):
        raise dienst.BildFehlt("Gerade wird kein Bild gezeigt.")
    bild = await speicher.bild(sitzung, runde.frage_id)
    if bild is None:
        raise dienst.BildFehlt("Gerade wird kein Bild gezeigt.")
    return Response(content=bild.inhalt, media_type=bild.mime)


@router.post("/runden/{code}/beitreten", summary="Mit eigenem Namen beitreten")
async def beitreten(
    daten: Beitritt,
    zugriff: RundenZugriff,
    antwort: Response,
    sitzung: DbSitzung,
    einstellungen: Einstellungen,
) -> Rundenstand:
    runde = zugriff.runde
    if zugriff.spieler is not None:
        # Schon dabei - ein zweiter Druck auf "Mitspielen" legt niemanden an.
        return await _rundenstand(sitzung, runde, zugriff.spieler)

    dienst.pruefe_beitritt(_status(runde))
    name, schluessel = dienst.pruefe_spielername(daten.name)
    token = neues_token()

    if daten.wiederkehrcode:
        spieler = await speicher.spieler_mit_name(sitzung, runde.id, schluessel)
        if spieler is None or not dienst.wiederkehr_erlaubt(
            spieler.wiederkehr_hash, spieler.wiederkehr_bis, daten.wiederkehrcode, _jetzt()
        ):
            raise dienst.WiederkehrUngueltig(
                "Der Code passt nicht zu diesem Namen oder ist abgelaufen."
            )
        # Das alte Token ist damit wertlos - wer das verlorene Handy findet,
        # spielt nicht weiter.
        spieler.token_hash = hashe_token(token)
        spieler.wiederkehr_hash = None
        spieler.wiederkehr_bis = None
    else:
        dienst.pruefe_spielerzahl(await speicher.anzahl_spieler(sitzung, runde.id))
        spieler = await speicher.spieler_anlegen(
            sitzung, runde.id, name, schluessel, hashe_token(token)
        )

    _setze_cookie(antwort, runde.code, token, einstellungen)
    return await _rundenstand(sitzung, runde, spieler)


@router.put("/runden/{code}/antwort", summary="Eigene Antwort abgeben oder ändern")
async def antworten(
    daten: AntwortEingabe, zugriff: SpielerZugriff, sitzung: DbSitzung
) -> Rundenstand:
    runde, spieler = zugriff.runde, zugriff.spieler
    assert spieler is not None
    frage = await _aktuelle_frage(sitzung, runde)
    dienst.pruefe_antwort_erlaubt(
        _status(runde), _phase(runde), frage.daten.typ, runde.frist, _jetzt()
    )
    wert = dienst.pruefe_antwort(frage.daten, daten, frage.id)
    await speicher.antwort_speichern(
        sitzung, runde.id, frage.id, spieler.id, wert, daten.eingeloggt
    )
    return await _rundenstand(sitzung, runde, spieler)


@router.post("/runden/{code}/buzzer", summary="Buzzer drücken")
async def buzzern(zugriff: SpielerZugriff, sitzung: DbSitzung) -> Rundenstand:
    runde, spieler = zugriff.runde, zugriff.spieler
    assert spieler is not None
    frage = await _aktuelle_frage(sitzung, runde)
    druecke = await speicher.druecke(sitzung, runde.id, frage.id)
    dienst.pruefe_buzzer_erlaubt(
        _status(runde),
        _phase(runde),
        frage.daten.typ,
        schon_gedrueckt=any(d.spieler_id == spieler.id for d in druecke),
    )
    await speicher.druecken(sitzung, runde.id, frage.id, spieler.id)
    return await _rundenstand(sitzung, runde, spieler)


# ===================================================== mit Konto: Kataloge


@router.get("/kataloge", summary="Alle Fragenkataloge", dependencies=[LESEN])
async def kataloge(sitzung: DbSitzung) -> list[KatalogAusgabe]:
    return [
        KatalogAusgabe(
            id=k.id,
            titel=k.titel,
            beschreibung=k.beschreibung,
            anzahl_fragen=n,
            geaendert=k.geaendert,
        )
        for k, n in await speicher.kataloge(sitzung)
    ]


@router.post(
    "/kataloge",
    status_code=status.HTTP_201_CREATED,
    summary="Katalog anlegen",
    dependencies=[LEITEN],
)
async def katalog_anlegen(daten: KatalogEingabe, sitzung: DbSitzung) -> KatalogDetail:
    eintrag = await speicher.katalog_anlegen(sitzung, daten)
    return await _katalog_detail(sitzung, eintrag.id)


@router.get(
    "/kataloge/{katalog_id}", summary="Katalog mit Fragen und Lösungen", dependencies=[LESEN]
)
async def katalog(katalog_id: uuid.UUID, sitzung: DbSitzung) -> KatalogDetail:
    return await _katalog_detail(sitzung, katalog_id)


@router.put("/kataloge/{katalog_id}", summary="Katalog umbenennen", dependencies=[LEITEN])
async def katalog_aendern(
    katalog_id: uuid.UUID, daten: KatalogEingabe, sitzung: DbSitzung
) -> KatalogDetail:
    await speicher.katalog_aendern(sitzung, await speicher.katalog(sitzung, katalog_id), daten)
    return await _katalog_detail(sitzung, katalog_id)


@router.delete(
    "/kataloge/{katalog_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Katalog samt beendeter Runden löschen",
    dependencies=[VERWALTEN],
)
async def katalog_loeschen(katalog_id: uuid.UUID, sitzung: DbSitzung) -> None:
    eintrag = await speicher.katalog(sitzung, katalog_id)
    dienst.pruefe_katalog_loeschbar(await speicher.laufende_runden_mit(sitzung, katalog_id))
    await speicher.katalog_loeschen(sitzung, eintrag)


@router.post(
    "/kataloge/{katalog_id}/fragen",
    status_code=status.HTTP_201_CREATED,
    summary="Frage anhängen",
    dependencies=[LEITEN],
)
async def frage_anlegen(
    katalog_id: uuid.UUID, daten: FrageEingabe, sitzung: DbSitzung
) -> FrageAusgabe:
    await speicher.katalog(sitzung, katalog_id)
    return _frage_ausgabe(await speicher.frage_anlegen(sitzung, katalog_id, daten), set())


@router.put(
    "/kataloge/{katalog_id}/reihenfolge", summary="Fragen umsortieren", dependencies=[LEITEN]
)
async def reihenfolge(
    katalog_id: uuid.UUID, daten: Reihenfolge, sitzung: DbSitzung
) -> KatalogDetail:
    vorhanden = [f.id for f in await speicher.fragen(sitzung, katalog_id)]
    dienst.pruefe_reihenfolge(vorhanden, daten.fragen)
    await speicher.reihenfolge_setzen(sitzung, daten.fragen)
    return await _katalog_detail(sitzung, katalog_id)


@router.put("/fragen/{frage_id}", summary="Frage ändern", dependencies=[LEITEN])
async def frage_aendern(
    frage_id: uuid.UUID, daten: FrageEingabe, sitzung: DbSitzung
) -> FrageAusgabe:
    eintrag = await speicher.frage(sitzung, frage_id)
    await speicher.frage_aendern(sitzung, eintrag, daten)
    return _frage_ausgabe(eintrag, await speicher.mit_bild(sitzung, [frage_id]))


@router.delete(
    "/fragen/{frage_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Frage löschen",
    dependencies=[LEITEN],
)
async def frage_loeschen(frage_id: uuid.UUID, sitzung: DbSitzung) -> None:
    await speicher.frage_loeschen(sitzung, await speicher.frage(sitzung, frage_id))


@router.get(
    "/fragen/{frage_id}/bild",
    summary="Bild einer Frage",
    response_class=Response,
    responses={200: {"content": {"image/*": {}}}},
    dependencies=[LESEN],
)
async def bild(frage_id: uuid.UUID, sitzung: DbSitzung) -> Response:
    eintrag = await speicher.bild(sitzung, frage_id)
    if eintrag is None:
        raise dienst.BildFehlt("Diese Frage hat kein Bild.")
    return Response(content=eintrag.inhalt, media_type=eintrag.mime)


@router.put(
    "/fragen/{frage_id}/bild",
    summary="Bild hochladen (Rohdaten mit Content-Type)",
    dependencies=[LEITEN],
    openapi_extra={
        "requestBody": {
            "required": True,
            "content": {"image/*": {"schema": {"type": "string", "format": "binary"}}},
        }
    },
)
async def bild_hochladen(frage_id: uuid.UUID, request: Request, sitzung: DbSitzung) -> FrageAusgabe:
    eintrag = await speicher.frage(sitzung, frage_id)
    angegeben = int(request.headers.get("content-length") or 0)
    # Vor dem Lesen: ein Bild mit angekuendigten 300 MB wird nicht erst in
    # den Speicher des Pi geladen, um dann abgelehnt zu werden.
    dienst.pruefe_bild(request.headers.get("content-type", ""), angegeben or 1)
    inhalt = await request.body()
    mime = dienst.pruefe_bild(request.headers.get("content-type", ""), len(inhalt))
    await speicher.bild_setzen(sitzung, frage_id, mime, inhalt)
    return _frage_ausgabe(eintrag, {frage_id})


@router.delete(
    "/fragen/{frage_id}/bild",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Bild entfernen",
    dependencies=[LEITEN],
)
async def bild_entfernen(frage_id: uuid.UUID, sitzung: DbSitzung) -> None:
    await speicher.frage(sitzung, frage_id)
    await speicher.bild_loeschen(sitzung, frage_id)


# ===================================================== mit Konto: Runden leiten


@router.get("/leitung", summary="Alle Runden", dependencies=[LESEN])
async def runden(sitzung: DbSitzung) -> list[RundeAusgabe]:
    return [
        RundeAusgabe(
            id=r.id,
            code=r.code,
            katalog_id=r.katalog_id,
            katalog_titel=titel,
            status=_status(r),
            anzahl_spieler=n,
            angelegt=r.angelegt,
        )
        for r, titel, n in await speicher.runden(sitzung)
    ]


@router.post(
    "/leitung",
    status_code=status.HTTP_201_CREATED,
    summary="Runde mit einem Katalog eröffnen",
    dependencies=[LEITEN],
)
async def runde_anlegen(daten: RundeAnlegen, sitzung: DbSitzung) -> RundeAusgabe:
    await speicher.katalog(sitzung, daten.katalog_id)
    dienst.pruefe_katalog_spielbar(len(await speicher.fragen(sitzung, daten.katalog_id)))
    return await _runde_ausgabe(sitzung, await speicher.runde_anlegen(sitzung, daten.katalog_id))


@router.get("/leitung/{runde_id}", summary="Steuerung einer Runde", dependencies=[LESEN])
async def steuerung(runde_id: uuid.UUID, sitzung: DbSitzung) -> Steuerung:
    return await _steuerung(sitzung, await speicher.runde(sitzung, runde_id))


@router.delete(
    "/leitung/{runde_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Runde löschen",
    dependencies=[LEITEN],
)
async def runde_loeschen(runde_id: uuid.UUID, sitzung: DbSitzung) -> None:
    await speicher.runde_loeschen(sitzung, await speicher.runde(sitzung, runde_id))


@router.post("/leitung/{runde_id}/frage", summary="Frage auswählen", dependencies=[LEITEN])
async def frage_waehlen(runde_id: uuid.UUID, daten: FrageWaehlen, sitzung: DbSitzung) -> Steuerung:
    runde = await speicher.runde(sitzung, runde_id)
    frage = await speicher.frage(sitzung, daten.frage_id)
    if frage.katalog_id != runde.katalog_id:
        raise dienst.FrageUnbekannt("Diese Frage gehört nicht zum Katalog der Runde.")
    dienst.naechste_phase(_status(runde), _phase(runde), "waehlen")
    runde.phase = dienst.phase_nach_wahl(erledigt=str(frage.id) in runde.erledigt)
    runde.status = "laeuft"
    runde.frage_id = frage.id
    runde.frist = None
    runde.bild_sichtbar = runde.phase == "aufgeloest" and bool(
        await speicher.mit_bild(sitzung, [frage.id])
    )
    await speicher.speichern(sitzung, runde)
    return await _steuerung(sitzung, runde)


@router.post(
    "/leitung/{runde_id}/zeigen", summary="Frage den Spielern zeigen", dependencies=[LEITEN]
)
async def zeigen(runde_id: uuid.UUID, daten: Zeigen, sitzung: DbSitzung) -> Steuerung:
    runde = await speicher.runde(sitzung, runde_id)
    frage = await _aktuelle_frage(sitzung, runde)
    runde.phase = dienst.naechste_phase(_status(runde), _phase(runde), "zeigen")
    dienst.pruefe_zeigbar(frage)
    runde.frist = dienst.frist_fuer(frage.zeitlimit, daten.timer, _jetzt())
    runde.bild_sichtbar = frage.hat_bild
    await speicher.speichern(sitzung, runde)
    return await _steuerung(sitzung, runde)


@router.post("/leitung/{runde_id}/sperren", summary="Eingabe sperren", dependencies=[LEITEN])
async def sperren(runde_id: uuid.UUID, sitzung: DbSitzung) -> Steuerung:
    runde = await speicher.runde(sitzung, runde_id)
    runde.phase = dienst.naechste_phase(_status(runde), _phase(runde), "sperren")
    runde.frist = None
    await speicher.speichern(sitzung, runde)
    return await _steuerung(sitzung, runde)


@router.post("/leitung/{runde_id}/oeffnen", summary="Eingabe wieder öffnen", dependencies=[LEITEN])
async def oeffnen(runde_id: uuid.UUID, sitzung: DbSitzung) -> Steuerung:
    runde = await speicher.runde(sitzung, runde_id)
    runde.phase = dienst.naechste_phase(_status(runde), _phase(runde), "oeffnen")
    runde.frist = None
    await speicher.speichern(sitzung, runde)
    return await _steuerung(sitzung, runde)


@router.post(
    "/leitung/{runde_id}/aufloesen",
    summary="Auflösen und Punkte vergeben",
    dependencies=[LEITEN],
)
async def aufloesen(runde_id: uuid.UUID, sitzung: DbSitzung) -> Steuerung:
    runde = await speicher.runde(sitzung, runde_id)
    frage = await _aktuelle_frage(sitzung, runde)
    runde.phase = dienst.naechste_phase(_status(runde), _phase(runde), "aufloesen")
    runde.frist = None
    await _auswerten(sitzung, runde, frage)
    await speicher.speichern(sitzung, runde)
    return await _steuerung(sitzung, runde)


@router.post(
    "/leitung/{runde_id}/bild", summary="Bild zeigen oder verbergen", dependencies=[LEITEN]
)
async def bild_umschalten(
    runde_id: uuid.UUID, daten: BildSichtbar, sitzung: DbSitzung
) -> Steuerung:
    runde = await speicher.runde(sitzung, runde_id)
    frage = await _aktuelle_frage(sitzung, runde)
    dienst.pruefe_bild_vorhanden(frage.hat_bild)
    runde.bild_sichtbar = daten.sichtbar
    await speicher.speichern(sitzung, runde)
    return await _steuerung(sitzung, runde)


@router.post(
    "/leitung/{runde_id}/buzzer", summary="Urteil über den, der dran ist", dependencies=[LEITEN]
)
async def buzzer_urteil(runde_id: uuid.UUID, daten: BuzzerUrteil, sitzung: DbSitzung) -> Steuerung:
    runde = await speicher.runde(sitzung, runde_id)
    frage = await _aktuelle_frage(sitzung, runde)
    druecke = await speicher.druecke(sitzung, runde.id, frage.id)
    dran = dienst.buzzer_dran([(d, d.urteil) for d in druecke])
    dienst.pruefe_buzzer_urteil(frage.daten.typ, _phase(runde), dran)
    assert dran is not None
    if daten.richtig:
        dran.urteil, dran.punkte = "richtig", frage.punkte
        runde.phase = dienst.naechste_phase(_status(runde), _phase(runde), "aufloesen")
        runde.frist = None
        _erledigen(runde, frage.id)
    else:
        # Der Naechste in der Reihe ist dran; wer noch nicht gedrueckt hat,
        # darf es jetzt noch.
        dran.urteil, dran.punkte = "falsch", 0
    await speicher.speichern(sitzung, runde)
    return await _steuerung(sitzung, runde)


@router.post(
    "/leitung/{runde_id}/buzzer/zuruecksetzen",
    summary="Buzzer freigeben (alle Drücke verwerfen)",
    dependencies=[LEITEN],
)
async def buzzer_zuruecksetzen(runde_id: uuid.UUID, sitzung: DbSitzung) -> Steuerung:
    runde = await speicher.runde(sitzung, runde_id)
    frage = await _aktuelle_frage(sitzung, runde)
    await speicher.buzzer_loeschen(sitzung, runde.id, frage.id)
    return await _steuerung(sitzung, runde)


@router.post("/leitung/{runde_id}/beenden", summary="Runde beenden", dependencies=[LEITEN])
async def beenden(runde_id: uuid.UUID, sitzung: DbSitzung) -> Steuerung:
    runde = await speicher.runde(sitzung, runde_id)
    vorher = _phase(runde)
    runde.phase = dienst.naechste_phase(_status(runde), vorher, "beenden")
    if runde.phase != vorher:
        # Eine offene Frage wird beim Beenden noch gewertet - sonst waeren
        # die Antworten der letzten Frage verloren.
        await _auswerten(sitzung, runde, await _aktuelle_frage(sitzung, runde))
    runde.status = "beendet"
    runde.frist = None
    await speicher.speichern(sitzung, runde)
    return await _steuerung(sitzung, runde)


@router.put(
    "/leitung/{runde_id}/antworten/{antwort_id}",
    summary="Punkte einer Antwort von Hand setzen",
    dependencies=[LEITEN],
)
async def antwort_bewerten(
    runde_id: uuid.UUID, antwort_id: uuid.UUID, daten: PunkteSetzen, sitzung: DbSitzung
) -> Steuerung:
    runde = await speicher.runde(sitzung, runde_id)
    eintrag = await speicher.antwort(sitzung, runde.id, antwort_id)
    eintrag.punkte = daten.punkte
    eintrag.richtig = daten.punkte > 0
    await speicher.speichern(sitzung, eintrag)
    return await _steuerung(sitzung, runde)


@router.post(
    "/leitung/{runde_id}/spieler/{spieler_id}/korrektur",
    summary="Punkte gutschreiben oder abziehen",
    dependencies=[LEITEN],
)
async def korrektur(
    runde_id: uuid.UUID, spieler_id: uuid.UUID, daten: Korrektur, sitzung: DbSitzung
) -> Steuerung:
    runde = await speicher.runde(sitzung, runde_id)
    await speicher.spieler(sitzung, runde.id, spieler_id)
    await speicher.korrektur_anlegen(sitzung, runde.id, spieler_id, daten.punkte, daten.grund)
    return await _steuerung(sitzung, runde)


@router.post(
    "/leitung/{runde_id}/spieler/{spieler_id}/wiederkehr",
    summary="Wiederkehrcode für ein verlorenes Gerät",
    dependencies=[LEITEN],
)
async def wiederkehr(
    runde_id: uuid.UUID, spieler_id: uuid.UUID, sitzung: DbSitzung
) -> Wiederkehrcode:
    eintrag = await speicher.spieler(sitzung, runde_id, spieler_id)
    code = dienst.neuer_wiederkehrcode()
    eintrag.wiederkehr_hash = hashe_token(code)
    eintrag.wiederkehr_bis = dienst.wiederkehr_gueltig_bis(_jetzt())
    await speicher.speichern(sitzung, eintrag)
    return Wiederkehrcode(code=code, gueltig_bis=eintrag.wiederkehr_bis)


@router.delete(
    "/leitung/{runde_id}/spieler/{spieler_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Spieler aus der Runde entfernen",
    dependencies=[LEITEN],
)
async def spieler_entfernen(runde_id: uuid.UUID, spieler_id: uuid.UUID, sitzung: DbSitzung) -> None:
    await speicher.spieler_loeschen(sitzung, await speicher.spieler(sitzung, runde_id, spieler_id))
