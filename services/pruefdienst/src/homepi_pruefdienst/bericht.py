"""Einen Spielbericht aus DFBnet-HTML lesen.

**Uebernommen aus der bestehenden Anwendung**
(`D:/DevLibrary/StaffelPilot/src/automation/extractor.py`) und bis auf diesen
Kopf unveraendert. Er ist ueber eine Saison an echten Seiten gewachsen und hat
zwei Fehler gefunden, die 630 andere Tests nicht sahen; ihn neu zu schreiben
hiesse, dieselben Fehler noch einmal zu machen.

Er liest drei Ausschnitte:

* `info_html` -- Wettkampfdaten, Spieldaten, Schiedsrichter, Spielstaette
* `teams_html` -- Aufstellungen, Bank, Wechsel
* `history_html` -- Ereignisse, Bestaetigungen, Dokumente

Und er ist mit Absicht nachsichtig: ein fehlender Abschnitt gibt Leeres
zurueck und wirft nicht. Ein Prueflauf ueber achtzig Berichte soll nicht am
ersten ungewoehnlichen stehenbleiben.

Die Namen sind englisch geblieben. Sie sind die Innenseite; was der
Staffelleiter liest, kommt aus dem Artefakt und ist deutsch. Sie hier zu
uebersetzen hiesse, jede Zeile anzufassen, die sich bewaehrt hat.
"""

import re
from dataclasses import dataclass, field
from pathlib import Path

from bs4 import BeautifulSoup, Tag


@dataclass
class MatchMeta:
    match_id: str = ""
    season: str = ""
    match_type: str = ""
    league_class: str = ""
    region: str = ""
    competition: str = ""
    staffel: str = ""
    round_: str = ""
    home_team: str = ""
    away_team: str = ""
    match_day: str = ""
    match_date: str = ""
    kickoff: str = ""
    end_time: str = ""
    result: str = ""
    halftime_result: str = ""
    report_status: str = ""
    venue: str = ""
    spectators: str = ""
    referee_release_at: str = ""


@dataclass
class Official:
    role: str = ""
    name: str = ""
    club: str = ""


@dataclass
class CardEvent:
    minute: str = ""
    team: str = ""
    player: str = ""
    card_type: str = ""  # Gelbe Karte, Rote Karte, Gelb-Rote Karte
    #: "spieler" or "offizieller". SPO § 58 names players, trainers and
    #: Funktionsträger alike, but DFBnet lists them in separate panels and only
    #: players carry a Passnummer.
    person_kind: str = "spieler"


@dataclass
class GoalEvent:
    minute: str = ""
    team: str = ""
    scorer: str = ""


@dataclass
class SubEvent:
    minute: str = ""
    team: str = ""
    player_in: str = ""
    player_out: str = ""


@dataclass
class Confirmation:
    party: str = ""  # Heim, Gast, Schiedsrichter
    confirmed: bool = False
    signed_by: str = ""
    signed_at: str = ""
    #: Free text the confirming person added. Must be read by a human.
    comment: str = ""


@dataclass
class TeamOfficial:
    name: str = ""
    roles: list[str] = field(default_factory=list)


@dataclass
class SeasonAppearance:
    match_id: str = ""
    kickoff: str = ""
    home_team: str = ""
    away_team: str = ""
    home_team_logo_id: str = ""
    away_team_logo_id: str = ""
    division: str = ""
    competition: str = ""  # e.g. Meisterschaft, Pokal, Freundschaftsspiel
    minutes: int = 0
    match_day: int | None = None


@dataclass
class SeasonAppearances:
    count: int = 0
    minutes: int = 0
    matches: list[SeasonAppearance] = field(default_factory=list)


@dataclass
class Player:
    name: str = ""
    pass_number: str = ""
    birthdate: str = ""
    jersey_number: str = ""
    is_goalkeeper: bool = False
    is_captain: bool = False
    badges: list[str] = field(default_factory=list)
    photo_title: str = ""
    #: Spielerfoto: "" = nicht bekannt, "vorhanden", "fehlt". Drei Zustaende
    #: mit Absicht — die DOM-Rueckfallebene und aeltere gespeicherte Berichte
    #: wissen es nicht, und "weiss ich nicht" darf nie wie "fehlt" aussehen.
    photo_state: str = ""
    #: Spielrecht, wie DFBnet es in der Aufstellung fuehrt. `None` heisst hier
    #: durchgehend: nicht bekannt. Die DOM-Rueckfallebene und aeltere
    #: gespeicherte Berichte kennen diese Felder nicht, und Unwissen darf
    #: nicht wie ein fehlendes Spielrecht aussehen.
    eligible_for_team: bool | None = None
    eligible_for_club: bool | None = None
    no_championship_eligibility: bool | None = None
    #: ISO-Datum, ab dem Meisterschaftsspiele erlaubt sind.
    championship_from: str = ""
    #: ISO-Datum, ab dem Pflichtspiele erlaubt sind (Wartefrist nach Wechsel).
    competitive_from: str = ""
    guest_eligibility: bool | None = None
    second_eligibility: bool | None = None
    #: DFBnets eigener Sperrvermerk zur Aufstellung, als Klartext.
    suspension_note: str = ""
    #: Wann das Foto hinterlegt wurde, ISO-Zeitstempel aus DFBnet. § 67 (3)
    #: haengt an diesem Datum, nicht am Alter des Spielers.
    photo_timestamp: str = ""
    player_id: str = ""
    match_status: str = ""  # starting_eleven, bench, not_in_squad, substituted_in, substituted_out
    substitutions: list[dict] = field(default_factory=list)
    season_appearances: SeasonAppearances = field(default_factory=SeasonAppearances)


@dataclass
class TeamSquad:
    team: str = ""  # Heim / Gast
    team_name: str = ""
    club_logo_id: str = ""
    starting_eleven: list[Player] = field(default_factory=list)
    bench: list[Player] = field(default_factory=list)
    not_in_squad: list[Player] = field(default_factory=list)
    officials: list[TeamOfficial] = field(default_factory=list)


@dataclass
class MatchReport:
    meta: MatchMeta = field(default_factory=MatchMeta)
    officials: list[Official] = field(default_factory=list)
    home_squad: TeamSquad = field(default_factory=TeamSquad)
    away_squad: TeamSquad = field(default_factory=TeamSquad)
    cards: list[CardEvent] = field(default_factory=list)
    goals: list[GoalEvent] = field(default_factory=list)
    substitutions: list[SubEvent] = field(default_factory=list)
    incidents_reported: bool = False
    incidents_details: dict = field(default_factory=dict)
    confirmations: list[Confirmation] = field(default_factory=list)
    documents: list[dict] = field(default_factory=list)
    raw_warnings: list[str] = field(default_factory=list)


class MatchReportExtractor:
    def __init__(
        self,
        info_html: str = "",
        teams_html: str = "",
        history_html: str = "",
        spectators: str = "",
        teams_data: list[dict] | None = None,
    ):
        self.info_soup = BeautifulSoup(info_html, "lxml") if info_html else None
        self.teams_soup = BeautifulSoup(teams_html, "lxml") if teams_html else None
        self.history_soup = BeautifulSoup(history_html, "lxml") if history_html else None
        self.spectators = spectators
        self.teams_data = teams_data or []
        self.warnings: list[str] = []

    @classmethod
    def from_files(
        cls,
        info_path: Path | str | None = None,
        teams_path: Path | str | None = None,
        history_path: Path | str | None = None,
        spectators: str = "",
        teams_data: list[dict] | None = None,
    ) -> "MatchReportExtractor":
        info_html = Path(info_path).read_text(encoding="utf-8") if info_path else ""
        teams_html = Path(teams_path).read_text(encoding="utf-8") if teams_path else ""
        history_html = Path(history_path).read_text(encoding="utf-8") if history_path else ""
        return cls(
            info_html=info_html,
            teams_html=teams_html,
            history_html=history_html,
            spectators=spectators,
            teams_data=teams_data,
        )

    def extract(self) -> MatchReport:
        report = MatchReport()
        report.meta = self._extract_meta()
        report.officials = self._extract_officials()
        report.home_squad, report.away_squad = self._extract_teams()
        # SPO § 58 applies to players, trainers and Funktionsträger alike, and
        # DFBnet keeps them in separate panels. Reading only the player panel
        # dropped every trainer caution.
        report.cards = self._extract_events("Strafen für Spieler", self._parse_card)
        for heading in ("Strafen für Offizielle", "Strafen für Trainer", "Innenraum"):
            report.cards.extend(self._extract_events(heading, self._parse_official_card))
        report.goals = self._extract_events("Torschützen", self._parse_goal)
        report.substitutions = self._extract_events("Ein- und Auswechslungen", self._parse_sub)
        self._apply_substitutions(report)
        report.incidents_details = self._extract_incidents()
        report.incidents_reported = bool(
            report.incidents_details.get("text") or report.incidents_details.get("checked_labels")
        )
        report.confirmations = self._extract_confirmations()
        report.meta.referee_release_at = self._extract_referee_release()
        report.documents = self._extract_documents()
        report.raw_warnings = self.warnings
        return report

    # ------------------------------------------------------------------ helpers

    def _panel_body(self, soup: BeautifulSoup, heading: str) -> Tag | None:
        for tag in soup.find_all(class_=lambda x: x and "panel-heading" in str(x)):
            if heading.lower() in tag.get_text(" ", strip=True).lower():
                panel = tag.find_parent(class_=re.compile("panel"))
                if panel:
                    bodies = panel.find_all(class_="panel-body")
                    if bodies:
                        return bodies[-1]
        return None

    def _rows_to_dict(self, body: Tag) -> dict[str, str]:
        """Parse a panel-body made of bootstrap rows with <b>label</b> + <span>value</span>."""
        result: dict[str, str] = {}
        if not body:
            return result
        for row in body.find_all(class_="row"):
            label_tag = row.find("b")
            value_tag = row.find("span")
            if not label_tag or not value_tag:
                continue
            label = label_tag.get_text(" ", strip=True).rstrip(":")
            value = value_tag.get_text(" ", strip=True)
            if label and value and label != value:
                result[label] = value
        return result

    #: A German postcode line inside the Spielstätte block ("01157 Dresden").
    _PLZ_RE = re.compile(r"^\d{5}\s+\S")

    def _extract_venue(self) -> str:
        """Name and town of the venue, for the Mahnungsformular's "Spielort".

        The Spielstätte panel is *not* built from label/value rows like the
        others — it is four plain lines (name, street, postcode + town,
        surface). Reading it with the row parser returned an empty dict, which
        is why every Mahnung went out without a Spielort.
        """
        body = self._panel_body(self.info_soup, "Spielstätte")
        if not body:
            return ""
        zeilen = [z.strip() for z in body.get_text("\n", strip=True).splitlines() if z.strip()]
        if not zeilen:
            return ""
        name = zeilen[0]
        ort = next((z for z in zeilen[1:] if self._PLZ_RE.match(z)), "")
        return f"{name}, {ort}" if ort else name

    # ---------------------------------------------------------------- meta

    def _extract_meta(self) -> MatchMeta:
        meta = MatchMeta()
        if not self.info_soup:
            return meta

        # Wettkampfdaten panel
        wettkampf = self._rows_to_dict(self._panel_body(self.info_soup, "Wettkampfdaten"))
        meta.season = wettkampf.get("Saison", "")
        meta.match_type = wettkampf.get("Mannschaftsart", "")
        meta.league_class = wettkampf.get("Spielklasse", "")
        meta.region = wettkampf.get("Gebiet", "")
        meta.competition = wettkampf.get("Wettkampf", "")
        meta.staffel = wettkampf.get("Staffel", "")
        meta.round_ = wettkampf.get("Runde", "")

        # Spieldaten panel
        spiel = self._rows_to_dict(self._panel_body(self.info_soup, "Spieldaten"))
        meta.match_id = spiel.get("Spielkennung", "")
        meta.match_day = spiel.get("Spieltag", "")
        begegnung = spiel.get("Begegnung", "")
        if " - " in begegnung:
            meta.home_team, meta.away_team = begegnung.split(" - ", 1)
        meta.match_date = spiel.get("Spieldatum", "")
        meta.kickoff = spiel.get("Anstoß", "")
        meta.end_time = spiel.get("Spielende", "")
        meta.result = spiel.get("Ergebnis", "")
        meta.report_status = spiel.get("Spielberichtsstatus", "")

        meta.venue = self._extract_venue()

        # Prefer spectators value provided by the caller (Playwright input value).
        if self.spectators:
            meta.spectators = self.spectators
        elif self.history_soup:
            text = self.history_soup.get_text(" ", strip=True)
            m = re.search(r"Zuschauer\s*(\d+)", text)
            if m:
                meta.spectators = m.group(1)

        return meta

    # ---------------------------------------------------------------- teams

    def _extract_teams(self) -> tuple[TeamSquad, TeamSquad]:
        """Parse the Mannschaften tab. Prefer structured teams_data produced by
        Playwright JS extraction; fall back to the synthetic HTML parser.
        """
        home = TeamSquad(team="Heim")
        away = TeamSquad(team="Gast")

        # Fill team names from meta when available.
        if self.info_soup:
            meta = self._extract_meta()
            home.team_name = meta.home_team
            away.team_name = meta.away_team

        if self.teams_data:
            for raw_team in self.teams_data:
                squad = self._parse_raw_team(raw_team)
                if not home.team_name or squad.team_name == home.team_name:
                    home = squad
                    home.team = "Heim"
                elif not away.team_name or squad.team_name == away.team_name:
                    away = squad
                    away.team = "Gast"
                else:
                    # If names cannot be matched, assign to the first empty slot.
                    if not home.starting_eleven and not home.bench and not home.officials:
                        home = squad
                        home.team = "Heim"
                    else:
                        away = squad
                        away.team = "Gast"
            return home, away

        # Fallback: synthetic HTML parsing (kept for file-based replays).
        return self._extract_teams_from_html(home, away)

    def _parse_raw_team(self, raw_team: dict) -> TeamSquad:
        """Convert the JS-extracted team dictionary into a TeamSquad."""
        squad = TeamSquad(
            team_name=raw_team.get("teamName", ""),
            club_logo_id=raw_team.get("club_logo_id", ""),
        )
        for section in raw_team.get("sections", []):
            title = section.get("title", "").lower()
            players = section.get("players", [])
            for p in players:
                if p.get("is_official"):
                    squad.officials.append(
                        TeamOfficial(
                            name=p.get("name", ""),
                            roles=[b for b in p.get("badges", []) if b],
                        )
                    )
                    continue
                raw_appearances = p.get("season_appearances") or {}
                matches = [
                    SeasonAppearance(
                        match_id=m.get("match_id", ""),
                        kickoff=m.get("kickoff", ""),
                        home_team=m.get("home_team", ""),
                        away_team=m.get("away_team", ""),
                        home_team_logo_id=m.get("home_team_logo_id", ""),
                        away_team_logo_id=m.get("away_team_logo_id", ""),
                        division=m.get("division", ""),
                        competition=m.get("competition", ""),
                        minutes=int(m.get("minutes", 0) or 0),
                        match_day=m.get("match_day"),
                    )
                    for m in raw_appearances.get("matches", [])
                ]
                player = Player(
                    name=p.get("name", ""),
                    pass_number=p.get("pass_number", ""),
                    birthdate=p.get("birthdate", ""),
                    jersey_number=p.get("jersey_number", ""),
                    is_goalkeeper=p.get("is_goalkeeper", False),
                    is_captain=p.get("is_captain", False),
                    badges=[b for b in p.get("badges", []) if b],
                    photo_title=p.get("photo_title", ""),
                    photo_state=p.get("photo_state", ""),
                    photo_timestamp=p.get("photo_timestamp", ""),
                    eligible_for_team=p.get("eligible_for_team"),
                    eligible_for_club=p.get("eligible_for_club"),
                    no_championship_eligibility=p.get("no_championship_eligibility"),
                    championship_from=p.get("championship_from", ""),
                    competitive_from=p.get("competitive_from", ""),
                    guest_eligibility=p.get("guest_eligibility"),
                    second_eligibility=p.get("second_eligibility"),
                    suspension_note=p.get("suspension_note", ""),
                    player_id=p.get("player_id", ""),
                    season_appearances=SeasonAppearances(
                        count=raw_appearances.get("count", 0) or len(matches),
                        minutes=raw_appearances.get("minutes", 0)
                        or sum(m.minutes for m in matches),
                        matches=matches,
                    ),
                )
                if "startaufstellung" in title:
                    player.match_status = "starting_eleven"
                    squad.starting_eleven.append(player)
                elif "ersatz" in title:
                    player.match_status = "bench"
                    squad.bench.append(player)
                elif "nicht im kader" in title or "nicht im kad" in title:
                    player.match_status = "not_in_squad"
                    squad.not_in_squad.append(player)
                else:
                    # Unknown section: treat as bench to not lose data.
                    player.match_status = "bench"
                    squad.bench.append(player)
        return squad

    def _extract_teams_from_html(
        self, home: TeamSquad, away: TeamSquad
    ) -> tuple[TeamSquad, TeamSquad]:
        """Legacy HTML-only parser for replays without teams_data."""
        if not self.teams_soup:
            return home, away

        text = self.teams_soup.get_text("\n", strip=True)
        lines = [l.strip() for l in text.splitlines() if l.strip()]
        for i, line in enumerate(lines):
            if "Begegnung" in line and " - " in lines[i + 1]:
                parts = lines[i + 1].split(" - ", 1)
                if len(parts) == 2:
                    home.team_name, away.team_name = parts
                    break

        section = ""
        squad = home
        for table in self.teams_soup.find_all("table"):
            for tr in table.find_all("tr"):
                tds = tr.find_all(["td", "th"])
                row_text = " ".join(td.get_text(" ", strip=True) for td in tds)
                lower = row_text.lower()
                if "startaufstellung" in lower:
                    section = "starting_eleven"
                    continue
                if "ersatzspieler" in lower or "ersatz" in lower:
                    section = "bench"
                    continue
                if "auswechslung" in lower:
                    section = "bench"
                    continue
                if "nicht im kader" in lower:
                    section = "not_in_squad"
                    continue

                m = re.search(r"^(\d+)\s+([A-Za-zÄÖÜäöüß\-\s,.'()]+)$", row_text.strip())
                if m:
                    player = Player(name=m.group(2).strip(), jersey_number=m.group(1))
                    if section == "starting_eleven":
                        player.match_status = "starting_eleven"
                        squad.starting_eleven.append(player)
                    elif section == "bench":
                        player.match_status = "bench"
                        squad.bench.append(player)
                    elif section == "not_in_squad":
                        player.match_status = "not_in_squad"
                        squad.not_in_squad.append(player)
        return home, away

    def _apply_substitutions(self, report: MatchReport) -> None:
        """Update player match_status/substitutions from the events tab.

        A player coming from the bench becomes 'substituted_in', a player
        leaving the pitch becomes 'substituted_out'. Players who stay on the
        bench keep status 'bench'.
        """
        team_map = {"home": report.home_squad, "away": report.away_squad}
        for sub in report.substitutions:
            squad = team_map.get(sub.team)
            if not squad:
                continue
            # player_out must be in starting_eleven
            for player in squad.starting_eleven:
                if player.name == sub.player_out:
                    player.match_status = "substituted_out"
                    player.substitutions.append(
                        {"minute": sub.minute, "type": "out", "partner": sub.player_in}
                    )
                    break
            # player_in may be on bench or not_in_squad
            for container in (squad.bench, squad.not_in_squad):
                for player in container:
                    if player.name == sub.player_in:
                        player.match_status = "substituted_in"
                        player.substitutions.append(
                            {"minute": sub.minute, "type": "in", "partner": sub.player_out}
                        )
                        break

    # ---------------------------------------------------------------- officials

    def _extract_officials(self) -> list[Official]:
        officials = []
        if not self.info_soup:
            return officials

        body = self._panel_body(self.info_soup, "Schiedsrichter")
        if not body:
            return officials

        headers = body.find_all(class_="official-header")
        roles = ["Schiedsrichter", "1. Assistent", "2. Assistent", "4. Offizieller"]
        for idx, header in enumerate(headers):
            role = roles[idx] if idx < len(roles) else f"Offizieller {idx + 1}"
            name_tag = header.find("b")
            if not name_tag:
                continue
            name = name_tag.get_text(" ", strip=True)
            if "Bitte auswählen" in name or not name:
                continue
            # Club is the next non-empty div after the name
            club = ""
            for div in header.find_all("div"):
                txt = div.get_text(" ", strip=True)
                if txt and txt != name and "Telefon" not in txt:
                    club = txt
                    break
            officials.append(Official(role=role, name=name.split("(")[0].strip(), club=club))
        return officials

    # ---------------------------------------------------------------- events

    def _extract_events(self, heading: str, parser) -> list:
        results = []
        if not self.history_soup:
            return results
        body = self._panel_body(self.history_soup, heading)
        if not body:
            return results

        event_wrappers = body.find_all(class_=re.compile("event-header"))
        for wrapper in event_wrappers:
            classes = " ".join(wrapper.get("class", []))
            team = "away" if "away" in classes else "home"

            minute = ""
            minute_tag = wrapper.find_previous(class_="minute-value")
            if not minute_tag:
                minute_tag = wrapper.find(class_="minute-value")
            if minute_tag:
                minute = minute_tag.get_text(strip=True).replace("'", "").replace(" ", "")

            event_items = wrapper.find_all("mr-match-event")
            for item in event_items:
                parsed = parser(item, minute, team)
                if parsed:
                    if isinstance(parsed, list):
                        results.extend(parsed)
                    else:
                        results.append(parsed)
        return results

    def _person_name(self, person_tag: Tag) -> str:
        name_tag = person_tag.find(class_="person-name")
        if name_tag:
            return name_tag.get_text(" ", strip=True)
        return ""

    def _parse_card(self, item: Tag, minute: str, team: str) -> CardEvent | None:
        person = item.find(class_="person")
        if not person:
            return None
        name = self._person_name(person)
        if not name:
            return None
        event_type = person.find(class_="event-type")
        card_type = ""
        if event_type:
            type_text = event_type.get_text(" ", strip=True).lower()
            if "gelb-rot" in type_text:
                card_type = "Gelb-Rote Karte"
            elif "rot" in type_text:
                card_type = "Rote Karte"
            elif "gelb" in type_text:
                card_type = "Gelbe Karte"
        return CardEvent(minute=minute, team=team, player=name, card_type=card_type)

    def _parse_official_card(self, item: Tag, minute: str, team: str) -> CardEvent | None:
        """Same shape as a player card, but flagged as an official."""
        card = self._parse_card(item, minute, team)
        if card is None:
            return None
        card.person_kind = "offizieller"
        return card

    def _parse_goal(self, item: Tag, minute: str, team: str) -> GoalEvent | None:
        person = item.find(class_="person")
        if not person:
            return None
        name = self._person_name(person)
        if not name:
            return None
        return GoalEvent(minute=minute, team=team, scorer=name)

    def _parse_sub(self, item: Tag, minute: str, team: str) -> list[SubEvent]:
        persons = item.find_all(class_="person")
        if len(persons) < 2:
            return []
        # DFBnet renders the substitute first (arrow-left / coming from bench)
        # and the leaving player second (arrow-right / going to bench).
        player_in = self._person_name(persons[0])
        player_out = self._person_name(persons[1])
        return [SubEvent(minute=minute, team=team, player_in=player_in, player_out=player_out)]

    # ---------------------------------------------------------------- incidents

    #: Labels inside the Vorkommnisse panel that are not content themselves.
    _INCIDENT_LABELS = (
        "vorkommnisse",
        "besondere vorkommnisse",
        "gewalt",
        "diskriminierung",
        "ja",
        "nein",
        "keine",
        "keine angabe",
        "bemerkung",
        "bemerkungen",
        "sonstiges",
    )

    def _extract_incidents(self) -> dict:
        """Read the 'Vorkommnisse' panel: free text plus checkbox state.

        The Staffelleiter has to read this text himself — it is where a referee
        records what actually happened. The previous implementation looked at
        the panel and then threw everything away, returning False
        unconditionally, so the rule that reports incidents could never fire.
        """
        result: dict = {"text": "", "checked_labels": [], "fields": {}}
        if not self.history_soup:
            return result
        body = self._panel_body(self.history_soup, "Vorkommnisse")
        if not body:
            return result

        # Free text lives in a textarea, or in a plain input on some layouts.
        texts: list[str] = []
        for area in body.find_all("textarea"):
            value = (area.get("value") or area.get_text(" ", strip=True) or "").strip()
            if value:
                name = (area.get("name") or area.get("id") or "text").strip()
                result["fields"][name] = value
                texts.append(value)
        for field_tag in body.find_all("input", {"type": "text"}):
            value = (field_tag.get("value") or "").strip()
            if value:
                name = (field_tag.get("name") or field_tag.get("id") or "text").strip()
                result["fields"][name] = value
                texts.append(value)

        # Checked boxes / selected radios, with the label they belong to.
        for box in body.find_all("input", {"type": ["checkbox", "radio"]}):
            if box.get("checked") is None:
                continue
            label = self._input_label(body, box)
            if label and label.lower() not in ("nein", "keine", "keine angabe"):
                result["checked_labels"].append(label)

        # Deliberately no fallback to the panel's visible text. The real DFBnet
        # panel is a questionnaire whose static labels include "Gewalthandlung",
        # "Diskriminierungen" and "Spielabbruch als Folge der Vorkommnisse" —
        # reading them as content made every single match report a CRITICAL
        # incident finding. Verified against
        # recordings/portal_capture/08_match_report_history.html.
        result["text"] = "\n".join(dict.fromkeys(texts)).strip()
        return result

    @staticmethod
    def _input_label(body: Tag, field_tag: Tag) -> str:
        """Best-effort label for a form field: <label for>, parent or sibling."""
        field_id = field_tag.get("id")
        if field_id:
            label = body.find("label", {"for": field_id})
            if label:
                return label.get_text(" ", strip=True)
        parent_label = field_tag.find_parent("label")
        if parent_label:
            return parent_label.get_text(" ", strip=True)
        sibling = field_tag.find_next(string=True)
        return sibling.strip() if sibling else ""

    # ---------------------------------------------------------------- confirmations

    #: Static labels inside a confirmation block; never a party or a comment.
    _CONFIRMATION_LABELS = frozenset(
        {
            "Bericht bestätigt",
            "ja",
            "nein",
            "Elektronische Unterschrift",
            # Header lines of the referee release section, which directly
            # follows the last team's block.
            "Freigabe",
            "Schiedsrichter",
        }
    )
    #: "Jens Färber (6300post2M)" — the id is alphanumeric, not just digits.
    #: "Jens Färber (6300post2M)", "Jovan Michalk (63632091-Dritte)". The id may
    #: carry hyphens, dots and letters — restricting it to [A-Za-z0-9] made the
    #: parser miss the guest team's signature on every report whose id has a
    #: suffix, so the name fell through into the comment and every guest looked
    #: like it had written free text.
    _SIGNER_RE = re.compile(r"\([\w.\- ]+\)\s*$")
    #: What DFBnet leaves in the comment box when nobody typed anything.
    _LEERE_KOMMENTARE = frozenset({"-", "–", "—", ".", "/", "--", "---", "kein", "keine"})
    _TIMESTAMP_RE = re.compile(r"\d{2}\.\d{2}\.\d{2,4},\s*\d{2}:\d{2}")

    def _extract_confirmations(self) -> list[Confirmation]:
        """Read the electronic confirmation of each team.

        Real DFBnet structure, one block of seven lines per team:

            0 team name           3 "nein"                        6 timestamp
            1 "Bericht bestätigt" 4 "Elektronische Unterschrift"
            2 "ja"                5 signer "Name (kennung)"

        The party is therefore the line directly *before* the marker. Scanning
        backwards for the first non-label line mistook the previous block's
        signer for the second team's name.
        """
        confs: list[Confirmation] = []
        if not self.history_soup:
            return confs
        body = self._panel_body(self.history_soup, "Elektronische Bestätigung")
        if not body:
            return confs

        lines = [
            line.strip() for line in body.get_text("\n", strip=True).splitlines() if line.strip()
        ]

        markers = [i for i, line in enumerate(lines) if "Bericht bestätigt" in line]
        for position, idx in enumerate(markers):
            party = lines[idx - 1] if idx > 0 else ""
            if not party or party in self._CONFIRMATION_LABELS:
                self.warnings.append(f"Confirmation block at line {idx} has no party name")
                continue

            # A block ends one line before the next block's party name, so a
            # fixed length cannot be used: it would pull the next team's name
            # in as this team's comment.
            next_marker = markers[position + 1] if position + 1 < len(markers) else None
            end = (next_marker - 1) if next_marker is not None else len(lines)
            block = lines[idx + 1 : end]
            signed_by = ""
            signed_at = ""
            for line in block:
                if not signed_at and self._TIMESTAMP_RE.search(line):
                    signed_at = line
                elif not signed_by and self._SIGNER_RE.search(line):
                    signed_by = line

            # The radio state is not exposed in the static HTML — both "ja" and
            # "nein" are always present as labels, so the previous check was
            # always True. A signature plus a timestamp is the only reliable
            # evidence that the report was actually confirmed.
            confirmed = bool(signed_by and signed_at)

            confs.append(
                Confirmation(
                    party=party,
                    confirmed=confirmed,
                    signed_by=signed_by,
                    signed_at=signed_at,
                    comment=self._confirmation_comment(block, signed_by, signed_at),
                )
            )
        return confs

    @staticmethod
    def _confirmation_comment(block: list[str], signed_by: str, signed_at: str) -> str:
        """Return the free text of a confirmation block, without its own labels.

        Everything that is neither a label, the signature nor the timestamp is
        treated as a comment the confirming person typed.
        """
        skip = {label.lower() for label in MatchReportExtractor._CONFIRMATION_LABELS} | {
            "bericht bestaetigt",
            "elektronische bestätigung",
            "bestätigt am",
            "kommentar",
            "bemerkung",
            "bemerkungen",
        }
        parts: list[str] = []
        for line in block:
            candidate = line.strip()
            if not candidate or candidate.lower() in skip:
                continue
            if candidate in (signed_by, signed_at):
                continue
            # Signature and timestamp patterns, already captured separately.
            if MatchReportExtractor._SIGNER_RE.search(candidate):
                continue
            if MatchReportExtractor._TIMESTAMP_RE.search(candidate):
                continue
            parts.append(candidate)
        text = " ".join(parts).strip()
        # DFBnet writes a placeholder when nothing was typed. Reporting "-" as
        # free text sent the Staffelleiter to read a comment that is not one.
        return "" if text in MatchReportExtractor._LEERE_KOMMENTARE else text

    def _extract_referee_release(self) -> str:
        """Return the referee release timestamp from the confirmations panel.

        DFBnet shows a 'Freigabe' row for the referee with name and timestamp.
        """
        if not self.history_soup:
            return ""
        body = self._panel_body(self.history_soup, "Elektronische Bestätigung")
        if not body:
            return ""
        # Look for a control-label containing 'Freigabe' and capture the
        # following timestamp-like sibling text.
        for label in body.find_all(class_="control-label"):
            if "freigabe" in label.get_text(" ", strip=True).lower():
                parent = label.find_parent(class_="form-group")
                if parent:
                    for div in parent.find_all("div"):
                        txt = div.get_text(" ", strip=True)
                        m = re.search(r"\d{2}\.\d{2}\.\d{4},\s*\d{2}:\d{2}(:\d{2})?", txt)
                        if m:
                            return m.group(0)
        return ""

    # ---------------------------------------------------------------- documents

    def _extract_documents(self) -> list[dict]:
        docs = []
        if not self.history_soup:
            return docs
        body = self._panel_body(self.history_soup, "Dokumente")
        if not body:
            return docs
        text = body.get_text(" ", strip=True).lower()
        if "keine einträge" not in text:
            docs.append({"info": text})
        return docs
