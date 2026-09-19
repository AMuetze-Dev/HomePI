"""Der Verwarnungszähler nach § 58 SpO SFV.

Vier Stellen, an denen man sich verrechnet — alle vier stehen hier als Test:

1. Die gelbe Karte **desselben Spiels** ist verbraucht, wenn es zusätzlich
   Gelb-Rot oder Rot gab (§ 58 (1) c), (2) d).
2. Pokal und Meisterschaft werden **getrennt** gezählt (§ 58 (2)).
3. Nach jeder verwirkten Sperre beginnt der Zähler bei **null** — es sind
   immer „5 weitere", nicht die absoluten Schwellen 5/10/15 (§ 58 (2) b).
4. Im Pokal ist es die **zweite** Verwarnung (§ 58 (2) c).

Und die fünfte, die keine Rechenregel ist: ohne Antwort kommt `None` und nicht
`0`. Eine 0 wäre die Behauptung „diese Person hat keine Verwarnungen", und die
Regel schwiege daraufhin, als hätte sie geprüft.
"""

from __future__ import annotations

import datetime as dt
from typing import Any

import pytest

from homepi_pruefdienst.auskunft import GatewayAuskunft


class FalschesGateway:
    """Gibt zurück, was ihm mitgegeben wurde — und zählt die Abfragen."""

    def __init__(self, karten: list[dict[str, Any]] | None = None) -> None:
        self._karten = karten or []
        self.abfragen = 0

    def karten(self, pass_nr: str, seit: object = None) -> list[dict[str, Any]]:
        self.abfragen += 1
        return [k for k in self._karten if k.get("pass_nr", "P1") == pass_nr]


def karte(
    tag: str,
    art: str = "Gelbe Karte",
    spiel: str = "",
    wettbewerb: str = "Meisterschaft",
    pass_nr: str = "P1",
) -> dict[str, Any]:
    return {
        "datum": tag,
        "art": art,
        "wettbewerb": wettbewerb,
        "pass_nr": pass_nr,
        "spielbericht_id": spiel or f"{tag}-{wettbewerb}",
        "person": "Müller, Max",
    }


def auskunft(*karten: dict[str, Any]) -> GatewayAuskunft:
    return GatewayAuskunft(FalschesGateway(list(karten)))


class TestZaehlen:
    def test_vier_verwarnungen_sind_vier(self) -> None:
        stand = auskunft(
            karte("2026-08-02"), karte("2026-08-09"), karte("2026-08-16"), karte("2026-08-23")
        )

        assert stand.verwarnungen("P1", "Meisterschaft") == 4

    def test_ohne_karten_sind_es_null(self) -> None:
        """Hier ist 0 richtig: das Artefakt hat geantwortet, und es waren
        keine."""
        assert auskunft().verwarnungen("P1", "Meisterschaft") == 0

    def test_zwei_karten_in_einem_spiel_sind_eine_verwarnung(self) -> None:
        """Doppelt gebucht kommt vor; der Zähler zählt Spiele, nicht Zeilen."""
        stand = auskunft(
            karte("2026-08-02", spiel="S1"),
            karte("2026-08-02", spiel="S1"),
        )

        assert stand.verwarnungen("P1", "Meisterschaft") == 1

    def test_eine_karte_ohne_datum_zaehlt_nicht_mit(self) -> None:
        """Ohne Datum lässt sich nicht sagen, ob sie vor oder nach einer
        Sperre fiel. Falsch einzusortieren wäre schlimmer als auszulassen."""
        stand = auskunft(karte("2026-08-02"), karte("", spiel="S2"))

        assert stand.verwarnungen("P1", "Meisterschaft") == 1


class TestVerbrauchteKarte:
    def test_gelb_und_gelb_rot_im_selben_spiel_zaehlen_nicht(self) -> None:
        """§ 58 (1) c): die gelbe Karte gilt als verbraucht."""
        stand = auskunft(
            karte("2026-08-02", spiel="S1"),
            karte("2026-08-02", art="Gelb-Rote Karte", spiel="S1"),
        )

        assert stand.verwarnungen("P1", "Meisterschaft") == 0

    def test_eine_rote_karte_ebenso(self) -> None:
        stand = auskunft(
            karte("2026-08-02", spiel="S1"),
            karte("2026-08-02", art="Rote Karte", spiel="S1"),
        )

        assert stand.verwarnungen("P1", "Meisterschaft") == 0


class TestWettbewerbeGetrennt:
    def test_pokal_zaehlt_nicht_zur_meisterschaft(self) -> None:
        stand = auskunft(
            karte("2026-08-02"),
            karte("2026-08-09", wettbewerb="Kreispokal Herren"),
            karte("2026-08-16", wettbewerb="Kreispokal Herren"),
        )

        assert stand.verwarnungen("P1", "Meisterschaft") == 1
        assert stand.verwarnungen("P1", "Pokal") == 2

    def test_der_rohe_name_wird_in_die_kategorie_uebersetzt(self) -> None:
        """Das Artefakt kennt "Kreispokal Herren", die Regel fragt nach
        "Pokal"."""
        stand = auskunft(karte("2026-08-02", wettbewerb="Landespokal"))

        assert stand.verwarnungen("P1", "Pokal") == 1
        assert stand.verwarnungen("P1", "Meisterschaft") == 0


class TestSperre:
    def test_ohne_sperre_gibt_es_keine(self) -> None:
        assert auskunft(karte("2026-08-02")).letzte_sperre("P1", "Meisterschaft") is None

    def test_eine_gelb_rote_karte_ist_eine(self) -> None:
        stand = auskunft(karte("2026-08-02", art="Gelb-Rote Karte"))

        assert stand.letzte_sperre("P1", "Meisterschaft") == dt.date(2026, 8, 2)

    def test_die_fuenfte_verwarnung_ist_eine(self) -> None:
        erster = dt.date(2026, 8, 2)
        tage = [erster + dt.timedelta(days=7 * i) for i in range(5)]
        stand = auskunft(*[karte(tag.isoformat()) for tag in tage])

        assert stand.letzte_sperre("P1", "Meisterschaft") == tage[4]

    def test_im_pokal_schon_die_zweite(self) -> None:
        """§ 58 (2) c)."""
        stand = auskunft(
            karte("2026-08-02", wettbewerb="Kreispokal"),
            karte("2026-08-09", wettbewerb="Kreispokal"),
        )

        assert stand.letzte_sperre("P1", "Pokal") == dt.date(2026, 8, 9)

    def test_danach_faengt_der_zaehler_von_vorn_an(self) -> None:
        """§ 58 (2) b): es sind immer „5 weitere", nicht 10 absolut."""
        erster = dt.date(2026, 8, 2)
        tage = [erster + dt.timedelta(days=7 * i) for i in range(7)]
        stand = auskunft(*[karte(tag.isoformat()) for tag in tage])

        sperre = stand.letzte_sperre("P1", "Meisterschaft")

        assert sperre == tage[4]
        assert stand.verwarnungen("P1", "Meisterschaft", sperre) == 2

    def test_die_karte_des_sperrtages_zaehlt_nicht_mehr_mit(self) -> None:
        """Sie gehört zum Zähler, den sie geschlossen hat — sonst stünde der
        neue sofort wieder bei eins."""
        stand = auskunft(karte("2026-08-30"), karte("2026-09-06"))

        assert stand.verwarnungen("P1", "Meisterschaft", dt.date(2026, 8, 30)) == 1

    def test_und_die_zehnte_meldet_wieder(self) -> None:
        erster = dt.date(2026, 8, 2)
        tage = [erster + dt.timedelta(days=7 * i) for i in range(10)]
        stand = auskunft(*[karte(tag.isoformat()) for tag in tage])

        assert stand.letzte_sperre("P1", "Meisterschaft") == tage[9]
        assert stand.verwarnungen("P1", "Meisterschaft", tage[9]) == 0


class TestWeissIchNicht:
    def test_ohne_passnummer_kommt_none(self) -> None:
        """Der übliche Trainer hat keine. Ihn mit 0 zu führen hieße, für ihn
        zu behaupten, er sei unbescholten."""
        assert auskunft(karte("2026-08-02")).verwarnungen("", "Meisterschaft") is None
        assert auskunft(karte("2026-08-02")).letzte_sperre("", "Meisterschaft") is None

    def test_ein_fehler_am_gateway_ebenso(self) -> None:
        class Kaputt:
            def karten(self, pass_nr: str, seit: object = None) -> list[dict[str, Any]]:
                raise RuntimeError("Artefakt weg")

        stand = GatewayAuskunft(Kaputt())

        assert stand.verwarnungen("P1", "Meisterschaft") is None
        assert stand.letzte_sperre("P1", "Meisterschaft") is None

    def test_und_er_wird_nicht_bei_jedem_spieler_neu_versucht(self) -> None:
        class Kaputt:
            def __init__(self) -> None:
                self.versuche = 0

            def karten(self, pass_nr: str, seit: object = None) -> list[dict[str, Any]]:
                self.versuche += 1
                raise RuntimeError("Artefakt weg")

        gateway = Kaputt()
        stand = GatewayAuskunft(gateway)
        stand.verwarnungen("P1", "Meisterschaft")
        stand.letzte_sperre("P1", "Meisterschaft")

        assert gateway.versuche == 1


class TestZwischenspeicher:
    def test_dieselbe_person_wird_einmal_geholt(self) -> None:
        """Eine Elf mit Bank sind siebzehn Spieler; achtzig Berichte wären
        sonst tausend Abfragen für dieselben Antworten."""
        gateway = FalschesGateway([karte("2026-08-02")])
        stand = GatewayAuskunft(gateway)

        stand.verwarnungen("P1", "Meisterschaft")
        stand.verwarnungen("P1", "Pokal")
        stand.letzte_sperre("P1", "Meisterschaft")

        assert gateway.abfragen == 1

    def test_der_saisonbeginn_wird_mitgegeben(self) -> None:
        """Karten der vorigen Saison zählen nicht mit."""
        aufgerufen: list[object] = []

        class Merkt:
            def karten(self, pass_nr: str, seit: object = None) -> list[dict[str, Any]]:
                aufgerufen.append(seit)
                return []

        GatewayAuskunft(Merkt(), dt.date(2026, 7, 1)).verwarnungen("P1", "Meisterschaft")

        assert aufgerufen == [dt.date(2026, 7, 1)]


@pytest.mark.parametrize("art", ["Gelb-Rote Karte", "Rote Karte"])
def test_eine_sperrkarte_allein_ist_keine_verwarnung(art: str) -> None:
    stand = auskunft(karte("2026-08-02", art=art))

    assert stand.verwarnungen("P1", "Meisterschaft") == 0
