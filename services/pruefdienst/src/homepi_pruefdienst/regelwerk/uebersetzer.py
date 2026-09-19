"""Vom `MatchReport` des Extractors zum `Spiel`, das eine Regel liest.

Diese Datei ist die einzige Stelle, die beide Welten kennt. Ändert DFBnet ein
Feld, ändert sich hier eine Zeile — und keine einzige Regel.

Das ist der eigentliche Zweck der Trennung: die Regeldatei gehört dem
Staffelleiter und soll Bestand haben. Sie darf nicht davon abhängen, dass ein
Kartentyp in DFBnet „Gelb-Rote Karte" heißt und nicht „Gelb/Rot".

Karten werden hier den Personen zugeordnet. Im Spielbericht stehen sie in einer
eigenen Liste mit dem Namen als Text; für eine Regel ist die Frage aber immer
„welche Karten hat diese Person", nie „welche Karten gab es".
"""

from __future__ import annotations

import logging
from datetime import datetime

from .spiel import (
    Einsatz,
    Karte,
    Mannschaft,
    Person,
    Spiel,
    Staffel,
    Tor,
    Wechsel,
    datum_lesen,
    wettbewerbskategorie,
)

logger = logging.getLogger(__name__)


def _minute(wert) -> int | None:
    text = str(wert or "").strip().rstrip(".").replace("'", "")
    if "+" in text:  # Nachspielzeit: "45+2" ist Minute 45
        text = text.split("+", 1)[0]
    try:
        return int(text)
    except ValueError:
        return None


def _norm(name: str) -> str:
    """Zum Vergleich von Namen aus zwei verschiedenen Tabellen."""
    return " ".join((name or "").split()).casefold()


def _karten_je_person(report) -> dict[str, list[Karte]]:
    zuordnung: dict[str, list[Karte]] = {}
    for ereignis in report.cards or []:
        karte = Karte(
            art=ereignis.card_type or "",
            minute=_minute(ereignis.minute),
            person=ereignis.player or "",
            mannschaft=ereignis.team or "",
            grund=getattr(ereignis, "reason", "") or "",
            personenart=getattr(ereignis, "person_kind", "spieler") or "spieler",
        )
        zuordnung.setdefault(_norm(karte.person), []).append(karte)
    return zuordnung


def _einsaetze(spieler) -> tuple[Einsatz, ...]:
    historie = getattr(spieler, "season_appearances", None)
    if historie is None:
        return ()
    return tuple(
        Einsatz(
            spielkennung=eintrag.match_id or "",
            datum=datum_lesen((eintrag.kickoff or "")[:10]),
            heim=eintrag.home_team or "",
            gast=eintrag.away_team or "",
            spielklasse=eintrag.division or "",
            wettbewerb=eintrag.competition or "",
            minuten=int(eintrag.minutes or 0),
            spieltag=eintrag.match_day,
        )
        for eintrag in (historie.matches or [])
    )


def _person(spieler, aufstellung: str, spieltag, karten, umfeld) -> Person:
    return Person(
        name=spieler.name or "",
        pass_nr=getattr(spieler, "pass_number", "") or "",
        trikot=getattr(spieler, "jersey_number", "") or "",
        geburtsdatum=datum_lesen(getattr(spieler, "birthdate", "")),
        aufstellung=aufstellung,
        ist_torwart=bool(getattr(spieler, "is_goalkeeper", False)),
        kennzeichen=tuple(sorted({(b or "").lower() for b in (spieler.badges or [])})),
        karten=tuple(karten.get(_norm(spieler.name), [])),
        einsaetze=_einsaetze(spieler),
        # § 67 (2) und (3): DFBnet liefert das Foto samt Zeitstempel in der
        # Aufstellung. Fehlt das Feld, bleibt der Zustand leer — und die
        # Fotoregeln schweigen, statt Unwissen zu melden.
        _foto_zustand=getattr(spieler, "photo_state", "") or "",
        foto_stand=datum_lesen(getattr(spieler, "photo_timestamp", "")),
        ist_spielfuehrer=bool(getattr(spieler, "is_captain", False)),
        _einsatzart=getattr(spieler, "match_status", "") or "",
        _altersklasse=umfeld[2],
        # Spielrecht: `None` bleibt `None`. Ein `or False` an dieser Stelle
        # würde aus „weiß ich nicht" ein „nein" machen — und damit aus jedem
        # älteren gespeicherten Bericht einen Kader ohne Spielrecht.
        spielrecht_mannschaft=getattr(spieler, "eligible_for_team", None),
        spielrecht_verein=getattr(spieler, "eligible_for_club", None),
        pflichtspielrecht_ab=datum_lesen(getattr(spieler, "competitive_from", "")),
        meisterschaftsrecht_ab=datum_lesen(getattr(spieler, "championship_from", "")),
        ohne_meisterschaftsrecht=getattr(spieler, "no_championship_eligibility", None),
        gastspielrecht=getattr(spieler, "guest_eligibility", None),
        zweitspielrecht=getattr(spieler, "second_eligibility", None),
        sperrvermerk=(getattr(spieler, "suspension_note", "") or "").strip(),
        _spieltag=spieltag,
        _auskunft=umfeld[0],
        _wettbewerb=umfeld[1],
    )


def _betreuer(offizieller, spieltag, karten, umfeld) -> Person:
    # Betreuer haben keine Passnummer. § 58 nennt sie gleichrangig, aber der
    # Verwarnungszähler der Datenbank hängt an der Passnummer — deshalb
    # bekommen sie die Auskunft zwar, liefern aber `None` statt einer Zahl,
    # die zu irgendjemandem gehören könnte.
    return Person(
        name=offizieller.name or "",
        aufstellung="betreuer",
        rollen=tuple(offizieller.roles or []),
        karten=tuple(karten.get(_norm(offizieller.name), [])),
        _spieltag=spieltag,
        _auskunft=umfeld[0],
        _wettbewerb=umfeld[1],
    )


def _abgeleitete_hoehere(squad) -> list[str]:
    """Höherklassige Mannschaften aus den Namen erschließen.

    Nur, wenn in der Staffelverwaltung keine hinterlegt sind. Die gepflegte
    Liste ist immer besser — sie kennt Spielgemeinschaften, die aus einem Namen
    nicht abzulesen sind.

    Ohne diese Rückfallebene prüfte die Wartefrist gar nicht mehr, sobald die
    Staffel nicht initialisiert war: `hoehere` wäre leer, die Regel liefe durch
    und fände nichts. Genau der stille Ausfall, den es hier nicht geben darf.
    """
    from .mannschaftsnamen import club_name_and_suffix, is_higher_class

    eigen = squad.team_name or ""
    eigene_nummer = club_name_and_suffix(eigen)[1] or 1
    gefunden: list[str] = []
    for spieler in list(squad.starting_eleven) + list(squad.bench):
        historie = getattr(spieler, "season_appearances", None)
        for eintrag in getattr(historie, "matches", None) or []:
            for name, logo in (
                (eintrag.home_team, eintrag.home_team_logo_id),
                (eintrag.away_team, eintrag.away_team_logo_id),
            ):
                if not name or name in gefunden:
                    continue
                if is_higher_class(
                    name,
                    eigen,
                    logo,
                    squad.club_logo_id,
                    current_team_suffix=eigene_nummer,
                ):
                    gefunden.append(name)
    return sorted(gefunden)


def _hoehere_ohne_sich_selbst(squad, namen) -> tuple[str, ...]:
    """Die eigene Mannschaft ist nie höherklassig als sie selbst.

    Klingt selbstverständlich und war es nicht: `_ranks_higher` liest einen
    Namen ohne Zahl als erste Mannschaft des Vereins und damit als „höher als
    jede nummerierte". Vergleicht man sie mit sich selbst, kommt dieselbe
    Antwort heraus — für „SG Gittersee" wurde „SG Gittersee" als höhere
    Mannschaft abgeleitet.

    Die Folge war kein stiller Ausfall, sondern das Gegenteil: jeder Einsatz
    der eigenen Elf zählte als Einsatz oben, und die Wartefrist schlug bei
    jedem an, der vorige Woche gespielt hatte. An echten Daten fielen so 20
    Falschbefunde auf 15 Spiele an.

    Gefiltert wird an dieser einen Stelle, damit es für beide Quellen gilt:
    die abgeleitete Liste und die gepflegte aus der Staffelverwaltung. Auch
    letztere kann den eigenen Namen enthalten — durch einen Tippfehler im
    Dialog oder eine Initialisierung, die den Verein zweimal sah.
    """
    eigen = _norm(squad.team_name or "")
    return tuple(n for n in namen if _norm(n) != eigen)


def _wechsel(report, ist_heim: bool, name: str) -> tuple[Wechsel, ...]:
    """Die Wechsel einer Mannschaft. DFBnet sagt "home"/"away", nicht den Namen."""
    seite = "home" if ist_heim else "away"
    return tuple(
        Wechsel(
            minute=_minute(getattr(e, "minute", "")),
            mannschaft=name,
            kommt=getattr(e, "player_in", "") or "",
            geht=getattr(e, "player_out", "") or "",
        )
        for e in (report.substitutions or [])
        if (getattr(e, "team", "") or "").lower() == seite
    )


def _tore(report, heim: str, gast: str) -> tuple[Tor, ...]:
    """Die Treffer, mit dem Mannschaftsnamen statt "home"/"away"."""
    return tuple(
        Tor(
            minute=_minute(getattr(e, "minute", "")),
            mannschaft=heim if (getattr(e, "team", "") or "").lower() == "home" else gast,
            schuetze=getattr(e, "scorer", "") or "",
        )
        for e in (report.goals or [])
    )


def _alle_karten(report) -> tuple[Karte, ...]:
    """Jede Karte des Spielverlaufs, unabhaengig von der Aufstellung.

    `Mannschaft.karten` entsteht aus den Personen. Findet sich zu einem Namen
    im Verlauf niemand in der Aufstellung, faellt die Karte dort heraus - und
    genau die soll eine Regel finden koennen.
    """
    return tuple(
        Karte(
            art=e.card_type or "",
            minute=_minute(e.minute),
            person=e.player or "",
            mannschaft=e.team or "",
            grund=getattr(e, "reason", "") or "",
            personenart=getattr(e, "person_kind", "spieler") or "spieler",
        )
        for e in (report.cards or [])
    )


def _mannschaft(squad, ist_heim: bool, spieltag, karten, hoehere, umfeld, wechsel=()) -> Mannschaft:
    return Mannschaft(
        name=squad.team_name or "",
        ist_heim=ist_heim,
        startelf=tuple(
            _person(s, "startelf", spieltag, karten, umfeld) for s in squad.starting_eleven
        ),
        bank=tuple(_person(s, "bank", spieltag, karten, umfeld) for s in squad.bench),
        nicht_im_kader=tuple(
            _person(s, "nicht_im_kader", spieltag, karten, umfeld) for s in squad.not_in_squad
        ),
        betreuer=tuple(_betreuer(o, spieltag, karten, umfeld) for o in (squad.officials or [])),
        hoehere=_hoehere_ohne_sich_selbst(
            squad, tuple(hoehere) or tuple(_abgeleitete_hoehere(squad))
        ),
        wechsel=tuple(wechsel),
    )


def _staffel(konfiguration) -> Staffel:
    if konfiguration is None:
        return Staffel()
    return Staffel(
        name=getattr(konfiguration, "name", "") or "",
        altersklasse=getattr(konfiguration, "altersklasse", "") or "",
        saison=getattr(konfiguration, "saison", "") or "",
        spieltage=int(getattr(konfiguration, "spieltage", 0) or 0),
        hoehere_mannschaften=tuple(getattr(konfiguration, "hoehere_mannschaften", ()) or ()),
    )


def _spieltag_nummer(wert) -> int | None:
    ziffern = "".join(z for z in str(wert or "") if z.isdigit())
    return int(ziffern) if ziffern else None


def _anstoss(datum, kickoff: str) -> datetime | None:
    if datum is None:
        return None
    text = (kickoff or "").strip()
    for form in ("%H:%M", "%H.%M"):
        try:
            uhr = datetime.strptime(text[:5], form)
        except ValueError:
            continue
        return datetime.combine(datum, uhr.time())
    return None


def uebersetzen(report, staffel_konfiguration=None, auskunft=None) -> Spiel:
    """Ein `Spiel` aus einem `MatchReport`.

    Wirft nicht: ein fehlendes Feld wird zu einem leeren Wert, damit eine
    einzelne Lücke im Bericht nicht das ganze Regelwerk stilllegt. Regeln
    prüfen selbst auf `None`, und die Vokabeln sind so gebaut, dass eine
    fehlende Angabe zu „keine Aussage" führt und nicht zu „null".
    """
    meta = report.meta
    datum = datum_lesen(meta.match_date)
    karten = _karten_je_person(report)
    hoehere = tuple(getattr(staffel_konfiguration, "hoehere_mannschaften", ()) or ())
    wettbewerb = meta.competition or meta.match_type or ""
    # Die Altersklasse der Staffel reist mit: § 68 (2) begrenzt Wartefrist
    # und Stammspielergrenze auf „diese Altersklasse", und ohne sie zählt ein
    # Ü35-Spiel als Einsatz in einer höheren Herrenmannschaft.
    altersklasse = (getattr(staffel_konfiguration, "altersklasse", "") or "").lower()
    if altersklasse in ("maenner", "herren", "frauen"):
        altersklasse = ""
    umfeld = (auskunft, wettbewerbskategorie(wettbewerb), altersklasse)

    return Spiel(
        heim=meta.home_team or "",
        gast=meta.away_team or "",
        datum=datum,
        anstoss=_anstoss(datum, meta.kickoff),
        spieltag=_spieltag_nummer(meta.match_day),
        spielklasse=meta.league_class or "",
        wettbewerb=wettbewerb,
        spielkennung=meta.match_id or "",
        ergebnis=meta.result or "",
        vorkommnisse=tuple(
            str(v) for v in (report.incidents_details or {}).get("checked_labels", [])
        ),
        vorkommnisse_text=str((report.incidents_details or {}).get("text", "")),
        heim_mannschaft=_mannschaft(
            report.home_squad,
            True,
            datum,
            karten,
            hoehere,
            umfeld,
            _wechsel(report, True, report.home_squad.team_name or ""),
        ),
        gast_mannschaft=_mannschaft(
            report.away_squad,
            False,
            datum,
            karten,
            hoehere,
            umfeld,
            _wechsel(report, False, report.away_squad.team_name or ""),
        ),
        staffel=_staffel(staffel_konfiguration),
        tore=_tore(
            report,
            report.home_squad.team_name or "",
            report.away_squad.team_name or "",
        ),
        alle_karten=_alle_karten(report),
    )
