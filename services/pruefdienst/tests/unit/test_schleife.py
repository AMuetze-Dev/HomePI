"""Der ganze Weg — gegen ein nachgebautes Gateway und den Demo-Leser.

Das ist der Punkt des Leser-Protokolls: anfordern, anmelden, lesen,
einspielen, abschließen und melden lässt sich hier vollständig prüfen. Offen
bleibt allein, ob die Selektoren in `dfbnet.py` noch zur Seite passen — und
das zeigt kein Test, sondern der erste echte Lauf.
"""

from __future__ import annotations

import datetime as dt
from typing import Any

import pytest

from homepi_pruefdienst import regeln
from homepi_pruefdienst.bericht import MatchMeta, MatchReport, Player, TeamSquad
from homepi_pruefdienst.dienst import Spielzeile
from homepi_pruefdienst.gateway import GatewayFehler
from homepi_pruefdienst.leser import BeispielLeser, DemoLeser
from homepi_pruefdienst.schleife import Prueflauf

HEUTE = dt.date.today()

#: Was am Spiel steht, wenn der Bericht nicht kam. Eine leere Liste waere die
#: gefaehrlichere Auskunft: sie sieht aus wie "geprueft und sauber".
UNGELESEN = regeln.nicht_gelesen("der Prüfdienst hat ihn nicht bekommen")

STAFFEL = {
    "id": "s1",
    "name": "Stadtliga C",
    "altersklasse": "maenner",
    "spielklasse": "3.Kreisliga (C)",
    "saison": "26/27",
    "aktiv": True,
}


def zeile(kennung: str = "M-1", tage_her: int = 1, **rest: Any) -> Spielzeile:
    felder: dict[str, Any] = {
        "dfbnet_id": kennung,
        "datum": HEUTE - dt.timedelta(days=tage_her),
        "heim": "SG Gittersee",
        "gast": "SV Fortschritt",
        "ergebnis": "2 : 1",
    }
    return Spielzeile(**{**felder, **rest})


class FalschesGateway:
    """Schreibt mit, was der Dienst getan hätte."""

    def __init__(
        self,
        auftrag: dict[str, Any] | None = None,
        staffeln: list[dict[str, Any]] | None = None,
        pausiert: bool = True,
        offen: int = 0,
    ) -> None:
        self._auftrag = auftrag
        self._staffeln = [STAFFEL] if staffeln is None else staffeln
        self._pausiert = pausiert
        self._offen = offen

        self.fortschritte: list[dict[str, Any]] = []
        self.abschluesse: list[tuple[str, str, str]] = []
        self.importe: list[tuple[str, list[dict[str, Any]]]] = []
        self.meldungen: list[tuple[str, list[dict[str, Any]]]] = []
        self.zugang_geholt = 0
        self.uebernommen: list[str] = []
        self.gemeldet: list[tuple[str, str, str]] = []
        self._warteschlange = [{"id": f"u{i + 1}"} for i in range(offen)]

    # Was der Prueflauf davon braucht:
    def offener_auftrag(self) -> dict[str, Any] | None:
        return self._auftrag

    def staffeln(self) -> list[dict[str, Any]]:
        return self._staffeln

    def einstellungen(self) -> dict[str, Any]:
        return {"pruefzeitraum_tage": 30, "frist_tage": 14}

    def zugang(self) -> tuple[str, str]:
        self.zugang_geholt += 1
        return "dfbnet-benutzer", "dfbnet-passwort"

    def fortschritt(self, auftrag_id: str, **felder: Any) -> None:
        self.fortschritte.append({"id": auftrag_id, **felder})

    def abschluss(self, auftrag_id: str, zustand: str, meldung: str = "") -> None:
        self.abschluesse.append((auftrag_id, zustand, meldung))

    def einspielen(self, staffel_id: str, spiele: list[dict[str, Any]]) -> dict[str, Any]:
        self.importe.append((staffel_id, spiele))
        return {"angelegt": len(spiele), "aktualisiert": 0, "befunde": 0}

    def mannschaften_setzen(
        self, staffel_id: str, mannschaften: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        self.meldungen.append((staffel_id, mannschaften))
        return mannschaften

    def uebertragung(self) -> dict[str, Any]:
        return {
            "pausiert": self._pausiert,
            "offen": len(self._warteschlange),
            "fehler": 0,
        }

    def uebertragung_uebernehmen(self) -> dict[str, Any] | None:
        if not self._warteschlange:
            return None
        naechste = self._warteschlange.pop(0)
        self.uebernommen.append(str(naechste["id"]))
        return naechste

    def uebertragung_abschliessen(
        self, uebertragung_id: str, zustand: str, meldung: str = ""
    ) -> None:
        self.gemeldet.append((uebertragung_id, zustand, meldung))

    # Hilfen fuer die Tests:
    @property
    def protokoll(self) -> str:
        return " | ".join(str(f.get("zeile", "")) for f in self.fortschritte)

    @property
    def schritte(self) -> str:
        return " | ".join(str(f.get("schritt", "")) for f in self.fortschritte)


def lauf(gateway: Any, leser: Any = None, darf_schreiben: bool = False) -> Prueflauf:
    return Prueflauf(gateway, leser or DemoLeser(), darf_schreiben=darf_schreiben)


class TestOhneArbeit:
    def test_ohne_auftrag_passiert_nichts(self) -> None:
        gateway = FalschesGateway()

        assert lauf(gateway).runde() is False
        assert gateway.abschluesse == []
        assert gateway.zugang_geholt == 0

    def test_und_die_zugangsdaten_werden_gar_nicht_erst_geholt(self) -> None:
        """Ein Passwort, das nicht geholt wird, kann auch nicht danebengehen."""
        gateway = FalschesGateway()

        lauf(gateway).runde()

        assert gateway.zugang_geholt == 0


class TestPrueflauf:
    def test_der_ganze_weg(self) -> None:
        gateway = FalschesGateway({"id": "a1", "art": "pruflauf", "staffel_id": None})
        leser = DemoLeser({"Stadtliga C": [zeile("M-1"), zeile("M-2")]})

        assert lauf(gateway, leser).runde() is True

        assert leser.angemeldet_als == "dfbnet-benutzer"
        assert gateway.importe == [
            (
                "s1",
                [
                    {
                        "dfbnet_id": "M-1",
                        "datum": (HEUTE - dt.timedelta(days=1)).isoformat(),
                        "heim": "SG Gittersee",
                        "gast": "SV Fortschritt",
                        "ergebnis": "2 : 1",
                        "befunde": UNGELESEN,
                    },
                    {
                        "dfbnet_id": "M-2",
                        "datum": (HEUTE - dt.timedelta(days=1)).isoformat(),
                        "heim": "SG Gittersee",
                        "gast": "SV Fortschritt",
                        "ergebnis": "2 : 1",
                        "befunde": UNGELESEN,
                    },
                ],
            )
        ]
        assert gateway.abschluesse == [("a1", "fertig", "")]

    def test_der_browser_wird_auch_danach_geschlossen(self) -> None:
        """Ein Chromium, das stehenbleibt, frisst auf dem Pi ein halbes
        Gigabyte - und beim naechsten Lauf noch eins."""
        gateway = FalschesGateway({"id": "a1", "art": "pruflauf", "staffel_id": None})
        leser = DemoLeser({"Stadtliga C": [zeile()]})

        lauf(gateway, leser).runde()

        assert leser.geschlossen

    def test_der_zeitraum_kommt_aus_den_einstellungen(self) -> None:
        gateway = FalschesGateway({"id": "a1", "art": "pruflauf", "staffel_id": None})
        # 40 Tage her: ausserhalb der eingestellten 30.
        leser = DemoLeser({"Stadtliga C": [zeile("M-1", tage_her=40)]})

        lauf(gateway, leser).runde()

        assert gateway.importe == []
        assert "nichts im Zeitraum" in gateway.protokoll

    def test_nur_die_gewaehlte_staffel(self) -> None:
        zweite = {**STAFFEL, "id": "s2", "name": "Stadtliga D"}
        gateway = FalschesGateway(
            {"id": "a1", "art": "pruflauf", "staffel_id": "s2"}, staffeln=[STAFFEL, zweite]
        )
        leser = DemoLeser({"Stadtliga C": [zeile("M-1")], "Stadtliga D": [zeile("M-2")]})

        lauf(gateway, leser).runde()

        assert [staffel for staffel, _ in gateway.importe] == ["s2"]

    def test_ohne_staffel_alle_aktiven(self) -> None:
        still = {**STAFFEL, "id": "s2", "name": "Stadtliga D", "aktiv": False}
        gateway = FalschesGateway(
            {"id": "a1", "art": "pruflauf", "staffel_id": None}, staffeln=[STAFFEL, still]
        )
        leser = DemoLeser({"Stadtliga C": [zeile("M-1")], "Stadtliga D": [zeile("M-2")]})

        lauf(gateway, leser).runde()

        assert [staffel for staffel, _ in gateway.importe] == ["s1"]

    def test_ohne_aktive_staffel_ist_er_gleich_fertig(self) -> None:
        """Wer keine aktive Staffel hat, hat nichts zu pruefen - das ist kein
        Fehler, und ein Browser muss dafuer nicht starten."""
        gateway = FalschesGateway({"id": "a1", "art": "pruflauf", "staffel_id": None}, staffeln=[])
        leser = DemoLeser()

        lauf(gateway, leser).runde()

        assert gateway.abschluesse[0][1] == "fertig"
        assert leser.angemeldet_als == ""
        assert gateway.zugang_geholt == 0

    def test_und_sagt_in_der_liste_warum(self) -> None:
        """Ein Lauf, der "fertig, 0 geprueft" meldet, sieht aus wie einer, der
        nichts gefunden hat. Genau das war die verwirrende Auskunft."""
        gateway = FalschesGateway({"id": "a1", "art": "pruflauf", "staffel_id": None}, staffeln=[])

        lauf(gateway).runde()

        _, _, meldung = gateway.abschluesse[0]
        assert "Keine aktive Staffel" in meldung
        assert "Staffeln" in meldung

    def test_unbrauchbare_zeilen_werden_gemeldet_und_nicht_verschwiegen(self) -> None:
        gateway = FalschesGateway({"id": "a1", "art": "pruflauf", "staffel_id": None})
        leser = DemoLeser({"Stadtliga C": [zeile("M-1"), zeile("M-2", heim="", gast="")]})

        lauf(gateway, leser).runde()

        assert "1 Zeile(n) ohne Datum übersprungen" in gateway.protokoll
        assert len(gateway.importe[0][1]) == 1

    def test_der_fortschritt_wird_mitgeschrieben(self) -> None:
        gateway = FalschesGateway({"id": "a1", "art": "pruflauf", "staffel_id": None})
        leser = DemoLeser({"Stadtliga C": [zeile()]})

        lauf(gateway, leser).runde()

        assert "Melde mich bei DFBnet an" in gateway.schritte
        assert "Lese Stadtliga C" in gateway.schritte
        assert "Angemeldet als dfbnet-benutzer" in gateway.protokoll

    def test_das_passwort_steht_in_keiner_meldung(self) -> None:
        """Was im Protokoll steht, liest irgendwann jemand vor."""
        gateway = FalschesGateway({"id": "a1", "art": "pruflauf", "staffel_id": None})

        lauf(gateway, DemoLeser({"Stadtliga C": [zeile()]})).runde()

        assert "dfbnet-passwort" not in str(gateway.fortschritte)


class TestWennEsSchiefgeht:
    def test_der_fehler_landet_am_auftrag(self) -> None:
        """Sonst sieht der Staffelleiter eine Anzeige, die stehenbleibt, und
        weiss nicht, warum."""

        class KaputterLeser(DemoLeser):
            def anmelden(self, benutzer: str, passwort: str) -> None:
                raise RuntimeError("DFBnet antwortet nicht")

        gateway = FalschesGateway({"id": "a1", "art": "pruflauf", "staffel_id": None})

        lauf(gateway, KaputterLeser()).runde()

        assert gateway.abschluesse == [("a1", "gescheitert", "DFBnet antwortet nicht")]

    def test_und_der_browser_wird_trotzdem_geschlossen(self) -> None:
        class KaputterLeser(DemoLeser):
            def spiele(self, staffel: str, von: dt.date, bis: dt.date) -> list[Spielzeile]:
                raise RuntimeError("Seite hat sich geaendert")

        gateway = FalschesGateway({"id": "a1", "art": "pruflauf", "staffel_id": None})
        leser = KaputterLeser()

        lauf(gateway, leser).runde()

        assert leser.geschlossen

    def test_ein_stummes_gateway_laesst_den_auftrag_offen(self) -> None:
        """Dann findet ihn der naechste Start wieder - besser als ein Auftrag,
        der als fertig gilt, ohne es zu sein."""

        class StummesGateway(FalschesGateway):
            def abschluss(self, auftrag_id: str, zustand: str, meldung: str = "") -> None:
                raise GatewayFehler("weg")

        class KaputterLeser(DemoLeser):
            def anmelden(self, benutzer: str, passwort: str) -> None:
                raise RuntimeError("kaputt")

        gateway = StummesGateway({"id": "a1", "art": "pruflauf", "staffel_id": None})

        lauf(gateway, KaputterLeser()).runde()

        assert gateway.abschluesse == []


class TestInitialisierung:
    def test_sie_setzt_die_meldung(self) -> None:
        gateway = FalschesGateway({"id": "a1", "art": "initialisierung", "staffel_id": None})
        leser = DemoLeser(mannschaften_je_staffel={"Stadtliga C": [{"name": "SV Loschwitz"}]})

        lauf(gateway, leser).runde()

        assert gateway.meldungen == [("s1", [{"name": "SV Loschwitz"}])]
        assert gateway.abschluesse == [("a1", "fertig", "1 Mannschaften übernommen")]

    def test_eine_leere_meldung_ueberschreibt_nichts(self) -> None:
        """Sonst waere ein Leser, der die Meldung nicht holen kann, ein Leser,
        der jede Handkorrektur wegwirft."""
        gateway = FalschesGateway({"id": "a1", "art": "initialisierung", "staffel_id": None})

        lauf(gateway, DemoLeser()).runde()

        assert gateway.meldungen == []
        assert gateway.abschluesse == [("a1", "fertig", "Es kam keine Meldung — nichts geändert")]


class TestUebertragung:
    def test_ohne_vorgemerktes_passiert_nichts(self) -> None:
        gateway = FalschesGateway(pausiert=False, offen=0)

        assert lauf(gateway, darf_schreiben=True).runde() is False

    @pytest.mark.parametrize(
        ("pausiert", "darf_schreiben"),
        [(True, True), (False, False), (True, False)],
    )
    def test_es_geht_nichts_hinaus_ohne_beide_schalter(
        self, pausiert: bool, darf_schreiben: bool
    ) -> None:
        """Eine Pruferfreigabe ist eine Handlung, die ein Verein sieht."""
        gateway = FalschesGateway(pausiert=pausiert, offen=3)

        ergebnis = lauf(gateway, darf_schreiben=darf_schreiben).runde()

        assert ergebnis is False

    def test_mit_dem_echten_leser_wird_noch_nichts_gemeldet(self) -> None:
        """Das Eintragen ist nicht portiert. Eine Zeile auf 'fertig' zu
        setzen, ohne dass etwas passiert ist, waere die schlimmste aller
        Auskuenfte."""
        gateway = FalschesGateway(pausiert=False, offen=3)

        assert lauf(gateway, DemoLeser(), darf_schreiben=True).runde() is False
        assert gateway.gemeldet == []

        assert lauf(gateway, darf_schreiben=True).runde() is False


class TestDemoLeser:
    def test_er_merkt_sich_das_passwort_nicht(self) -> None:
        leser = DemoLeser()

        leser.anmelden("wer", "geheim")

        assert "geheim" not in str(vars(leser))

    def test_er_filtert_nach_zeitraum(self) -> None:
        leser = DemoLeser({"A": [zeile("M-1", tage_her=1), zeile("M-2", tage_her=40)]})

        gefunden = leser.spiele("A", HEUTE - dt.timedelta(days=30), HEUTE)

        assert [z.dfbnet_id for z in gefunden] == ["M-1"]

    def test_eine_unbekannte_staffel_gibt_nichts(self) -> None:
        assert DemoLeser().spiele("gibt es nicht", HEUTE, HEUTE) == []


class TestBeispielLeser:
    """Der Leser, mit dem sich der ganze Weg durchklicken laesst."""

    def test_er_erfindet_spiele_zu_jeder_staffel(self) -> None:
        gefunden = BeispielLeser().spiele(
            "Egal wie sie heisst", HEUTE - dt.timedelta(days=30), HEUTE
        )

        assert len(gefunden) == BeispielLeser.SPIELTAGE
        assert all(z.brauchbar for z in gefunden)

    def test_und_sagt_an_jeder_kennung_dass_es_eine_attrappe_ist(self) -> None:
        """Wer das in der Oberflaeche sieht, weiss, dass niemand bei DFBnet
        war."""
        gefunden = BeispielLeser().spiele("A", HEUTE - dt.timedelta(days=30), HEUTE)

        assert all(z.dfbnet_id.startswith("DEMO-") for z in gefunden)

    def test_die_spiele_liegen_im_zeitraum(self) -> None:
        von, bis = HEUTE - dt.timedelta(days=30), HEUTE

        gefunden = BeispielLeser().spiele("A", von, bis)

        assert all(z.datum is not None and von <= z.datum <= bis for z in gefunden)

    def test_ein_enger_zeitraum_liefert_weniger(self) -> None:
        assert len(BeispielLeser().spiele("A", HEUTE - dt.timedelta(days=3), HEUTE)) == 1

    def test_befunde_gibt_es_nur_am_ersten_spiel(self) -> None:
        """An jedem Spiel waere die Warteschlange voller Arbeit, die es nicht
        gibt - und "geprueft und sauber" nicht mehr von "geprueft und
        auffaellig" zu unterscheiden."""
        leser = BeispielLeser()
        spiele = leser.spiele("A", HEUTE - dt.timedelta(days=30), HEUTE)

        assert len([z for z in spiele if leser.befunde_zu(z)]) == 1

    def test_jeder_befund_traegt_den_hinweis(self) -> None:
        leser = BeispielLeser()
        erstes = leser.spiele("A", HEUTE - dt.timedelta(days=30), HEUTE)[0]

        befunde = leser.befunde_zu(erstes)

        assert befunde
        assert all("Beispieldaten" in str(b["text"]) for b in befunde)

    def test_die_mannschaften_enthalten_eine_spielgemeinschaft(self) -> None:
        """Sonst zeigt die Oberflaeche nie, wozu "pruefen" da ist."""
        assert any(m["ist_sg"] for m in BeispielLeser().mannschaften("A"))


class TestSimulierteUebertragung:
    def test_mit_beispieldaten_wird_sie_simuliert(self) -> None:
        gateway = FalschesGateway(pausiert=False, offen=2)

        assert lauf(gateway, BeispielLeser(), darf_schreiben=True).runde() is True
        assert gateway.uebernommen == ["u1", "u2"]
        assert [z for _, z, _ in gateway.gemeldet] == ["fertig", "fertig"]

    def test_und_jede_zeile_sagt_dass_sie_simuliert_ist(self) -> None:
        """Sonst steht in der Akte eine Freigabe, die es nicht gibt."""
        gateway = FalschesGateway(pausiert=False, offen=1)

        lauf(gateway, BeispielLeser(), darf_schreiben=True).runde()

        assert "Simuliert" in gateway.gemeldet[0][2]

    @pytest.mark.parametrize(("pausiert", "darf_schreiben"), [(True, True), (False, False)])
    def test_auch_simuliert_braucht_es_beide_schalter(
        self, pausiert: bool, darf_schreiben: bool
    ) -> None:
        gateway = FalschesGateway(pausiert=pausiert, offen=2)

        lauf(gateway, BeispielLeser(), darf_schreiben=darf_schreiben).runde()

        assert gateway.gemeldet == []


class TestBefundeImLauf:
    def test_der_beispiel_leser_bringt_befunde_mit(self) -> None:
        gateway = FalschesGateway({"id": "a1", "art": "pruflauf", "staffel_id": None})

        lauf(gateway, BeispielLeser()).runde()

        _, spiele = gateway.importe[0]
        assert sum(len(s["befunde"]) for s in spiele) > 0

    def test_und_sie_werden_mitgezaehlt(self) -> None:
        gateway = FalschesGateway({"id": "a1", "art": "pruflauf", "staffel_id": None})

        lauf(gateway, BeispielLeser()).runde()

        assert any(f.get("befunde") for f in gateway.fortschritte)

    def test_ein_bericht_der_nicht_kam_wird_zur_warnung(self) -> None:
        """Eine leere Liste sieht in der Warteschlange aus wie "geprueft und
        sauber" -- dieses Spiel hat aber niemand angesehen."""
        gateway = FalschesGateway({"id": "a1", "art": "pruflauf", "staffel_id": None})

        lauf(gateway, DemoLeser({"Stadtliga C": [zeile()]})).runde()

        _, spiele = gateway.importe[0]
        befunde = spiele[0]["befunde"]
        assert [b["regel"] for b in befunde] == ["bericht_ungelesen"]
        assert befunde[0]["schwere"] == "warnung"

    def test_der_katalog_laeuft_mit(self, tmp_path: Any, monkeypatch: Any) -> None:
        """Zwei Quellen, und beide laufen: die eingebauten Regeln und der
        Katalog des Staffelleiters."""
        monkeypatch.setenv("PRUEFDIENST_REGELN", str(tmp_path / "regeln"))
        from homepi_pruefdienst import katalog

        katalog.zuruecksetzen()
        bericht = MatchReport(
            meta=MatchMeta(
                match_id="M-1",
                home_team="SG Gittersee",
                away_team="SV Fortschritt",
                match_date=(HEUTE - dt.timedelta(days=1)).strftime("%d.%m.%Y"),
            ),
            home_squad=TeamSquad(
                team_name="SG Gittersee",
                starting_eleven=[Player(name=f"S{i}", pass_number=f"P{i}") for i in range(11)],
            ),
        )
        gateway = FalschesGateway({"id": "a1", "art": "pruflauf", "staffel_id": None})
        leser = DemoLeser({"Stadtliga C": [zeile("M-1")]}, berichte_je_spiel={"M-1": bericht})

        lauf(gateway, leser).runde()

        _, spiele = gateway.importe[0]
        gefunden = {b["regel"] for b in spiele[0]["befunde"]}
        # Aus regeln.py und aus 80_wechsel_und_spielfuehrer.py.
        assert "confirmation_missing" in gefunden
        assert "spielfuehrer_fehlt" in gefunden

    def test_ein_bericht_wird_durch_die_regeln_geschickt(self) -> None:
        bericht = MatchReport(
            meta=MatchMeta(
                match_id="M-1",
                home_team="SG Gittersee",
                away_team="SV Fortschritt",
                match_date=(HEUTE - dt.timedelta(days=1)).strftime("%d.%m.%Y"),
                kickoff="15:00",
                end_time="16:45",
            )
        )
        gateway = FalschesGateway({"id": "a1", "art": "pruflauf", "staffel_id": None})
        leser = DemoLeser({"Stadtliga C": [zeile("M-1")]}, berichte_je_spiel={"M-1": bericht})

        lauf(gateway, leser).runde()

        _, spiele = gateway.importe[0]
        regelnamen = [b["regel"] for b in spiele[0]["befunde"]]
        # Keine Bestaetigung im Bericht, also meldet die Regel sie an -- und
        # "bericht_ungelesen" steht gerade nicht dabei.
        assert regelnamen == ["confirmation_missing", "confirmation_missing"]
