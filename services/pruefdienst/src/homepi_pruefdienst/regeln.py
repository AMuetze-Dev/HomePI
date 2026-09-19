"""Die Regeln, die **nur den Spielbericht** brauchen.

Uebernommen aus `D:/DevLibrary/StaffelPilot/src/rules/rules_engine.py`, und
zwar genau der Teil, der ohne Datenbank und ohne Konfiguration auskommt:
Vorkommnisse, Kommentare an Bestaetigungen, Ordnungsdienst, fehlende
Bestaetigungen, Fristen, Dokumente und das Spielrecht aus der Aufstellung.

Was hier **nicht** steht, und warum:

* **Gelbe Karten zaehlen** braucht die Geschichte des Spielers ueber die
  Saison -- also einen Speicher, den dieser Dienst nicht hat.
* **Stammspieler** (§ 68) braucht die Einsaetze in hoeherklassigen
  Mannschaften, dasselbe Problem.
* Die **Regeldateien** des Staffelleiters (`config/regeln/*.py`) sind ein
  eigenes Stueck; sie kommen spaeter.

Alles hier ist rein: Bericht hinein, Befunde heraus. Kein Netz, keine Uhr
ausser der, die uebergeben wird -- deshalb laesst es sich in Millisekunden
pruefen, und deshalb steht es hier und nicht im Browser.

**Nichts wird automatisch beurteilt.** Ein Vorkommnis wird vorgelegt, nicht
bewertet; Stichworte heben nur die Schwere an, damit ein Eintrag ueber Gewalt
nicht zwischen zwanzig Routinenotizen verschwindet. Was er bedeutet,
entscheidet der Staffelleiter.
"""

from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any

from .bericht import Confirmation, MatchReport, Player, TeamSquad


class Severity(Enum):
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


@dataclass
class Violation:
    """Ein Befund, wie ihn eine Regel meldet.

    Die Namen sind englisch geblieben, wie im Original -- sie sind die
    Innenseite. Was der Staffelleiter liest, entsteht in `als_befund`.
    """

    rule: str
    severity: Severity
    message: str
    details: dict[str, Any] = field(default_factory=dict)


#: Welche Schwere im Artefakt dazu gehoert.
_SCHWERE = {
    Severity.CRITICAL: "kritisch",
    Severity.WARNING: "warnung",
    Severity.INFO: "hinweis",
}


#: Die Ueberschrift, unter der ein Befund in der Warteschlange steht.
#:
#: Ausgeschrieben und nicht aus der Meldung geschnitten: die faengt mit dem
#: Vereinsnamen an, und "Post SV Dresden 2" ist keine Ueberschrift, sondern
#: eine Mannschaft. In der Liste stehen zwanzig Befunde untereinander -- man
#: liest dort, *was* los ist, nicht *bei wem*.
_TITEL = {
    "confirmation_comment": "Kommentar an der Bestätigung",
    "confirmation_late": "Bestätigung zu spät",
    "confirmation_missing": "Bestätigung fehlt",
    "confirmation_unlesbar": "Bestätigung nicht lesbar",
    "dfbnet_warning": "Hinweis aus DFBnet",
    "documents_present": "Dokumente am Spielbericht",
    "incidents": "Vorkommnisse im Spielverlauf",
    "order_manager_dual_role": "Ordnungsdienst in Doppelrolle",
    "order_manager_is_player": "Ordnungsdienst ist Spieler",
    "order_manager_missing": "Ordnungsdienst nicht benannt",
    "player_eligibility": "Spielrecht fraglich",
    "release_late": "Freigabe des Schiedsrichters zu spät",
    "rule_error": "Eine Regel ist gescheitert",
    "bericht_ungelesen": "Spielbericht nicht gelesen",
}


def titel_zu(regel: str) -> str:
    """Die Ueberschrift, oder die Kennung -- aber nie nichts.

    Eine unbekannte Regel bekommt ihren technischen Namen. Der ist haesslich
    und genau deshalb richtig: er faellt auf, und jemand traegt die
    Ueberschrift nach.
    """
    return _TITEL.get(regel, regel)


def als_befund(verstoss: Violation, mannschaft: str = "") -> dict[str, object]:
    """Ein Befund in der Sprache des Artefakts.

    `weg` bleibt leer: wohin ein Befund fuehrt, steht in der Spielordnung, und
    die kennt der Regelkatalog des Artefakts -- nicht diese Datei.
    """
    einzelheiten = verstoss.details or {}
    return {
        "regel": verstoss.rule,
        "schwere": _SCHWERE[verstoss.severity],
        "titel": titel_zu(verstoss.rule),
        "text": verstoss.message[:2000],
        "person": str(einzelheiten.get("player") or einzelheiten.get("person") or "")[:120],
        "mannschaft": (mannschaft or str(einzelheiten.get("team") or ""))[:120],
    }


def befunde_aus(report: MatchReport) -> list[dict[str, object]]:
    """Alle Regeln ueber einen Bericht, fertig fuer das Artefakt."""
    return [als_befund(v) for v in pruefe(report)]


def nicht_gelesen(grund: str) -> list[dict[str, object]]:
    """Ein Bericht, den der Dienst nicht aufbekommen hat.

    Das **muss** ein Befund werden. Ein Spiel ohne Befunde sieht in der
    Warteschlange aus wie eines, das geprueft und sauber war -- und dieses
    hier hat niemand angesehen. Lieber eine Warnung, die jemand wegklickt,
    als eine Liste, die Vollstaendigkeit vortaeuscht.
    """
    return [
        {
            "regel": "bericht_ungelesen",
            "schwere": "warnung",
            "titel": titel_zu("bericht_ungelesen"),
            "text": f"Der Spielbericht liess sich nicht lesen: {grund}"[:2000],
            "person": "",
            "mannschaft": "",
        }
    ]


#: Eine Regel: Bericht hinein, Befunde heraus. Mehr braucht sie nicht --
#: weder Datenbank noch Konfiguration, und genau deshalb steht sie hier.
Regel = Callable[[MatchReport], list[Violation]]


#: Die Regeln dieser Datei, in der Reihenfolge, in der sie laufen.
#: Ausdruecklich aufgezaehlt und nicht eingesammelt: eine Regel, die
#: versehentlich mitlaeuft, ist ein Schreiben an einen Verein.
def alle_regeln() -> list[Regel]:
    return [
        _check_incidents,
        _check_confirmation_comments,
        _check_order_manager,
        _check_team_confirmations,
        _check_release_timeliness,
        _check_documents,
        _check_player_eligibility,
    ]


def pruefe(report: MatchReport) -> list[Violation]:
    """Alle Regeln ueber einen Bericht.

    Eine Regel, die wirft, nimmt die anderen nicht mit: sie meldet sich als
    `rule_error` und der Lauf geht weiter. Achtzig Berichte duerfen nicht an
    einem ungewoehnlichen stehenbleiben.
    """
    gefunden: list[Violation] = []
    for regel in alle_regeln():
        try:
            gefunden.extend(regel(report))
        except Exception as fehler:
            gefunden.append(
                Violation(
                    rule="rule_error",
                    severity=Severity.WARNING,
                    message=f"Die Regel {regel.__name__} ist gescheitert: {fehler}",
                    details={"regel": regel.__name__},
                )
            )
    return gefunden


_INCIDENT_KEYWORDS = (
    "gewalt",
    "diskrimin",
    "rassis",
    "beleidig",
    "tätlich",
    "taetlich",
    "handgreif",
    "bedroh",
    "spuck",
    "schlag",
    "abbruch",
    "polizei",
)


def _check_incidents(report: MatchReport) -> list[Violation]:
    """Surface the free text of the 'Vorkommnisse' panel for a human to read.

    The text is never judged automatically — the Staffelleiter decides what it
    means. Keywords only raise the severity so an entry mentioning violence or
    discrimination is not buried among routine notes.
    """
    details = report.incidents_details or {}
    text = (details.get("text") or "").strip()
    checked = list(details.get("checked_labels") or [])
    if not text and not checked:
        return []

    haystack = " ".join([text, *checked]).lower()
    is_severe = any(keyword in haystack for keyword in _INCIDENT_KEYWORDS)

    parts: list[str] = []
    if checked:
        parts.append(f"Angekreuzt: {', '.join(checked)}.")
    if text:
        parts.append(_shorten(text))

    return [
        Violation(
            rule="incidents",
            severity=Severity.CRITICAL if is_severe else Severity.WARNING,
            message="Vorkommnisse im Spielverlauf: " + " ".join(parts),
            details={**details, "severe": is_severe},
        )
    ]


def _check_confirmation_comments(report: MatchReport) -> list[Violation]:
    """Report free text a team or the referee added to their confirmation.

    Per the workflow the Staffelleiter has to read such a comment and decide;
    it is therefore surfaced verbatim rather than interpreted.
    """
    violations: list[Violation] = []
    for conf in report.confirmations:
        comment = (getattr(conf, "comment", "") or "").strip()
        if not comment:
            continue
        violations.append(
            Violation(
                rule="confirmation_comment",
                severity=Severity.WARNING,
                message=f"{conf.party or 'Unbekannt'} hat die Bestätigung kommentiert: "
                + _shorten(comment),
                details={"team": conf.party, "comment": comment},
            )
        )
    return violations


def _shorten(text: str, limit: int = 300) -> str:
    """Collapse whitespace and cut overly long free text for a message."""
    collapsed = " ".join(text.split())
    if len(collapsed) <= limit:
        return collapsed
    return collapsed[: limit - 1].rstrip() + "…"


def _check_order_manager(report: MatchReport) -> list[Violation]:
    """The *home* team must field one dedicated 'Leiter Ordnungsdienst'.

    Only the home team does: the Ordnungsdienst belongs to whoever runs the
    ground, and a visiting team has no such duty. Checking both squads produced
    a Mahnung against every guest — findings the Staffelleiter then had to talk
    away one by one.

    The order manager must not hold another team-official role and must not be
    listed as a player.
    """
    return _check_squad_order_manager(report.home_squad)


def aufstellung_bekannt(squad: TeamSquad) -> bool:
    """Ob wir ueber diese Mannschaft ueberhaupt etwas wissen.

    Aus dem HTML des Spielberichts kommt nur der Name; Spieler und Offizielle
    stehen in der Aufstellungsschnittstelle. Fehlt die -- weil sie nicht
    abgerufen wurde oder die Berechtigung fehlt --, ist die Mannschaft leer,
    und eine Regel, die daraus "kein Ordnungsdienst" macht, schickt jedem
    Heimverein eine Mahnung fuer nichts.

    Dasselbe Prinzip wie beim Spielerfoto: Unwissen darf nie wie ein
    Verstoss aussehen.
    """
    return bool(squad.starting_eleven or squad.bench or squad.officials)


def _check_squad_order_manager(squad: TeamSquad) -> list[Violation]:
    if not aufstellung_bekannt(squad):
        return []

    violations = []
    order_managers = [
        o for o in squad.officials if any("Leiter Ordnungsdienst" in r for r in o.roles)
    ]

    if not order_managers:
        violations.append(
            Violation(
                rule="order_manager_missing",
                severity=Severity.CRITICAL,
                message=f"{squad.team_name}: Kein Leiter Ordnungsdienst angegeben.",
                details={"team": squad.team_name},
            )
        )
        return violations

    for om in order_managers:
        other_roles = [r for r in om.roles if r != "Leiter Ordnungsdienst"]
        if other_roles:
            violations.append(
                Violation(
                    rule="order_manager_dual_role",
                    severity=Severity.WARNING,
                    message=(
                        f"{squad.team_name}: {om.name} hat als Leiter Ordnungsdienst "
                        f"zusätzlich die Rolle(n) {', '.join(other_roles)}."
                    ),
                    details={"team": squad.team_name, "name": om.name, "roles": om.roles},
                )
            )

        player_names = {
            p.name
            for container in (squad.starting_eleven, squad.bench, squad.not_in_squad)
            for p in container
        }
        if om.name in player_names:
            violations.append(
                Violation(
                    rule="order_manager_is_player",
                    severity=Severity.CRITICAL,
                    message=(
                        f"{squad.team_name}: {om.name} ist gleichzeitig Spieler und "
                        "Leiter Ordnungsdienst."
                    ),
                    details={"team": squad.team_name, "name": om.name},
                )
            )

    return violations


def canonical_team(report: MatchReport, home: bool) -> str:
    """Return one agreed spelling of a team name.

    Three sources exist for the same team: `squad.team_name` from the squad
    panel, `meta.home_team`/`away_team` from splitting the "Begegnung" line, and
    `spielberichte.heim`/`gast` from the match-list row. When they diverge, a
    finding filtered by one spelling disappears from a view filtered by
    another — and an empty `meta` value produced messages that began with a
    bare colon. The squad panel is the most reliable of the three.
    """
    squad = report.home_squad if home else report.away_squad
    meta_name = report.meta.home_team if home else report.meta.away_team
    for candidate in (getattr(squad, "team_name", ""), meta_name):
        if candidate and candidate.strip():
            return candidate.strip()
    return "Heim" if home else "Gast"


def _check_team_confirmations(report: MatchReport) -> list[Violation]:
    """Both teams must confirm the report — step 6.

    Home first, then the guest: without an appointed referee the home team's
    confirmation is what releases the report, and the guest's own window only
    opens after it. See `_confirmation_deadline` for the deadlines themselves.
    """
    violations: list[Violation] = []
    now = datetime.now()

    heim = canonical_team(report, True)
    gast = canonical_team(report, False)
    heim_conf = _find_confirmation(report, heim)
    heim_bestaetigt = (
        _parse_datetime(heim_conf.signed_at)
        if heim_conf is not None and heim_conf.confirmed
        else None
    )

    for team_name, conf, frist in (
        (heim, heim_conf, _confirmation_deadline(report)),
        (
            gast,
            _find_confirmation(report, gast),
            _confirmation_deadline(report, gast=True, heim_bestaetigt=heim_bestaetigt),
        ),
    ):
        if conf is None or not conf.confirmed:
            abgelaufen = frist is not None and now > frist
            violations.append(
                Violation(
                    rule="confirmation_missing",
                    severity=Severity.CRITICAL if abgelaufen else Severity.WARNING,
                    message=(
                        f"{team_name}: Spielbericht nicht bestätigt. "
                        f"Frist ({_fmt_dt(frist)}) ist abgelaufen."
                        if abgelaufen
                        else f"{team_name}: Spielbericht noch nicht bestätigt."
                    ),
                    details=(
                        {"team": team_name, "deadline": _fmt_dt(frist)}
                        if abgelaufen
                        else {"team": team_name}
                    ),
                )
            )
            continue

        signed_at = _parse_datetime(conf.signed_at)
        if conf.signed_at and signed_at is None:
            # Confirmed, but the timestamp is unreadable — so the lateness
            # check cannot run. Saying nothing here would look exactly like
            # "confirmed in time".
            violations.append(
                Violation(
                    rule="confirmation_unlesbar",
                    severity=Severity.WARNING,
                    message=(
                        f"{team_name}: Zeitpunkt der Bestätigung "
                        f"({conf.signed_at!r}) ist nicht lesbar — ob sie "
                        "fristgerecht war, konnte nicht geprüft werden."
                    ),
                    details={"team": team_name, "signed_at": conf.signed_at},
                )
            )
            continue
        if frist and signed_at and signed_at > frist:
            violations.append(
                Violation(
                    rule="confirmation_late",
                    severity=Severity.CRITICAL,
                    message=(
                        f"{team_name}: Bestätigung erfolgte erst am "
                        f"{_fmt_dt(signed_at)} (Frist: {_fmt_dt(frist)}, "
                        f"{_verspaetung(signed_at - frist)} zu spät)."
                    ),
                    details={
                        "team": team_name,
                        "signed_at": _fmt_dt(signed_at),
                        "deadline": _fmt_dt(frist),
                    },
                )
            )

    return violations


def _find_confirmation(report: MatchReport, team_name: str) -> Confirmation | None:
    """Find the confirmation entry belonging to a team.

    The party field sometimes contains the team name and sometimes the name of
    the person who signed. We first try a direct name match, then fall back to
    positional assignment (first remaining entry -> home, last remaining -> away).
    """
    # Direct match: party contains the team name.
    for conf in report.confirmations:
        if team_name and team_name in conf.party:
            return conf

    # No direct match: use the remaining non-referee confirmation positionally.
    home_name = report.meta.home_team
    away_name = report.meta.away_team
    other = away_name if team_name == home_name else home_name
    candidates = [
        conf
        for conf in report.confirmations
        if (other not in conf.party) and ("Schiedsrichter" not in conf.party)
    ]
    if not candidates:
        return None
    # First remaining entry is treated as home confirmation, last as away.
    return candidates[0] if team_name == home_name else candidates[-1]


#: Beide Fristen stehen in § 59 (17) SpO SFV:
#:
#:   „Der Spielbericht Online ist unmittelbar nach dem Spiel vom Schiedsrichter
#:    oder den SR-Assistenten vollständig auszufüllen. Die Eintragungen sind
#:    mit den beiden Mannschaftsverantwortlichen abzugleichen und nach der
#:    Schiedsrichterfreigabe durch diese unmittelbar vor Ort bis 18:00 Uhr
#:    spätestens aber 60 Minuten nach Spielende die Kenntnisnahme zu
#:    bestätigen."
#:
#: Die Zahlen standen lange unbelegt hier — die Annahme war richtig, aber
#: niemand konnte sie nachschlagen. „spätestens aber 60 Minuten nach
#: Spielende" ist dabei die spätere der beiden Fristen, nicht die frühere:
#: ein Abendspiel, das um 18:40 endet, kann nicht um 18:00 bestätigt sein.

#: § 59 (17) — Freigabe durch den Schiedsrichter am Spieltag.
REFEREE_RELEASE_DEADLINE_HOUR = 18

#: § 59 (17) — „spätestens aber 60 Minuten nach Spielende".
RELEASE_GRACE_MINUTES = 60

#: § 59 (17) — dieselben Fristen für die Bestätigung durch die Mannschaften.
#: Es gilt die spätere von beiden.
CONFIRMATION_DEADLINE_HOUR = 18
CONFIRMATION_GRACE_MINUTES = 60


def _verspaetung(delta: timedelta) -> str:
    """How late something was, in the unit that carries the information.

    "0 Std. zu spät" for eleven minutes reads like a rounding artefact and made
    a real finding look like noise.
    """
    minuten = int(delta.total_seconds() // 60)
    if minuten < 60:
        return f"{minuten} Min."
    stunden, rest = divmod(minuten, 60)
    if stunden < 24:
        return f"{stunden} Std. {rest} Min." if rest else f"{stunden} Std."
    tage, rest_std = divmod(stunden, 24)
    einheit = "Tag" if tage == 1 else "Tage"
    return f"{tage} {einheit} {rest_std} Std." if rest_std else f"{tage} {einheit}"


def _uhrzeit_auf(tag: datetime, text: str) -> datetime | None:
    """A "HH:MM" from `text`, placed on `tag`. Rolls over past midnight.

    DFBnet writes "24:00" for a match that ended exactly at midnight, and
    `datetime.replace(hour=24)` raises — which came out of the rules as
    `rule_error` and blocked the match from being ticked off at all.
    """
    treffer = re.search(r"(\d{1,2}):(\d{2})", text or "")
    if not treffer:
        return None
    minuten = int(treffer.group(1)) * 60 + int(treffer.group(2))
    tage, rest = divmod(minuten, 24 * 60)
    stunde, minute = divmod(rest, 60)
    return tag.replace(hour=stunde, minute=minute, second=0, microsecond=0) + timedelta(days=tage)


def _anstoss(report: MatchReport) -> datetime | None:
    """Kickoff, as a full datetime. DFBnet writes "17:00 (17:00 )"."""
    match_date = _parse_date(report.meta.match_date)
    if not match_date:
        return None
    return _uhrzeit_auf(match_date, report.meta.kickoff or "")


def _match_end(report: MatchReport) -> datetime | None:
    """When the match finished, as a full datetime.

    Usually on the match day, but not always: a 22:00 kick-off that ends at
    00:30 ends on the *following* day, and reading that as 00:30 in the morning
    puts the confirmation deadline eighteen hours before the final whistle —
    the same mistake that once flagged every evening match as late, one day
    further along.
    """
    match_date = _parse_date(report.meta.match_date)
    if not match_date:
        return None
    ende = _uhrzeit_auf(match_date, report.meta.end_time or "")
    if ende is None:
        return None

    anstoss = _anstoss(report)
    if anstoss and ende < anstoss:
        ende += timedelta(days=1)
    return ende


def referee_release_deadline(report: MatchReport) -> datetime | None:
    """Deadline by which the referee should have released the report.

    18:00 on match day — but never before the match has actually ended. An
    evening kick-off finishing at 18:40 cannot have been released by 18:00, and
    flagging it as late was the single biggest source of false findings.

    The grace period after the final whistle is deliberately explicit rather
    than woven into the comparison; see RELEASE_GRACE_MINUTES.
    """
    match_date = _parse_date(report.meta.match_date)
    if not match_date:
        return None
    regel = match_date.replace(
        hour=REFEREE_RELEASE_DEADLINE_HOUR, minute=0, second=0, microsecond=0
    )
    ende = _match_end(report)
    if ende is None:
        return regel
    return max(regel, ende + timedelta(minutes=RELEASE_GRACE_MINUTES))


def _check_release_timeliness(report: MatchReport) -> list[Violation]:
    """Report a match whose Spielbericht was released too late — step 8.

    Only fires when the release timestamp is actually known. A missing
    timestamp is reported by `confirmation_missing` instead of being guessed
    into a lateness finding.
    """
    deadline = referee_release_deadline(report)
    if deadline is None:
        return []
    release = _parse_datetime(report.meta.referee_release_at)
    if release is None:
        return []
    if release <= deadline:
        return []

    hours_late = (release - deadline).total_seconds() / 3600
    return [
        Violation(
            rule="release_late",
            severity=Severity.CRITICAL if hours_late >= 24 else Severity.WARNING,
            message=(
                f"Spielbericht erst am {_fmt_dt(release)} freigegeben; "
                f"Frist war {_fmt_dt(deadline)} ({_verspaetung(release - deadline)} zu spät)."
            ),
            details={
                "released_at": _fmt_dt(release),
                "deadline": _fmt_dt(deadline),
                "hours_late": round(hours_late, 1),
            },
        )
    ]


def _basis_frist(report: MatchReport) -> datetime | None:
    """The earliest a confirmation can reasonably be expected.

    18:00 on match day, but never less than an hour after the final whistle.
    The hour is not a formality: the teams change, shower and only then sit
    down with the report. A match ending 21:45 confirmed at 22:15 is exactly
    the normal case, and calling it late was pure noise.
    """
    match_date = _parse_date(report.meta.match_date)
    if not match_date:
        return None
    regel = match_date.replace(hour=CONFIRMATION_DEADLINE_HOUR, minute=0, second=0, microsecond=0)
    ende = _match_end(report)
    if ende is None:
        return regel
    return max(regel, ende + timedelta(minutes=CONFIRMATION_GRACE_MINUTES))


def _confirmation_deadline(
    report: MatchReport,
    *,
    gast: bool = False,
    heim_bestaetigt: datetime | None = None,
) -> datetime | None:
    """When this team must have confirmed the report.

    The deadline is per team, because the report is passed along rather than
    opened by both at once:

    * base — 18:00 or final whistle + 60 minutes, whichever is later;
    * with a referee — additionally 60 minutes after the referee's release,
      whichever is later;
    * without a referee — the *home* team's confirmation takes the place of
      the release, so the guest gets 60 minutes after that.

    Measuring both teams against one deadline made every unrefereed evening
    match look late for the guest, who by the rule had not even started yet.
    """
    basis = _basis_frist(report)
    if basis is None:
        return None

    release = _parse_datetime(report.meta.referee_release_at)
    if release is not None:
        return max(basis, release + timedelta(minutes=CONFIRMATION_GRACE_MINUTES))

    if gast and heim_bestaetigt is not None:
        return max(basis, heim_bestaetigt + timedelta(minutes=CONFIRMATION_GRACE_MINUTES))
    return basis


def _parse_date(value: str) -> datetime | None:
    """Parse dates like 'Sa., 13.06.26' or '13.06.2026'."""
    if not value:
        return None
    value = value.strip()
    # Remove weekday prefix if present.
    if "," in value:
        value = value.split(",", 1)[1].strip()
    # ISO last: it is what the database stores, and a caller reaching in with
    # a stored date should get an answer rather than a silent None.
    for fmt in ("%d.%m.%Y", "%d.%m.%y", "%Y-%m-%d"):
        try:
            return datetime.strptime(value, fmt)
        except ValueError:
            continue
    return None


def _parse_datetime(value: str) -> datetime | None:
    """Parse timestamps like '13.06.2026, 19:25:47' or '13.06.2026, 19:25'."""
    if not value:
        return None
    value = value.strip()
    # The comma is DFBnet's, but a separator is not worth a missed check: a
    # timestamp that fails to parse silently disables the lateness rule for
    # that confirmation.
    for fmt in (
        "%d.%m.%Y, %H:%M:%S",
        "%d.%m.%Y, %H:%M",
        "%d.%m.%y, %H:%M:%S",
        "%d.%m.%y, %H:%M",
        "%d.%m.%Y %H:%M:%S",
        "%d.%m.%Y %H:%M",
        "%d.%m.%y %H:%M:%S",
        "%d.%m.%y %H:%M",
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%dT%H:%M:%S",
    ):
        try:
            return datetime.strptime(value, fmt)
        except ValueError:
            continue
    return None


def _fmt_dt(dt: datetime | None) -> str:
    if not dt:
        return ""
    return dt.strftime("%d.%m.%Y, %H:%M")


def _check_documents(report: MatchReport) -> list[Violation]:
    if not report.documents:
        return []
    return [
        Violation(
            rule="documents_present",
            severity=Severity.INFO,
            message=f"{len(report.documents)} Dokument(e) am Spielbericht hinterlegt.",
            details={"documents": report.documents},
        )
    ]


def _check_player_eligibility(report: MatchReport) -> list[Violation]:
    """Kennzeichen aus DFBnet, die einen Einsatz ausschließen.

    Die Altersklassen sind hier heraus: sie stehen in
    `config/regeln/10_altersklassen.py`. Was bleibt, ist das Ablesen dessen,
    was DFBnet selbst am Spieler vermerkt hat — Datenbeschaffung, kein
    Regelwerk.
    """
    violations: list[Violation] = []

    # Only these badges mean the player must not have played. "Stammspieler"
    # and "U23" are neutral markers: per SPO § 68 (2) b) a Stammspieler of a
    # higher-class team merely counts against a cap of two — that cap is
    # checked by the stammspieler_limit rule — and § 68 (2) c) makes U23 an
    # *exemption* from the cap, not a problem. Reporting those as ineligible
    # produced one warning per such player and drowned the real findings.
    # See docs/spielordnung-regeln.md.
    blocking_badges = {
        "nicht spielberechtigt",
        "gesperrt",
        "keine spielberechtigung",
        "spielrecht fehlt",
    }

    def _blocking_badge(player: Player) -> str:
        for badge in sorted(str(b).lower() for b in player.badges):
            for marker in blocking_badges:
                if marker in badge:
                    return badge
        return ""

    for squad in (report.home_squad, report.away_squad):
        for container in (squad.starting_eleven, squad.bench):
            for player in container:
                badge = _blocking_badge(player)
                if badge:
                    violations.append(
                        Violation(
                            rule="player_eligibility",
                            severity=Severity.CRITICAL,
                            message=(
                                f"{squad.team_name}: {player.name} ({player.pass_number}) "
                                f"war nicht spielberechtigt — Kennzeichnung '{badge}'."
                            ),
                            details={
                                "team": squad.team_name,
                                "player": player.name,
                                "pass_nr": player.pass_number,
                                "badge": badge,
                            },
                        )
                    )
        # Altersklassen stehen jetzt in config/regeln/10_altersklassen.py.

    # Surface raw DFBnet warnings that mention a player name.
    if report.raw_warnings:
        for warning in report.raw_warnings:
            warning_lower = warning.lower()
            for squad in (report.home_squad, report.away_squad):
                for container in (squad.starting_eleven, squad.bench, squad.not_in_squad):
                    for player in container:
                        if player.name and player.name.lower() in warning_lower:
                            violations.append(
                                Violation(
                                    rule="dfbnet_warning",
                                    severity=Severity.WARNING,
                                    message=f"{squad.team_name}: {warning}",
                                    details={
                                        "team": squad.team_name,
                                        "player": player.name,
                                        "warning": warning,
                                    },
                                )
                            )

    return violations


# Die Altersklassenpruefungen stehen in config/regeln/10_altersklassen.py.


def _parse_minute(value: str) -> int | None:
    """Extract a numeric minute from strings like '42 or 42'."""
    if not value:
        return None
    text = str(value).replace("'", "").strip()
    match = re.search(r"\d+", text)
    return int(match.group(0)) if match else None


def _season_start_from_match_date(match_date: str) -> str | None:
    """Return the season start as an ISO date (YYYY-07-01).

    The German football season starts on 1 July; matches before July belong to
    the previous season. ISO on purpose: the value is compared against
    karten.datum_iso, and comparing German DD.MM.YYYY strings made
    '20.10.2024' >= '01.07.2025' true.
    """
    dt = _parse_date(match_date)
    if not dt:
        return None
    season_year = dt.year if dt.month >= 7 else dt.year - 1
    return datetime(season_year, 7, 1).strftime("%Y-%m-%d")
