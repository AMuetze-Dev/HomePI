"""Die Fristen aus § 59 (17), wenn ein Staffelleiter sie anders eingestellt hat.

Die Vorgabe bleibt die Spielordnung. Was hier geprüft wird, ist dreierlei: dass
jeder Wert genau das tut, was sein Name sagt; dass ohne Werte alles bleibt, wie
es war; und dass ein unbrauchbarer Wert auf die Vorgabe zurückfällt, statt den
Lauf über achtzig Berichte abzubrechen.
"""

from __future__ import annotations

from datetime import datetime

import pytest

from homepi_pruefdienst import regeln
from homepi_pruefdienst.bericht import Confirmation, MatchMeta, MatchReport

HEIM = "Post SV Dresden 2"
GAST = "SV Fortuna Dresden-Rähnitz"


def bestaetigt(heim: str = "", gast: str = "", freigabe: str = "13.06.2026 17:00") -> MatchReport:
    """Ein Spiel, das um 16:45 endet und um 17:00 freigegeben wird.

    Die Frist der Spielordnung ist damit fuer beide Mannschaften 18:00.
    """
    return MatchReport(
        meta=MatchMeta(
            match_id="633203177",
            home_team=HEIM,
            away_team=GAST,
            match_date="Sa., 13.06.26",
            kickoff="15:00 (15:00 )",
            end_time="16:45",
            referee_release_at=freigabe,
        ),
        confirmations=[
            Confirmation(party=HEIM, confirmed=True, signed_at=heim),
            Confirmation(party=GAST, confirmed=True, signed_at=gast),
        ],
    )


def spaet(report: MatchReport, werte: regeln.Regelwerte | None = None) -> list[str]:
    return [
        v.rule
        for v in regeln.pruefe(report, werte)
        if v.rule in ("confirmation_late", "release_late")
    ]


class TestKulanz:
    def test_ohne_werte_gilt_die_spielordnung(self) -> None:
        assert spaet(bestaetigt("13.06.2026 23:30", "13.06.2026 23:30")) == [
            "confirmation_late",
            "confirmation_late",
        ]

    def test_sechs_stunden_reichen_bis_mitternacht(self) -> None:
        """„Es reicht am selben Tag" -- das ist der Fall, für den es sie gibt."""
        werte = {"confirmation_late": {"kulanz": 6}}

        assert spaet(bestaetigt("13.06.2026 23:30", "13.06.2026 23:59"), werte) == []

    def test_und_nicht_weiter(self) -> None:
        werte = {"confirmation_late": {"kulanz": 6}}

        assert spaet(bestaetigt("13.06.2026 23:30", "14.06.2026 00:01"), werte) == [
            "confirmation_late"
        ]

    def test_die_frist_im_befund_ist_die_eingestellte(self) -> None:
        """Sie steht später im Schreiben an den Verein. Dort 18:00 zu nennen,
        wenn bis 20:00 gewartet wurde, wäre falsch."""
        gefunden = regeln.pruefe(
            bestaetigt("13.06.2026 21:00", "13.06.2026 17:00"),
            {"confirmation_late": {"kulanz": 2}},
        )
        befund = next(v for v in gefunden if v.rule == "confirmation_late")

        assert befund.details["deadline"] == "13.06.2026, 20:00"

    def test_die_fehlende_bestaetigung_misst_an_derselben_frist(self) -> None:
        """Sonst wäre eine Mannschaft, die noch Zeit hat, schon „abgelaufen"."""
        streng = regeln.fristen_bestaetigung({})
        locker = regeln.fristen_bestaetigung({"confirmation_late": {"kulanz": 6}})

        assert regeln._confirmation_deadline(bestaetigt(), streng) == datetime(2026, 6, 13, 18, 0)
        assert regeln._confirmation_deadline(bestaetigt(), locker) == datetime(2026, 6, 14, 0, 0)


class TestDieEinzelnenWerte:
    def test_die_uhrzeit_am_spieltag(self) -> None:
        werte = {"confirmation_late": {"frist_uhrzeit": "20:30"}}

        assert spaet(bestaetigt("13.06.2026 20:30", "13.06.2026 20:31"), werte) == [
            "confirmation_late"
        ]

    def test_die_minuten_nach_spielende(self) -> None:
        """16:45 + 120 Minuten = 18:45, und das ist später als 18:00."""
        werte = {"confirmation_late": {"nach_spielende": 120}}

        assert spaet(bestaetigt("13.06.2026 18:45", "13.06.2026 18:46"), werte) == [
            "confirmation_late"
        ]

    def test_die_minuten_nach_der_freigabe(self) -> None:
        werte = {"confirmation_late": {"nach_freigabe": 90}}
        r = bestaetigt("13.06.2026 19:20", "13.06.2026 19:21", freigabe="13.06.2026 17:50")

        assert spaet(r, werte) == ["confirmation_late"]

    def test_ohne_schiedsrichter_zaehlt_die_bestaetigung_der_heimmannschaft(self) -> None:
        """Dann tritt sie an die Stelle der Freigabe -- mit derselben Zahl."""
        werte = {"confirmation_late": {"nach_freigabe": 90}}
        r = bestaetigt("13.06.2026 18:00", "13.06.2026 19:30", freigabe="")

        assert spaet(r, werte) == []
        assert spaet(r) == ["confirmation_late"]

    def test_die_freigabe_hat_ihre_eigenen(self) -> None:
        """Was jemand bei der Bestätigung einstellt, ändert die Freigabe nicht."""
        r = bestaetigt("13.06.2026 17:30", "13.06.2026 17:30", freigabe="13.06.2026 20:00")

        assert spaet(r, {"confirmation_late": {"kulanz": 6}}) == ["release_late"]
        assert spaet(r, {"release_late": {"kulanz": 2}}) == []

    def test_uhrzeit_und_minuten_der_freigabe(self) -> None:
        r = bestaetigt("13.06.2026 17:30", "13.06.2026 17:30", freigabe="13.06.2026 20:00")

        assert spaet(r, {"release_late": {"frist_uhrzeit": "20:00"}}) == []
        assert spaet(r, {"release_late": {"nach_spielende": 195}}) == []
        assert spaet(r, {"release_late": {"nach_spielende": 194}}) == ["release_late"]


class TestUnbrauchbareWerte:
    @pytest.mark.parametrize(
        "werte",
        [
            {"frist_uhrzeit": "Mitternacht"},
            {"frist_uhrzeit": "25:00"},
            {"frist_uhrzeit": None},
            {"kulanz": "viel"},
            {"kulanz": None},
            {"kulanz": True},
            {"kulanz": -3},
            {"gibt_es_nicht": 1},
        ],
    )
    def test_sie_fallen_auf_die_vorgabe_zurueck(self, werte: dict[str, object]) -> None:
        assert regeln.fristen_bestaetigung({"confirmation_late": werte}) == (
            regeln.fristen_bestaetigung({})
        )


class TestImKatalog:
    def test_die_fristregeln_melden_ihre_parameter(self) -> None:
        je = {r["schluessel"]: r for r in regeln.katalog()}

        assert [p["schluessel"] for p in je["confirmation_late"]["parameter"]] == [
            "frist_uhrzeit",
            "nach_spielende",
            "nach_freigabe",
            "kulanz",
        ]
        assert [p["schluessel"] for p in je["release_late"]["parameter"]] == [
            "frist_uhrzeit",
            "nach_spielende",
            "kulanz",
        ]

    def test_die_gemeldeten_vorgaben_sind_die_geprueften(self) -> None:
        """Zwei Stellen mit derselben Zahl laufen auseinander. Dann stünde in
        der Oberfläche eine Vorgabe, nach der niemand prüft."""
        je = {r["schluessel"]: r for r in regeln.katalog()}
        gemeldet = {
            kennung: {p["schluessel"]: p["vorgabe"] for p in je[kennung]["parameter"]}
            for kennung in ("confirmation_late", "release_late")
        }

        assert regeln.fristen_bestaetigung(gemeldet) == regeln.fristen_bestaetigung({})
        assert regeln.fristen_freigabe(gemeldet) == regeln.fristen_freigabe({})

    def test_die_uebrigen_melden_keine(self) -> None:
        for r in regeln.katalog():
            if r["schluessel"] not in ("confirmation_late", "release_late"):
                assert r["parameter"] == []

    def test_jede_regel_erklaert_sich(self) -> None:
        """Ein Staffelleiter soll entscheiden, ob er sie braucht -- dafür muss
        dastehen, was sie tut."""
        for r in regeln.katalog():
            assert len(str(r["beschreibung"])) > 20, r["schluessel"]
