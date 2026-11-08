"""Das Auswuerfeln - die einzige Stelle, an der Zufall erlaubt ist.

Zufall laesst sich nur pruefen, wenn er gezaehmt ist: jede Funktion hier
bekommt ihre Saat uebergeben und entscheidet nichts selbst. Deshalb pruefen
diese Tests nicht "es ist zufaellig", sondern die Zusagen, die auch bei
Zufall gelten muessen - jeder genau einmal, niemand zweimal in derselben
Runde, kein Duell gegen den eigenen Gruppengegner in der ersten KO-Runde.
"""

from __future__ import annotations

from itertools import pairwise

import pytest

from homepi_tischtennis import los
from homepi_tischtennis.dienst import LosUnmoeglich

VIER = ["anna", "bernd", "cem", "dana"]
SIEBEN = [*VIER, "elif", "fiete", "gesa"]


class TestGruppenAuswuerfeln:
    def test_jeder_ist_genau_einmal_dabei(self) -> None:
        gruppen = los.gruppen_auswuerfeln(SIEBEN, anzahl_gruppen=2, saat=1)

        assert sorted(t for g in gruppen for t in g) == sorted(SIEBEN)

    def test_gruppen_unterscheiden_sich_um_hoechstens_einen(self) -> None:
        gruppen = los.gruppen_auswuerfeln(SIEBEN, anzahl_gruppen=3, saat=1)

        groessen = sorted(len(g) for g in gruppen)
        assert groessen[-1] - groessen[0] <= 1

    def test_dieselbe_saat_ergibt_dasselbe_los(self) -> None:
        """Die Saat wird am Turnier gespeichert. Ohne diese Zusage waere das
        gespeicherte "so wurde gelost" keine Auskunft, sondern Dekoration."""
        assert los.gruppen_auswuerfeln(SIEBEN, 2, saat=42) == los.gruppen_auswuerfeln(
            SIEBEN, 2, saat=42
        )

    def test_verschiedene_saaten_ergeben_verschiedene_lose(self) -> None:
        """Nicht jede einzelne muss abweichen - aber nicht alle zwanzig
        duerfen gleich sein, sonst wuerfelt der Knopf gar nicht."""
        lose = {
            tuple(tuple(g) for g in los.gruppen_auswuerfeln(SIEBEN, 2, saat=s)) for s in range(20)
        }

        assert len(lose) > 1

    def test_eine_gruppe_ist_jeder_gegen_jeden(self) -> None:
        gruppen = los.gruppen_auswuerfeln(VIER, anzahl_gruppen=1, saat=1)

        assert len(gruppen) == 1
        assert sorted(gruppen[0]) == sorted(VIER)

    def test_gruppe_mit_einem_teilnehmer_wird_abgelehnt(self) -> None:
        """Wer allein in einer Gruppe steht, hat kein Spiel - und stuende
        trotzdem als Gruppensieger im Raster."""
        with pytest.raises(LosUnmoeglich):
            los.gruppen_auswuerfeln(VIER, anzahl_gruppen=3, saat=1)

    def test_weniger_als_zwei_teilnehmer_wird_abgelehnt(self) -> None:
        with pytest.raises(LosUnmoeglich):
            los.gruppen_auswuerfeln(["anna"], anzahl_gruppen=1, saat=1)


class TestBergerRunden:
    def test_jede_paarung_genau_einmal(self) -> None:
        runden = los.berger_runden(VIER)

        paarungen = [frozenset(p) for runde in runden for p in runde]
        assert len(paarungen) == 6
        assert len(set(paarungen)) == 6

    def test_niemand_spielt_zweimal_in_derselben_runde(self) -> None:
        """Der ganze Zweck der Berger-Tabelle: mit zwei Tischen laufen die
        Spiele einer Runde gleichzeitig, und niemand wird an zwei Tischen
        gebraucht."""
        for runde in los.berger_runden(SIEBEN):
            beteiligte = [t for paarung in runde for t in paarung]
            assert len(beteiligte) == len(set(beteiligte))

    def test_ungerade_zahl_laesst_je_runde_einen_aussetzen(self) -> None:
        runden = los.berger_runden(SIEBEN)

        assert len(runden) == 7
        for runde in runden:
            assert len(runde) == 3

    def test_gerade_zahl_hat_keine_aussetzer(self) -> None:
        runden = los.berger_runden(VIER)

        assert len(runden) == 3
        assert all(len(runde) == 2 for runde in runden)


class TestGruppenspiele:
    def test_runde_und_gruppe_stehen_an_jeder_begegnung(self) -> None:
        spiele = los.gruppenspiele([VIER[:2], VIER[2:]])

        assert [(s.gruppe, s.runde) for s in spiele] == [(0, 1), (1, 1)]

    def test_aufeinanderfolgende_spiele_kommen_aus_verschiedenen_gruppen(self) -> None:
        """Sonst spielt Gruppe A ihre sechs Spiele, waehrend Gruppe B
        zusieht - und am Ende sitzt die halbe Belegschaft drei Stunden
        herum."""
        spiele = los.gruppenspiele([VIER, ["elif", "fiete", "gesa", "hanna"]])

        for vorher, nachher in pairwise(spiele):
            if vorher.runde == nachher.runde:
                assert vorher.gruppe != nachher.gruppe

    def test_niemand_spielt_zwei_spiele_hintereinander(self) -> None:
        spiele = los.gruppenspiele([VIER, ["elif", "fiete", "gesa", "hanna"]])

        for vorher, nachher in pairwise(spiele):
            assert {vorher.heim, vorher.gast}.isdisjoint({nachher.heim, nachher.gast})


class TestKoRaster:
    def test_vier_teilnehmer_ergeben_zwei_halbfinals_und_ein_endspiel(self) -> None:
        raster = los.ko_raster(VIER)

        assert [s.runde for s in raster] == [1, 1, 2]
        endspiel = raster[-1]
        assert endspiel.heim.aus_spiel == raster[0].nummer
        assert endspiel.gast.aus_spiel == raster[1].nummer

    def test_die_beiden_staerksten_treffen_sich_erst_im_endspiel(self) -> None:
        raster = los.ko_raster(["erster", "zweiter", "dritter", "vierter"])

        for spiel in (s for s in raster if s.runde == 1):
            assert {spiel.heim.teilnehmer, spiel.gast.teilnehmer} != {"erster", "zweiter"}

    def test_freilose_gehen_an_die_gesetzten(self) -> None:
        """Sechs Leute, Raster fuer acht: zwei Freilose. Sie gehoeren den
        beiden Erstgesetzten, nicht dem Los - alles andere waere eine
        Belohnung fuer schlechtes Abschneiden in der Gruppe."""
        raster = los.ko_raster(["s1", "s2", "s3", "s4", "s5", "s6"])

        erste_runde = [s for s in raster if s.runde == 1]
        spieler_der_ersten_runde = {
            p.teilnehmer for s in erste_runde for p in (s.heim, s.gast) if p.teilnehmer
        }
        assert "s1" not in spieler_der_ersten_runde
        assert "s2" not in spieler_der_ersten_runde

        zweite_runde = [s for s in raster if s.runde == 2]
        direkt = {p.teilnehmer for s in zweite_runde for p in (s.heim, s.gast) if p.teilnehmer}
        assert direkt == {"s1", "s2"}

    def test_jeder_kommt_genau_einmal_vor(self) -> None:
        raster = los.ko_raster(SIEBEN)

        gesetzt = [p.teilnehmer for s in raster for p in (s.heim, s.gast) if p.teilnehmer]
        assert sorted(gesetzt) == sorted(SIEBEN)

    def test_jedes_spiel_hat_zwei_belegte_plaetze(self) -> None:
        """Ein Platz ist entweder ein Teilnehmer oder der Sieger eines
        vorherigen Spiels. Ein leerer Platz waere ein Spiel, das nie
        stattfinden kann."""
        for spiel in los.ko_raster(SIEBEN):
            for platz in (spiel.heim, spiel.gast):
                assert (platz.teilnehmer is None) != (platz.aus_spiel is None)

    def test_nummern_sind_fortlaufend(self) -> None:
        raster = los.ko_raster(SIEBEN)

        assert [s.nummer for s in raster] == list(range(1, len(raster) + 1))

    def test_zwei_teilnehmer_sind_ein_endspiel(self) -> None:
        raster = los.ko_raster(["anna", "bernd"])

        assert len(raster) == 1
        assert raster[0].runde == 1

    def test_unter_zwei_teilnehmern_gibt_es_kein_raster(self) -> None:
        with pytest.raises(LosUnmoeglich):
            los.ko_raster(["anna"])


class TestSetzliste:
    @pytest.mark.parametrize("anzahl_gruppen", [2, 3, 4, 5, 8])
    def test_kein_gruppenduell_in_der_ersten_runde(self, anzahl_gruppen: int) -> None:
        """Zwei, die gerade in der Gruppe gegeneinander gespielt haben,
        sollen sich nicht sofort wieder gegenueberstehen - sonst war die
        Gruppenphase fuer sie beide umsonst."""
        gruppen = [[f"g{g}p{p}" for p in range(4)] for g in range(anzahl_gruppen)]
        herkunft = {f"g{g}p{p}": g for g in range(anzahl_gruppen) for p in range(4)}

        setzliste = los.ko_setzliste(gruppen, weiter_pro_gruppe=2)
        raster = los.ko_raster(setzliste)

        for spiel in (s for s in raster if s.runde == 1):
            heim, gast = spiel.heim.teilnehmer, spiel.gast.teilnehmer
            assert heim is not None and gast is not None
            assert herkunft[heim] != herkunft[gast], f"{heim} gegen {gast}"

    def test_nimmt_nur_die_vorderen_plaetze(self) -> None:
        gruppen = [["a1", "a2", "a3"], ["b1", "b2", "b3"]]

        assert sorted(los.ko_setzliste(gruppen, weiter_pro_gruppe=2)) == ["a1", "a2", "b1", "b2"]

    def test_gruppensieger_stehen_vor_den_zweiten(self) -> None:
        gruppen = [["a1", "a2"], ["b1", "b2"]]

        setzliste = los.ko_setzliste(gruppen, weiter_pro_gruppe=2)

        assert setzliste.index("a1") < setzliste.index("a2")
        assert setzliste.index("b1") < setzliste.index("a2")

    def test_kleine_gruppe_liefert_weniger(self) -> None:
        """Eine Gruppe, aus der drei weiterkommen sollen, aber nur zwei
        gespielt haben, liefert zwei - und nicht eine Luecke im Raster."""
        gruppen = [["a1", "a2"], ["b1", "b2", "b3"]]

        assert len(los.ko_setzliste(gruppen, weiter_pro_gruppe=3)) == 5


class TestSchweizerPaarung:
    def test_paart_von_oben_nach_unten(self) -> None:
        paarungen, freilos = los.schweizer_paarung(VIER, bisherige=set(), freilose=set())

        assert freilos is None
        assert paarungen == [("anna", "bernd"), ("cem", "dana")]

    def test_wiederholt_keine_paarung(self) -> None:
        """Die zweite Runde darf nicht dasselbe Spiel noch einmal sein."""
        bisherige = {frozenset(("anna", "bernd")), frozenset(("cem", "dana"))}

        paarungen, _ = los.schweizer_paarung(VIER, bisherige=bisherige, freilose=set())

        assert all(frozenset(p) not in bisherige for p in paarungen)

    def test_findet_auch_die_unbequeme_loesung(self) -> None:
        """Gierig von oben gepaart laeuft man sich fest: anna-cem, dann
        bleiben bernd und dana, die schon gegeneinander gespielt haben.
        Dann muss die Paarung davor zurueckgenommen werden."""
        bisherige = {
            frozenset(("anna", "bernd")),
            frozenset(("bernd", "dana")),
            frozenset(("cem", "dana")),
        }

        paarungen, _ = los.schweizer_paarung(VIER, bisherige=bisherige, freilose=set())

        assert len(paarungen) == 2
        assert all(frozenset(p) not in bisherige for p in paarungen)

    def test_ungerade_zahl_gibt_ein_freilos_nach_unten(self) -> None:
        paarungen, freilos = los.schweizer_paarung(
            ["anna", "bernd", "cem"], bisherige=set(), freilose=set()
        )

        assert freilos == "cem"
        assert paarungen == [("anna", "bernd")]

    def test_niemand_bekommt_zwei_freilose(self) -> None:
        paarungen, freilos = los.schweizer_paarung(
            ["anna", "bernd", "cem"], bisherige=set(), freilose={"cem"}
        )

        assert freilos == "bernd"
        assert paarungen == [("anna", "cem")]

    def test_wenn_alles_schon_gespielt_ist_gibt_es_keine_runde_mehr(self) -> None:
        bisherige = {frozenset(("anna", "bernd"))}

        with pytest.raises(LosUnmoeglich):
            los.schweizer_paarung(["anna", "bernd"], bisherige=bisherige, freilose=set())


class TestPlanAuswuerfeln:
    def test_gruppen_ko_liefert_gruppen_und_gruppenspiele(self) -> None:
        plan = los.plan_auswuerfeln("gruppen_ko", SIEBEN, anzahl_gruppen=2, saat=1)

        assert len(plan.gruppen) == 2
        assert plan.begegnungen
        assert not plan.ko

    def test_ko_liefert_nur_das_raster(self) -> None:
        plan = los.plan_auswuerfeln("ko", SIEBEN, anzahl_gruppen=2, saat=1)

        assert plan.ko
        assert not plan.gruppen
        assert not plan.begegnungen

    def test_schweizer_liefert_die_erste_runde(self) -> None:
        plan = los.plan_auswuerfeln("schweizer", SIEBEN, anzahl_gruppen=2, saat=1)

        assert len(plan.begegnungen) == 3
        assert plan.freilos is not None
        assert all(begegnung.runde == 1 for begegnung in plan.begegnungen)

    def test_ohne_teilnehmer_sagt_es_das(self) -> None:
        with pytest.raises(LosUnmoeglich):
            los.plan_auswuerfeln("ko", ["anna"], anzahl_gruppen=1, saat=1)

    def test_unbekannter_modus_wird_abgelehnt(self) -> None:
        with pytest.raises(LosUnmoeglich):
            los.plan_auswuerfeln("tombola", SIEBEN, anzahl_gruppen=2, saat=1)


class TestEntzerren:
    """Wie viele Spiele liegen zwischen zwei Einsaetzen desselben Spielers?

    Eine Pause fuer jeden ist nicht immer moeglich: in einer Vierergruppe
    stehen in zwei aufeinanderfolgenden Spielen bereits alle vier Leute, das
    dritte muss also jemanden wiederholen. Deshalb verspricht `entzerren`
    keine Luecke, sondern weniger Wiederholungen - und dasselbe Spielfeld.
    """

    @staticmethod
    def wiederholungen(spiele: list[los.Begegnung], fenster: int) -> int:
        """Wie oft jemand im Fenster vor seinem Spiel schon gespielt hat."""
        return sum(
            1
            for stelle, spiel in enumerate(spiele)
            if not {spiel.heim, spiel.gast}.isdisjoint(
                {
                    wer
                    for davor in spiele[max(0, stelle - fenster) : stelle]
                    for wer in (davor.heim, davor.gast)
                }
            )
        )

    def test_zieht_ein_passendes_spiel_vor(self) -> None:
        begegnungen = [
            los.Begegnung("anna", "bernd", runde=1),
            los.Begegnung("anna", "cem", runde=2),
            los.Begegnung("cem", "dana", runde=1),
            los.Begegnung("elif", "fiete", runde=1),
        ]

        geordnet = los.entzerren(begegnungen, fenster=1)

        assert self.wiederholungen(geordnet, fenster=1) == 0
        assert geordnet[1] != begegnungen[1], "anna stand sonst zweimal hintereinander"

    def test_es_bleiben_genau_dieselben_spiele(self) -> None:
        begegnungen = [
            los.Begegnung("anna", "bernd", runde=1),
            los.Begegnung("cem", "dana", runde=1),
            los.Begegnung("anna", "cem", runde=2),
        ]

        geordnet = los.entzerren(begegnungen, fenster=2)

        assert sorted(geordnet, key=repr) == sorted(begegnungen, key=repr)

    def test_eine_unloesbare_lage_endet_trotzdem(self) -> None:
        """Anna spielt gegen alle. Da ist keine Reihenfolge besser als eine
        andere - und die Funktion liefert trotzdem einen vollstaendigen Plan,
        statt an ihrem eigenen Anspruch haengen zu bleiben."""
        begegnungen = [
            los.Begegnung("anna", "bernd", runde=1),
            los.Begegnung("anna", "cem", runde=2),
            los.Begegnung("anna", "dana", runde=3),
        ]

        geordnet = los.entzerren(begegnungen, fenster=3)

        assert len(geordnet) == 3

    def test_der_ausgewuerfelte_plan_wird_besser(self) -> None:
        """Die Zusage gilt fuer das, was tatsaechlich gespeichert wird, und
        nicht nur fuer die Hilfsfunktion. Gemessen an dem Fall, der es
        aufgedeckt hat: acht Leute, zwei Gruppen, zwei Tische."""
        acht = [*SIEBEN, "hanna"]
        gruppen = los.gruppen_auswuerfeln(acht, anzahl_gruppen=2, saat=7)
        vorher = self.wiederholungen(los.gruppenspiele(gruppen), fenster=2)

        plan = los.plan_auswuerfeln("gruppen_ko", acht, anzahl_gruppen=2, saat=7, tische=2)
        nachher = self.wiederholungen(plan.begegnungen, fenster=2)

        assert vorher > 0, "sonst prueft dieser Test nichts"
        assert nachher < vorher

    def test_bei_einem_tisch_zaehlt_nur_das_spiel_davor(self) -> None:
        acht = [*SIEBEN, "hanna"]
        plan = los.plan_auswuerfeln("gruppen_ko", acht, anzahl_gruppen=2, saat=7, tische=1)

        assert self.wiederholungen(plan.begegnungen, fenster=1) == 0
