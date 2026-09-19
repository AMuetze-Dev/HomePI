"""Die Auswertung — rein, also in Millisekunden."""

from __future__ import annotations

from homepi_staffelpilot.dienst import GRENZE, BefundSicht, auswerten


def b(
    regel: str = "rote_karte",
    schwere: str = "kritisch",
    entscheidung: str = "offen",
    mannschaft: str = "SG Gittersee",
    monat: str = "2026-09",
) -> BefundSicht:
    return BefundSicht(
        schwere=schwere,
        entscheidung=entscheidung,
        regel=regel,
        mannschaft=mannschaft,
        monat=monat,
    )


def test_ohne_befunde_bleibt_alles_bei_null() -> None:
    werte = auswerten([])

    assert werte.befunde == 0
    assert werte.nach_regel == []


def test_die_drei_schweren_stehen_immer_da() -> None:
    """'Keine kritischen' ist eine Aussage. Eine fehlende Zeile ist keine."""
    werte = auswerten([b(schwere="hinweis")])

    assert [p.name for p in werte.nach_schwere] == ["kritisch", "warnung", "hinweis"]
    assert werte.nach_schwere[0].anzahl == 0


def test_offene_werden_getrennt_gezaehlt() -> None:
    werte = auswerten([b(), b(entscheidung="kenntnis"), b(entscheidung="verworfen")])

    assert werte.befunde == 3
    assert werte.offen == 1
    assert werte.nach_regel[0].anzahl == 3
    assert werte.nach_regel[0].offen == 1


def test_nach_haeufigkeit_sortiert() -> None:
    werte = auswerten([b(regel="selten"), b(regel="oft"), b(regel="oft")])

    assert [p.name for p in werte.nach_regel] == ["oft", "selten"]


def test_bei_gleichstand_entscheidet_der_name() -> None:
    """Ohne zweiten Schluessel tauschen zwei gleich haeufige Zeilen bei jedem
    Laden die Plaetze, und man verliert die Stelle, an der man liest."""
    zweimal = [auswerten([b(regel="b"), b(regel="a")]).nach_regel for _ in range(2)]

    assert [p.name for p in zweimal[0]] == ["a", "b"]
    assert zweimal[0] == zweimal[1]


def test_lange_listen_werden_gekappt() -> None:
    """Eine Liste mit achtzig Vereinen ist keine Auswertung mehr, sondern
    wieder die Liste, aus der sie entstanden ist."""
    werte = auswerten([b(mannschaft=f"Verein {i:02d}") for i in range(30)])

    assert len(werte.nach_mannschaft) == GRENZE


def test_leere_namen_zaehlen_nicht_mit() -> None:
    """Ein Befund ohne Mannschaft gehoert zu keinem Verein - eine Zeile mit
    leerem Namen waere ein Verein, den es nicht gibt."""
    werte = auswerten([b(mannschaft=""), b(mannschaft="SG Gittersee")])

    assert [p.name for p in werte.nach_mannschaft] == ["SG Gittersee"]


def test_die_monate_stehen_in_der_zeit_und_vollstaendig() -> None:
    """'Welcher Monat war der schlimmste' ist nicht die Frage - der Verlauf
    ist es. Eine Saison hat zehn Monate, die passen alle."""
    werte = auswerten(
        [b(monat="2026-11"), b(monat="2026-09"), b(monat="2026-10"), b(monat="2026-09")]
    )

    assert [p.name for p in werte.nach_monat] == ["2026-09", "2026-10", "2026-11"]
    assert werte.nach_monat[0].anzahl == 2
