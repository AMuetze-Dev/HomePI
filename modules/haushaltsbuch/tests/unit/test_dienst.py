"""Die Rechnungen des Haushaltsbuchs - ohne Datenbank, in Millisekunden.

Die Zahlen in den Abnahmetests unten stammen aus der Tabelle, die dieses
Artefakt abloest. Sie sind die eigentliche Pruefung: alles andere kann richtig
sein und trotzdem einen Monatsbeitrag falsch ausrechnen.
"""

from __future__ import annotations

import uuid
from decimal import Decimal

import pytest

from homepi_haushaltsbuch import dienst
from homepi_haushaltsbuch.dienst import (
    AnteilOhneGewicht,
    KategorieSicht,
    KontoSicht,
    PersonSicht,
    PostenSicht,
)
from homepi_haushaltsbuch.schemas import PersonBilanz


def euro(wert: str) -> Decimal:
    return Decimal(wert)


# ----------------------------------------------------------- Monatsrate


def test_monatlicher_posten_ist_seine_eigene_rate() -> None:
    assert dienst.monatsrate(euro("31.90"), 1) == euro("31.90")


def test_jaehrlicher_posten_wird_auf_zwoelf_monate_verteilt() -> None:
    # 169 / 12 = 14,0833 - aufgerundet, siehe naechster Test.
    assert dienst.monatsrate(euro("169.00"), 12) == euro("14.09")


def test_die_rate_wird_aufgerundet_und_nicht_kaufmaennisch() -> None:
    assert dienst.monatsrate(euro("549.09"), 12) == euro("45.76")


def test_zwoelf_raten_decken_die_abbuchung_immer() -> None:
    """Der eigentliche Zweck des Aufrundens.

    Kaufmaennisch gerundet fehlten bei 169 Euro vier Cent - und zwar genau in
    dem Monat, in dem die Bank zugreift.
    """
    for jahresbetrag in ("169.00", "549.09", "104.00", "0.07", "1133.47"):
        rate = dienst.monatsrate(euro(jahresbetrag), 12)
        assert rate * 12 >= euro(jahresbetrag), jahresbetrag


# ---------------------------------------------------------- Faelligkeit


def test_monatlich_ist_in_jedem_monat_faellig() -> None:
    assert dienst.faelligkeiten(1, 1) == (1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12)


def test_quartal_ab_februar_trifft_februar_mai_august_november() -> None:
    assert dienst.faelligkeiten(3, 2) == (2, 5, 8, 11)


def test_jaehrlich_trifft_genau_einen_monat() -> None:
    assert dienst.faelligkeiten(12, 1) == (1,)


@pytest.mark.parametrize(
    ("intervall", "faellig_ab", "monat", "erwartet"),
    [
        # Jaehrlich im Januar, jetzt ist November: zehnmal eingezahlt.
        (12, 1, 11, 10),
        # Jaehrlich im Maerz, jetzt November: achtmal.
        (12, 3, 11, 8),
        # Quartalsweise ab Februar - November ist selbst ein Abbuchungsmonat.
        (3, 2, 11, 0),
        (3, 2, 12, 1),
        # Monatlich: es wird nie etwas zurueckgelegt.
        (1, 1, 7, 0),
    ],
)
def test_monate_seit_der_letzten_abbuchung(
    intervall: int, faellig_ab: int, monat: int, erwartet: int
) -> None:
    assert dienst.monate_seit_faelligkeit(intervall, faellig_ab, monat) == erwartet


def test_ruecklagenstand_ist_rate_mal_vergangene_monate() -> None:
    # Amazon Music: 169,00 im Maerz, im November liegen acht Raten bereit.
    assert dienst.ruecklagenstand(euro("169.00"), 12, 3, 11) == euro("112.72")


def test_im_abbuchungsmonat_ist_die_ruecklage_aufgebraucht() -> None:
    assert dienst.ruecklagenstand(euro("549.09"), 12, 1, 1) == euro("0.00")


# ------------------------------------------------------------- Aufteilen


def test_halbe_halbe() -> None:
    assert dienst.aufteilen(euro("200.00"), [1, 1]) == [euro("100.00"), euro("100.00")]


def test_verhaeltnis_eins_zu_zwei() -> None:
    assert dienst.aufteilen(euro("600.00"), [1, 2]) == [euro("200.00"), euro("400.00")]


def test_ein_nicht_teilbarer_betrag_geht_trotzdem_voll_auf() -> None:
    """Der Restcent muss irgendwohin - sonst fehlt er auf dem Konto."""
    teile = dienst.aufteilen(euro("1133.47"), [1, 2])

    assert sum(teile) == euro("1133.47")
    assert teile == [euro("377.82"), euro("755.65")]


def test_drei_drittel_summieren_sich_zum_ganzen() -> None:
    teile = dienst.aufteilen(euro("100.00"), [1, 1, 1])

    assert sum(teile) == euro("100.00")
    assert teile == [euro("33.34"), euro("33.33"), euro("33.33")]


def test_ohne_gewicht_laesst_sich_nichts_aufteilen() -> None:
    with pytest.raises(AnteilOhneGewicht):
        dienst.aufteilen(euro("10.00"), [])


# --------------------------------------------------------- Der Monatsplan
#
# Ein kleiner, vollstaendiger Haushalt. Die Zahlen sind so gewaehlt, dass
# sich jede Behauptung im Kopf nachrechnen laesst.

AARON = PersonSicht(id=uuid.uuid4(), name="Aaron")
JESSI = PersonSicht(id=uuid.uuid4(), name="Jessi")

GEMEINSAM = KontoSicht(id=uuid.uuid4(), name="DKB1", art="verteiler", inhaber_id=None)
AARONS_KONTO = KontoSicht(id=uuid.uuid4(), name="CON1", art="verteiler", inhaber_id=AARON.id)
JESSIS_KONTO = KontoSicht(id=uuid.uuid4(), name="SPK", art="verteiler", inhaber_id=JESSI.id)

WOHNEN = KategorieSicht(id=uuid.uuid4(), name="Wohnen", zaehlt_als_sparen=False)
ANLAGE = KategorieSicht(id=uuid.uuid4(), name="Investments", zaehlt_als_sparen=True)
KONSUM = KategorieSicht(id=uuid.uuid4(), name="Konsum", zaehlt_als_sparen=False)


def posten(
    name: str,
    art: str,
    betrag: str,
    konto: KontoSicht,
    *,
    kategorie: KategorieSicht | None = None,
    intervall: int = 1,
    faellig_ab: int = 1,
    variabel: bool = False,
    aktiv: bool = True,
    anteile: dict[uuid.UUID, int] | None = None,
) -> PostenSicht:
    return PostenSicht(
        id=uuid.uuid4(),
        name=name,
        art=art,
        betrag=Decimal(betrag),
        intervall_monate=intervall,
        faelligkeitsmonat=faellig_ab,
        abbuchungstag=1,
        konto_id=konto.id,
        kategorie_id=kategorie.id if kategorie else None,
        variabel=variabel,
        aktiv=aktiv,
        anteile=tuple((person, gewicht) for person, gewicht in (anteile or {}).items()),
    )


HAUSHALT = [
    posten("Sold Aaron", "einnahme", "3000.00", AARONS_KONTO),
    posten("Sold Jessi", "einnahme", "1500.00", JESSIS_KONTO),
    # Gemeinsam, 1:2 zu Aarons Lasten.
    posten(
        "Miete",
        "ausgabe",
        "900.00",
        GEMEINSAM,
        kategorie=WOHNEN,
        anteile={JESSI.id: 1, AARON.id: 2},
    ),
    # Gemeinsam, jaehrlich im Januar, halbe-halbe.
    posten(
        "Kfz-Versicherung",
        "ausgabe",
        "600.00",
        GEMEINSAM,
        kategorie=WOHNEN,
        intervall=12,
        faellig_ab=1,
        anteile={JESSI.id: 1, AARON.id: 1},
    ),
    # Nur Aaron.
    posten("MSCI World", "ausgabe", "500.00", AARONS_KONTO, kategorie=ANLAGE),
    posten("Variabel", "ausgabe", "100.00", AARONS_KONTO, kategorie=KONSUM, variabel=True),
]

KONTEN = [GEMEINSAM, AARONS_KONTO, JESSIS_KONTO]
KATEGORIEN = [WOHNEN, ANLAGE, KONSUM]
PERSONEN = [AARON, JESSI]


def bilanz(name: str, monat: int = 6) -> PersonBilanz:
    plan = dienst.monatsplan(PERSONEN, KONTEN, KATEGORIEN, HAUSHALT, jahr=2026, monat=monat)
    return next(p for p in plan.personen if p.name == name)


def test_einnahmen_stehen_bei_der_person_der_das_konto_gehoert() -> None:
    assert bilanz("Aaron").einnahmen == euro("3000.00")
    assert bilanz("Jessi").einnahmen == euro("1500.00")


def test_gemeinsame_kosten_landen_nach_gewicht_bei_den_personen() -> None:
    # Miete 900 im Verhaeltnis 1:2 und Kfz 600/12 = 50 halbe-halbe.
    assert bilanz("Jessi").einzahlung_gemeinschaft == euro("325.00")
    assert bilanz("Aaron").einzahlung_gemeinschaft == euro("625.00")


def test_die_einzahlungen_decken_den_bedarf_genau() -> None:
    plan = dienst.monatsplan(PERSONEN, KONTEN, KATEGORIEN, HAUSHALT, jahr=2026, monat=6)

    assert sum(p.einzahlung_gemeinschaft for p in plan.personen) == plan.gemeinschaft.bedarf


def test_eigene_ausgaben_bleiben_bei_der_person() -> None:
    assert bilanz("Aaron").eigene_ausgaben == euro("600.00")
    assert bilanz("Jessi").eigene_ausgaben == euro("0.00")


def test_sparen_zaehlt_nicht_zu_den_festen_kosten() -> None:
    aaron = bilanz("Aaron")

    # Fest sind nur die Gemeinschaftsanteile: Anlage und Variabel nicht.
    assert aaron.feste_kosten == euro("625.00")
    assert aaron.sparen == euro("500.00")
    assert aaron.variabel == euro("100.00")


def test_moeglich_ist_einkommen_minus_fester_kosten() -> None:
    assert bilanz("Aaron").moeglich == euro("2375.00")


def test_rest_bleibt_nach_allem_uebrig() -> None:
    # 3000 - 625 - 500 - 100
    assert bilanz("Aaron").rest == euro("1775.00")


def test_die_sparquote_ist_ein_prozentwert_mit_einer_nachkommastelle() -> None:
    # 500 von 3000
    assert bilanz("Aaron").sparquote == euro("16.7")


def test_ohne_einnahmen_ist_die_sparquote_null_und_kein_fehler() -> None:
    """Eine frisch angelegte Person hat noch kein Konto - das darf nicht
    durch eine Division durch null auffallen."""
    niemand = PersonSicht(id=uuid.uuid4(), name="Neu")

    plan = dienst.monatsplan([niemand], [], [], [], jahr=2026, monat=6)

    assert plan.personen[0].sparquote == euro("0.0")


def test_faellig_zeigt_nur_was_die_bank_in_diesem_monat_abbucht() -> None:
    januar = dienst.monatsplan(PERSONEN, KONTEN, KATEGORIEN, HAUSHALT, jahr=2026, monat=1)
    juni = dienst.monatsplan(PERSONEN, KONTEN, KATEGORIEN, HAUSHALT, jahr=2026, monat=6)

    assert "Kfz-Versicherung" in [z.name for z in januar.faellig]
    assert "Kfz-Versicherung" not in [z.name for z in juni.faellig]


def test_ruecklagen_fuehren_nur_die_unregelmaessigen_posten() -> None:
    plan = dienst.monatsplan(PERSONEN, KONTEN, KATEGORIEN, HAUSHALT, jahr=2026, monat=6)

    assert [z.name for z in plan.ruecklagen] == ["Kfz-Versicherung"]
    # Januar abgebucht, Juni: fuenf Raten zu 50.
    assert plan.ruecklagen_summe == euro("250.00")


def test_ein_gemeinsamer_posten_ohne_aufteilung_wird_benannt() -> None:
    verwaist = posten("Niemandes Sache", "ausgabe", "10.00", GEMEINSAM, kategorie=WOHNEN)

    plan = dienst.monatsplan(
        PERSONEN, KONTEN, KATEGORIEN, [*HAUSHALT, verwaist], jahr=2026, monat=6
    )

    assert plan.gemeinschaft.ohne_aufteilung == ["Niemandes Sache"]


def test_gemeinsame_einnahmen_mindern_den_bedarf() -> None:
    kindergeld = posten(
        "Kindergeld",
        "einnahme",
        "250.00",
        GEMEINSAM,
        anteile={JESSI.id: 1, AARON.id: 1},
    )

    plan = dienst.monatsplan(
        PERSONEN, KONTEN, KATEGORIEN, [*HAUSHALT, kindergeld], jahr=2026, monat=6
    )
    jessi = next(p for p in plan.personen if p.name == "Jessi")

    assert jessi.gutschrift_gemeinschaft == euro("125.00")
    assert plan.gemeinschaft.bedarf == euro("700.00")


def test_abgeschaltete_posten_kommen_nicht_vor() -> None:
    """Ein Posten, der pausiert, soll nicht geloescht werden muessen."""
    stillgelegt = posten("Alte Versicherung", "ausgabe", "99.00", AARONS_KONTO, aktiv=False)

    plan = dienst.monatsplan(
        PERSONEN, KONTEN, KATEGORIEN, [*HAUSHALT, stillgelegt], jahr=2026, monat=6
    )

    assert "Alte Versicherung" in [z.name for z in plan.alle]
    assert bilanz("Aaron").eigene_ausgaben == euro("600.00")


def test_kategoriesummen_zaehlen_eigenes_und_anteiliges_zusammen() -> None:
    aaron = bilanz("Aaron")
    wohnen = next(k for k in aaron.nach_kategorie if k.kategorie == "Wohnen")

    # 600 Mietanteil + 25 Kfz-Anteil
    assert wohnen.betrag == euro("625.00")


# --------------------------------------------------------------- Flussbild


def test_das_flussbild_fuehrt_vom_einkommen_bis_zum_posten() -> None:
    bild = dienst.flussbild(PERSONEN, KONTEN, KATEGORIEN, HAUSHALT)
    arten = {k.id: k.art for k in bild.knoten}

    assert "einnahme" in arten.values()
    assert "posten" in arten.values()
    assert all(f.betrag > 0 for f in bild.fluesse)


def test_jeder_fluss_laeuft_nach_rechts() -> None:
    """Sonst kreuzen sich die Baender und das Bild erklaert nichts mehr."""
    bild = dienst.flussbild(PERSONEN, KONTEN, KATEGORIEN, HAUSHALT)
    ebene = {k.id: k.ebene for k in bild.knoten}

    assert all(ebene[f.von] < ebene[f.nach] for f in bild.fluesse)


def test_der_gemeinsame_topf_wird_von_beiden_gespeist() -> None:
    bild = dienst.flussbild(PERSONEN, KONTEN, KATEGORIEN, HAUSHALT)
    knoten = {k.id: k for k in bild.knoten}
    zufluss = [f for f in bild.fluesse if knoten[f.nach].beschriftung == "DKB1"]

    assert sorted(f.betrag for f in zufluss) == [euro("325.00"), euro("625.00")]


def test_ein_verbrauchskonto_haengt_am_verteilerkonto() -> None:
    """Sonst stuende es als eigene Quelle ganz links im Bild.

    Geld findet sich auf einem Verbrauchskonto nicht von selbst ein - es wird
    vom Gehaltskonto dorthin umgebucht, auch wenn dafuer kein Posten erfasst ist.
    """
    verbrauch = KontoSicht(id=uuid.uuid4(), name="CON2", art="verbrauch", inhaber_id=AARON.id)
    netflix = posten("Netflix", "ausgabe", "24.98", verbrauch, kategorie=KONSUM)

    bild = dienst.flussbild(PERSONEN, [*KONTEN, verbrauch], KATEGORIEN, [*HAUSHALT, netflix])
    knoten = {k.id: k for k in bild.knoten}
    zufluss = [f for f in bild.fluesse if knoten[f.nach].beschriftung == "CON2"]

    assert [(knoten[f.von].beschriftung, f.betrag) for f in zufluss] == [("CON1", euro("24.98"))]


def test_ein_leerer_haushalt_ergibt_ein_leeres_bild() -> None:
    bild = dienst.flussbild([], [], [], [])

    assert bild.knoten == []
    assert bild.fluesse == []
    assert bild.ebenen == 0
