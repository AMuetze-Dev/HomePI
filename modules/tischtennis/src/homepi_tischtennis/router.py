"""HTTP-Schicht. Uebersetzt zwischen Anfrage und Fachlichkeit, sonst nichts.

Dieses Artefakt ist ``Zugang.OEFFENTLICH``: die Dashboard-Ansicht soll ohne
Anmeldung erreichbar sein, und zwar ueber die Kachel und nicht nur ueber
einen weitergegebenen Link. Damit haengt die Pruefung NICHT am Router, und
jeder schreibende Endpunkt braucht sein eigenes ``erfordert``.

Das ist die gefaehrlichere Bauweise - docs/11-anmeldung.md begruendet, warum
sonst die Pruefung am Router haengt: der vergessene Endpunkt ist der, der das
Loch reisst. Deshalb steht in tests/unit/test_anmeldung.py ein Test, der
**alle** Routen durchgeht und bei jeder schreibenden eine Abhaengigkeit
verlangt. Ein neuer Endpunkt ohne Pruefung macht die CI rot.

Weitere Regeln, die hier gelten:
  - summary= bei jedem Endpunkt: die generische Ansicht im Frontend zeigt ihn
  - feste Pfade VOR parametrisierten, sonst liest FastAPI das Wort als UUID
  - Fehler ueber eigene ServiceError-Klassen, nie HTTPException
  - Rueckgabetypen annotieren, sonst fehlt das OpenAPI-Schema
"""

from __future__ import annotations

import datetime as dt
import uuid
from collections.abc import Sequence

from fastapi import APIRouter, status
from homepi_core.auth import Rolle, erfordert
from homepi_core.deps import DbSitzung

from . import dienst, speicher
from .modelle import Gruppe, Spiel, Teilnehmer, Turnier
from .schemas import (
    Auslosung,
    AuswuerfelnAnfrage,
    Dashboard,
    ErgebnisEintragen,
    GruppeVorschau,
    PaarungVorschau,
    SpielAusgabe,
    SpielBeginnen,
    SpielVerschieben,
    TabelleAusgabe,
    TabellenzeileAusgabe,
    TeilnehmerAnlegen,
    TeilnehmerAusgabe,
    TischAusgabe,
    TurnierAnlegen,
    TurnierAusgabe,
    TurnierEinstellungen,
)

ARTEFAKT = "tischtennis"

#: Ergebnisse eintragen und Teilnehmer pflegen - die alltaegliche Arbeit am
#: Turniertag.
MITSCHREIBEN = erfordert(ARTEFAKT, Rolle.NUTZER)
#: Turnier anlegen, auswuerfeln, zuruecksetzen, loeschen. Das sind die
#: Handgriffe, die den ganzen Abend umwerfen koennen.
EINRICHTEN = erfordert(ARTEFAKT, Rolle.VERWALTER)

router = APIRouter()


# ------------------------------------------------------- Uebersetzung


def _turnier_ausgabe(
    lauf: Turnier, leute: Sequence[Teilnehmer], alle: Sequence[Spiel]
) -> TurnierAusgabe:
    ausgabe = TurnierAusgabe.model_validate(lauf)
    ausgabe.anzahl_teilnehmer = len(leute)
    ausgabe.anzahl_spiele = len(alle)
    ausgabe.offene_spiele = sum(1 for spiel in alle if spiel.zustand != "beendet")
    return ausgabe


def _teilnehmer_ausgabe(wer: Teilnehmer, gruppennamen: dict[uuid.UUID, str]) -> TeilnehmerAusgabe:
    return TeilnehmerAusgabe(
        id=wer.id,
        name=wer.name,
        notiz=wer.notiz,
        gruppe=gruppennamen.get(wer.gruppe_id) if wer.gruppe_id else None,
        freilose=wer.freilose,
    )


def _spiel_ausgabe(
    spiel: Spiel,
    namen: dict[uuid.UUID, str],
    gruppennamen: dict[uuid.UUID, str],
    plan: dict[str, dienst.Planzeile],
) -> SpielAusgabe:
    zeile = plan.get(str(spiel.id))

    return SpielAusgabe(
        id=spiel.id,
        nummer=spiel.nummer,
        phase=spiel.phase,  # type: ignore[arg-type]
        runde=spiel.runde,
        bezeichnung=spiel.bezeichnung,
        gruppe=gruppennamen.get(spiel.gruppe_id) if spiel.gruppe_id else None,
        heim_id=spiel.heim_id,
        gast_id=spiel.gast_id,
        heim=namen.get(spiel.heim_id) if spiel.heim_id else None,
        gast=namen.get(spiel.gast_id) if spiel.gast_id else None,
        heim_herkunft=_herkunft(
            spiel.heim_id, spiel.heim_aus_spiel, spiel.freilos, spiel.heim_aus_verlierer
        ),
        gast_herkunft=_herkunft(
            spiel.gast_id, spiel.gast_aus_spiel, spiel.freilos, spiel.gast_aus_verlierer
        ),
        zustand=spiel.zustand,  # type: ignore[arg-type]
        tisch=spiel.tisch if spiel.tisch is not None else (zeile.tisch if zeile else None),
        sieger_id=spiel.sieger_id,
        freilos=spiel.freilos,
        begonnen_am=spiel.begonnen_am,
        beendet_am=spiel.beendet_am,
        erwartet_ab=zeile.erwartet_ab if zeile and not zeile.laeuft else None,
        gleich_dran=bool(zeile and zeile.gleich_dran),
    )


def _herkunft(
    teilnehmer_id: uuid.UUID | None,
    aus_spiel: int | None,
    freilos: bool,
    aus_verlierer: bool = False,
) -> str | None:
    """Was anstelle des Namens steht, solange der Gegner nicht feststeht.

    Im Doppel-KO laeuft hier auch ein Verlierer ein - und dann muss genau das
    dastehen. "Sieger aus Spiel 7" an einem Platz, auf den der Verlierer
    kommt, wuere das Raster an der Wand unlesbar machen.
    """
    if teilnehmer_id is not None:
        return None
    if freilos:
        return "Freilos"
    if aus_spiel is not None:
        wer = "Verlierer" if aus_verlierer else "Sieger"
        return f"{wer} aus Spiel {aus_spiel}"
    return "offen"


def _tabellen_ausgabe(
    lauf: Turnier,
    alle: Sequence[Spiel],
    leute: Sequence[Teilnehmer],
    gruppenliste: Sequence[Gruppe],
) -> list[TabelleAusgabe]:
    namen = {str(wer.id): wer.name for wer in leute}
    kennungen = {str(wer.id): wer.id for wer in leute}

    return [
        TabelleAusgabe(
            titel=titel,
            zeilen=[
                TabellenzeileAusgabe(
                    platz=zeile.platz,
                    teilnehmer_id=kennungen.get(zeile.teilnehmer),
                    teilnehmer=namen.get(zeile.teilnehmer, "?"),
                    spiele=zeile.spiele,
                    siege=zeile.siege,
                    niederlagen=zeile.niederlagen,
                    punkte=zeile.punkte,
                )
                for zeile in zeilen
            ],
            entscheidung_offen=[namen.get(wer, "?") for wer in offen],
        )
        for titel, zeilen, offen in speicher.tabellen_daten(lauf, alle, leute, gruppenliste)
    ]


async def _alles(
    sitzung: DbSitzung, turnier_id: uuid.UUID
) -> tuple[Turnier, list[Teilnehmer], list[Gruppe], list[Spiel], dict[str, dienst.Planzeile]]:
    """Ein Turnier mit allem, was die Ansichten brauchen - und dem Zeitplan.

    Vier Abfragen in einer Funktion, weil jede Ansicht dieselben vier
    braucht: ohne Teilnehmer keine Namen, ohne Gruppen keine Tabellen, ohne
    Spiele kein Plan.
    """
    lauf = await speicher.turnier(sitzung, turnier_id)
    leute = await speicher.teilnehmer(sitzung, turnier_id)
    gruppenliste = await speicher.gruppen(sitzung, turnier_id)
    alle = await speicher.spiele(sitzung, turnier_id)

    plan = {
        zeile.spiel: zeile
        for zeile in dienst.planen(
            speicher.planzeilen(alle),
            tische=lauf.tische,
            minuten=lauf.minuten_pro_spiel,
            jetzt=speicher.jetzt(),
        )
    }
    return lauf, leute, gruppenliste, alle, plan


# ------------------------------------------------------- oeffentlich lesend


@router.get("/", summary="Alle Turniere")
async def liste(sitzung: DbSitzung) -> list[TurnierAusgabe]:
    ausgabe: list[TurnierAusgabe] = []
    for lauf in await speicher.turniere(sitzung):
        leute = await speicher.teilnehmer(sitzung, lauf.id)
        alle = await speicher.spiele(sitzung, lauf.id)
        ausgabe.append(_turnier_ausgabe(lauf, leute, alle))
    return ausgabe


@router.get("/dashboard", summary="Oeffentliche Ansicht des laufenden Turniers")
async def dashboard(sitzung: DbSitzung) -> Dashboard:
    """Die Ansicht, fuer die dieses Artefakt oeffentlich ist.

    Ohne Anmeldung erreichbar und in einem Abruf vollstaendig: wer gerade
    spielt, wer als naechstes dran ist, wie die anderen gespielt haben.
    """
    lauf = await speicher.aktives_turnier(sitzung)
    if lauf is None:
        return Dashboard(stand=speicher.jetzt())
    return await _dashboard(sitzung, lauf.id)


@router.get("/turnier/{turnier_id}", summary="Ein Turnier")
async def eines(turnier_id: uuid.UUID, sitzung: DbSitzung) -> TurnierAusgabe:
    lauf, leute, _, alle, _ = await _alles(sitzung, turnier_id)
    return _turnier_ausgabe(lauf, leute, alle)


@router.get("/turnier/{turnier_id}/dashboard", summary="Oeffentliche Ansicht eines Turniers")
async def dashboard_eines(turnier_id: uuid.UUID, sitzung: DbSitzung) -> Dashboard:
    return await _dashboard(sitzung, turnier_id)


@router.get("/turnier/{turnier_id}/teilnehmer", summary="Teilnehmer eines Turniers")
async def teilnehmerliste(turnier_id: uuid.UUID, sitzung: DbSitzung) -> list[TeilnehmerAusgabe]:
    _, leute, gruppenliste, _, _ = await _alles(sitzung, turnier_id)
    gruppennamen = {gruppe.id: gruppe.name for gruppe in gruppenliste}
    return [_teilnehmer_ausgabe(wer, gruppennamen) for wer in leute]


@router.get("/turnier/{turnier_id}/spiele", summary="Spielplan eines Turniers")
async def spielplan(turnier_id: uuid.UUID, sitzung: DbSitzung) -> list[SpielAusgabe]:
    _, leute, gruppenliste, alle, plan = await _alles(sitzung, turnier_id)
    namen = {wer.id: wer.name for wer in leute}
    gruppennamen = {gruppe.id: gruppe.name for gruppe in gruppenliste}
    return [_spiel_ausgabe(spiel, namen, gruppennamen, plan) for spiel in alle]


@router.get("/turnier/{turnier_id}/tabellen", summary="Tabellen eines Turniers")
async def tabellen(turnier_id: uuid.UUID, sitzung: DbSitzung) -> list[TabelleAusgabe]:
    lauf, leute, gruppenliste, alle, _ = await _alles(sitzung, turnier_id)
    return _tabellen_ausgabe(lauf, alle, leute, gruppenliste)


async def _dashboard(sitzung: DbSitzung, turnier_id: uuid.UUID) -> Dashboard:
    lauf, leute, gruppenliste, alle, plan = await _alles(sitzung, turnier_id)
    namen = {wer.id: wer.name for wer in leute}
    gruppennamen = {gruppe.id: gruppe.name for gruppe in gruppenliste}

    ausgaben = [_spiel_ausgabe(spiel, namen, gruppennamen, plan) for spiel in alle]
    offen = sorted(
        (
            spiel
            for spiel in ausgaben
            if spiel.zustand != "beendet" and spiel.erwartet_ab is not None
        ),
        key=lambda spiel: (spiel.erwartet_ab or dt.datetime.max, spiel.nummer),
    )
    laufend = [spiel for spiel in ausgaben if spiel.zustand == "laeuft"]

    tische = [
        _tisch_ausgabe(nummer, laufend, offen) for nummer in range(1, max(1, lauf.tische) + 1)
    ]

    return Dashboard(
        turnier=_turnier_ausgabe(lauf, leute, alle),
        stand=speicher.jetzt(),
        tische=tische,
        spiele=ausgaben,
        naechste=offen[:8],
        letzte=sorted(
            (spiel for spiel in ausgaben if spiel.zustand == "beendet" and not spiel.freilos),
            key=lambda spiel: (spiel.beendet_am or dt.datetime.min, spiel.nummer),
            reverse=True,
        )[:6],
        tabellen=_tabellen_ausgabe(lauf, alle, leute, gruppenliste),
        teilnehmer=[_teilnehmer_ausgabe(wer, gruppennamen) for wer in leute],
        fertig=lauf.zustand == "beendet",
    )


def _tisch_ausgabe(
    nummer: int, laufend: Sequence[SpielAusgabe], offen: Sequence[SpielAusgabe]
) -> TischAusgabe:
    return TischAusgabe(
        tisch=nummer,
        laeuft=next((spiel for spiel in laufend if spiel.tisch == nummer), None),
        danach=[spiel for spiel in offen if spiel.tisch == nummer and spiel.zustand != "laeuft"][
            :2
        ],
    )


# ------------------------------------------------------------ Turnier fuehren


@router.post(
    "/turnier",
    status_code=status.HTTP_201_CREATED,
    summary="Turnier anlegen",
    dependencies=[EINRICHTEN],
)
async def anlegen(daten: TurnierAnlegen, sitzung: DbSitzung) -> TurnierAusgabe:
    lauf = await speicher.turnier_anlegen(sitzung, daten)
    return _turnier_ausgabe(lauf, [], [])


@router.put("/turnier/{turnier_id}", summary="Einstellungen aendern", dependencies=[EINRICHTEN])
async def aendern(
    turnier_id: uuid.UUID, daten: TurnierEinstellungen, sitzung: DbSitzung
) -> TurnierAusgabe:
    lauf = await speicher.turnier_aendern(sitzung, turnier_id, daten)
    leute = await speicher.teilnehmer(sitzung, turnier_id)
    alle = await speicher.spiele(sitzung, turnier_id)
    return _turnier_ausgabe(lauf, leute, alle)


@router.delete(
    "/turnier/{turnier_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Turnier loeschen",
    dependencies=[EINRICHTEN],
)
async def loeschen(turnier_id: uuid.UUID, sitzung: DbSitzung) -> None:
    await speicher.turnier_loeschen(sitzung, turnier_id)


@router.post(
    "/turnier/{turnier_id}/auslosung",
    summary="Auslosung vorschlagen, ohne sie zu speichern",
    dependencies=[EINRICHTEN],
)
async def auslosen(
    turnier_id: uuid.UUID, daten: AuswuerfelnAnfrage, sitzung: DbSitzung
) -> Auslosung:
    """Der Wuerfel. Speichert nichts - deshalb geht "nochmal" beliebig oft."""
    lauf, nach_kennung, plan, saat = await speicher.plan_vorschlag(sitzung, turnier_id, daten.saat)
    name = {kennung: wer.name for kennung, wer in nach_kennung.items()}

    anzahl = len(plan.begegnungen) + len(plan.ko)
    dauer = dienst.geschaetzte_dauer(anzahl, lauf.tische, lauf.minuten_pro_spiel)

    gruppen = [
        GruppeVorschau(
            name=f"Gruppe {speicher.GRUPPENNAMEN[index]}",
            teilnehmer=[name[kennung] for kennung in mitglieder],
        )
        for index, mitglieder in enumerate(plan.gruppen)
    ]
    paarungen = [
        PaarungVorschau(
            bezeichnung=(
                f"Gruppe {speicher.GRUPPENNAMEN[begegnung.gruppe]}, Runde {begegnung.runde}"
                if begegnung.gruppe is not None
                else f"Runde {begegnung.runde}"
            ),
            heim=name[begegnung.heim],
            gast=name[begegnung.gast],
        )
        for begegnung in plan.begegnungen
    ]
    runden_im_raster = max((spiel.runde for spiel in plan.ko), default=0)
    paarungen += [
        PaarungVorschau(
            bezeichnung=dienst.ko_bezeichnung(spiel.runde, runden_im_raster),
            heim=name.get(spiel.heim.teilnehmer or "", f"Sieger aus Spiel {spiel.heim.aus_spiel}"),
            gast=name.get(spiel.gast.teilnehmer or "", f"Sieger aus Spiel {spiel.gast.aus_spiel}"),
        )
        for spiel in plan.ko
    ]

    return Auslosung(
        saat=saat,
        modus=lauf.modus,  # type: ignore[arg-type]
        gruppen=gruppen,
        paarungen=paarungen,
        anzahl_spiele=anzahl,
        dauer_minuten=int(dauer.total_seconds() // 60),
        hinweis=(f"Freilos in Runde 1: {name[plan.freilos]}" if plan.freilos is not None else ""),
    )


@router.post(
    "/turnier/{turnier_id}/auswuerfeln",
    summary="Auslosung festschreiben und Turnier starten",
    dependencies=[EINRICHTEN],
)
async def auswuerfeln(
    turnier_id: uuid.UUID, daten: AuswuerfelnAnfrage, sitzung: DbSitzung
) -> TurnierAusgabe:
    lauf = await speicher.auswuerfeln(sitzung, turnier_id, daten.saat)
    leute = await speicher.teilnehmer(sitzung, turnier_id)
    alle = await speicher.spiele(sitzung, turnier_id)
    return _turnier_ausgabe(lauf, leute, alle)


@router.post(
    "/turnier/{turnier_id}/naechste-runde",
    summary="Naechste Runde oder KO-Raster ansetzen",
    dependencies=[EINRICHTEN],
)
async def naechste_runde(turnier_id: uuid.UUID, sitzung: DbSitzung) -> TurnierAusgabe:
    lauf = await speicher.naechste_runde(sitzung, turnier_id)
    leute = await speicher.teilnehmer(sitzung, turnier_id)
    alle = await speicher.spiele(sitzung, turnier_id)
    return _turnier_ausgabe(lauf, leute, alle)


@router.post(
    "/turnier/{turnier_id}/zuruecksetzen",
    summary="Spielplan verwerfen und zurueck in die Planung",
    dependencies=[EINRICHTEN],
)
async def zuruecksetzen(turnier_id: uuid.UUID, sitzung: DbSitzung) -> TurnierAusgabe:
    lauf = await speicher.zuruecksetzen(sitzung, turnier_id)
    leute = await speicher.teilnehmer(sitzung, turnier_id)
    return _turnier_ausgabe(lauf, leute, [])


@router.post("/turnier/{turnier_id}/beenden", summary="Turnier beenden", dependencies=[EINRICHTEN])
async def beenden(turnier_id: uuid.UUID, sitzung: DbSitzung) -> TurnierAusgabe:
    lauf = await speicher.turnier_beenden(sitzung, turnier_id)
    leute = await speicher.teilnehmer(sitzung, turnier_id)
    alle = await speicher.spiele(sitzung, turnier_id)
    return _turnier_ausgabe(lauf, leute, alle)


# --------------------------------------------------------------- Teilnehmer


@router.post(
    "/turnier/{turnier_id}/teilnehmer",
    status_code=status.HTTP_201_CREATED,
    summary="Teilnehmer eintragen",
    dependencies=[MITSCHREIBEN],
)
async def teilnehmer_anlegen(
    turnier_id: uuid.UUID, daten: TeilnehmerAnlegen, sitzung: DbSitzung
) -> TeilnehmerAusgabe:
    wer = await speicher.teilnehmer_anlegen(sitzung, turnier_id, daten)
    return _teilnehmer_ausgabe(wer, {})


@router.put(
    "/teilnehmer/{teilnehmer_id}", summary="Teilnehmer aendern", dependencies=[MITSCHREIBEN]
)
async def teilnehmer_aendern(
    teilnehmer_id: uuid.UUID, daten: TeilnehmerAnlegen, sitzung: DbSitzung
) -> TeilnehmerAusgabe:
    wer = await speicher.teilnehmer_aendern(sitzung, teilnehmer_id, daten)
    return _teilnehmer_ausgabe(wer, {})


@router.delete(
    "/teilnehmer/{teilnehmer_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Teilnehmer entfernen",
    dependencies=[MITSCHREIBEN],
)
async def teilnehmer_loeschen(teilnehmer_id: uuid.UUID, sitzung: DbSitzung) -> None:
    await speicher.teilnehmer_loeschen(sitzung, teilnehmer_id)


# -------------------------------------------------------------------- Spiele


@router.post("/spiel/{spiel_id}/beginnen", summary="Spiel beginnen", dependencies=[MITSCHREIBEN])
async def spiel_beginnen(
    spiel_id: uuid.UUID, daten: SpielBeginnen, sitzung: DbSitzung
) -> SpielAusgabe:
    spiel = await speicher.spiel_beginnen(sitzung, spiel_id, daten.tisch)
    return await _ein_spiel_ausgabe(sitzung, spiel)


@router.post(
    "/spiel/{spiel_id}/verschieben",
    summary="Spiel in der Warteschlange verschieben",
    dependencies=[MITSCHREIBEN],
)
async def spiel_verschieben(
    spiel_id: uuid.UUID, daten: SpielVerschieben, sitzung: DbSitzung
) -> SpielAusgabe:
    """Ein Spiel einen Platz nach vorn oder nach hinten.

    Wer gerade nicht da ist, haelt sonst den ganzen Plan auf. Trotzdem
    anzupfeifen waere die schlechtere Loesung: dann stimmt die Warteschlange
    im Dashboard nicht mehr, und die Glocke laeutet beim Falschen.
    """
    spiel = await speicher.spiel_verschieben(sitzung, spiel_id, daten.richtung)
    return await _ein_spiel_ausgabe(sitzung, spiel)


@router.put("/spiel/{spiel_id}/ergebnis", summary="Ergebnis eintragen", dependencies=[MITSCHREIBEN])
async def ergebnis_eintragen(
    spiel_id: uuid.UUID, daten: ErgebnisEintragen, sitzung: DbSitzung
) -> SpielAusgabe:
    """Den Sieger eintragen - das ist das ganze Ergebnis.

    Der Sieger rueckt im Raster auf, und steht danach jemand punktgleich an
    der Grenze, erscheint das Entscheidungsspiel von selbst im Plan.
    """
    spiel = await speicher.ergebnis_eintragen(sitzung, spiel_id, daten)
    return await _ein_spiel_ausgabe(sitzung, spiel)


@router.delete(
    "/spiel/{spiel_id}/ergebnis",
    summary="Ergebnis zuruecknehmen",
    dependencies=[MITSCHREIBEN],
)
async def ergebnis_zuruecknehmen(spiel_id: uuid.UUID, sitzung: DbSitzung) -> SpielAusgabe:
    """Korrektur. Nimmt mit, was daran hing: ein Folgespiel, das mit dem
    falschen Sieger schon gewertet war, wird ebenfalls offen."""
    spiel = await speicher.ergebnis_zuruecknehmen(sitzung, spiel_id)
    return await _ein_spiel_ausgabe(sitzung, spiel)


async def _ein_spiel_ausgabe(sitzung: DbSitzung, spiel: Spiel) -> SpielAusgabe:
    _, leute, gruppenliste, _, plan = await _alles(sitzung, spiel.turnier_id)
    return _spiel_ausgabe(
        spiel,
        {wer.id: wer.name for wer in leute},
        {gruppe.id: gruppe.name for gruppe in gruppenliste},
        plan,
    )
