"""Die Sätze je Vergehen.

Hier steht die Regel, die dieses Modul überhaupt rechtfertigt: **eine Lücke
ist schlimmer als ein fehlender Satzteil.** Ein Schreiben an einen Verein, in
dem "erst am " steht und danach nichts, ist ein Schreiben, das jemand
zurückschickt — oder schlimmer, eines, das vor dem Sportgericht auseinander
genommen wird.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from homepi_staffelpilot import texte

# ── Einsetzen ─────────────────────────────────────────────────────────────


def test_ein_platzhalter_wird_zum_wert() -> None:
    assert texte.fuellen("wurde {person} eingetragen.", {"person": "Max Müller"}) == (
        "wurde Max Müller eingetragen."
    )


def test_ein_abschnitt_ohne_wert_verschwindet_ganz() -> None:
    """Der Grund für die eckigen Klammern.

    Ohne sie stünde "erst am" mit einer Lücke dahinter auf einem Schreiben an
    einen Verein.
    """
    gefuellt = texte.fuellen(
        "wurde durch {verein}[ erst am {signed_at}] und damit zu spät bestätigt.",
        {"verein": "SV Loschwitz"},
    )

    assert gefuellt == "wurde durch SV Loschwitz und damit zu spät bestätigt."


def test_ein_abschnitt_mit_wert_bleibt_stehen() -> None:
    gefuellt = texte.fuellen(
        "wurde durch {verein}[ erst am {signed_at}] und damit zu spät bestätigt.",
        {"verein": "SV Loschwitz", "signed_at": "20:35"},
    )

    assert gefuellt == "wurde durch SV Loschwitz erst am 20:35 und damit zu spät bestätigt."


def test_leerzeichen_ein_wort_zu_viel_bleiben_nicht_stehen() -> None:
    """Nach einem weggefallenen Abschnitt folgen sonst zwei Leerzeichen.

    Das sieht man nicht beim Lesen, aber im ausgedruckten Schreiben.
    """
    gefuellt = texte.fuellen("a[ {fehlt}] b[ {fehlt}] c", {})

    assert gefuellt == "a b c"


def test_ein_unbekannter_platzhalter_bleibt_sichtbar() -> None:
    """Draußen vor den Klammern fällt er auf, statt still zu verschwinden.

    Eine Vorlage mit einem Tippfehler soll man sehen — nicht erst dann, wenn
    im Schreiben eine Angabe fehlt, die dort hingehört hätte.
    """
    assert "{unbekannt}" in texte.fuellen("Wert: {unbekannt}", {"person": "Max"})


def test_ein_wert_aus_leerzeichen_zaehlt_als_leer() -> None:
    assert texte.fuellen("a[ {x}] b", {"x": "   "}) == "a b"


# ── Bausteine je Regel ────────────────────────────────────────────────────


def test_die_vorlage_kennt_den_fehlenden_ordnungsdienst() -> None:
    bausteine = texte.bausteine_fuer("order_manager_missing", {"verein": "SV Loschwitz"})

    assert "kein Leiter Ordnungsdienst" in bausteine.sachverhalt
    assert "SV Loschwitz" in bausteine.sachverhalt
    assert "§ 53" in bausteine.hinweis


def test_eine_unbekannte_regel_gibt_nichts_statt_irgendetwas() -> None:
    """Lieber der Text der Prüfung als ein Satz, der zu etwas anderem passt."""
    bausteine = texte.bausteine_fuer("gibt_es_nicht", {"person": "Max"})

    assert not bausteine
    assert bausteine.sachverhalt == ""


def test_der_folgesatz_macht_die_mahnung_zur_mahnung() -> None:
    assert "Sportgericht" in texte.folgesatz()


def test_ein_eigener_folgesatz_geht_vor() -> None:
    assert texte.folgesatz("Beim nächsten Mal.") == "Beim nächsten Mal."


# ── Eigene Sätze ────────────────────────────────────────────


def test_ein_eigener_satz_ersetzt_nur_sich_selbst() -> None:
    """Wer den Sachverhalt umformuliert, soll den Paragrafen behalten."""
    eigene = texte.eigene("order_manager_missing", "fehlte der Ordnungsdienst.", "")

    assert eigene.sachverhalt == "fehlte der Ordnungsdienst."
    assert "§ 53" in eigene.hinweis


def test_ohne_eigene_saetze_gelten_die_mitgelieferten() -> None:
    assert texte.eigene("order_manager_missing", "", "") == texte.vorlage_fuer(
        "order_manager_missing"
    )


def test_eine_uebergebene_vorlage_schlaegt_die_datei() -> None:
    bausteine = texte.bausteine_fuer(
        "order_manager_missing",
        {"verein": "SV Loschwitz"},
        texte.Vorlage(sachverhalt="fehlte bei {verein} der Ordnungsdienst."),
    )

    assert bausteine.sachverhalt == "fehlte bei SV Loschwitz der Ordnungsdienst."
    assert bausteine.hinweis == ""


# ── Wenn die Datei fehlt oder kaputt ist ────────────────────────────────


@pytest.fixture
def _ohne_gedaechtnis() -> None:
    """Die Datei wird einmal gelesen und gemerkt. Fuer diese Tests nicht."""
    texte._vorlagen.cache_clear()
    yield
    texte._vorlagen.cache_clear()


@pytest.mark.usefixtures("_ohne_gedaechtnis")
def test_ohne_datei_gibt_es_keine_bausteine_statt_eines_absturzes(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Ein Entwurf ohne die schoeneren Saetze ist besser als kein Entwurf.

    Der Staffelleiter sieht dann den Text der Pruefung — und nicht eine
    Fehlerseite an der Stelle, an der ein Schreiben stehen sollte.
    """
    monkeypatch.setattr(texte, "TEXTE", tmp_path / "gibt-es-nicht.yaml")

    assert not texte.bausteine_fuer("order_manager_missing", {})
    assert texte.folgesatz() == ""


@pytest.mark.usefixtures("_ohne_gedaechtnis")
def test_eine_kaputte_datei_reisst_das_schreiben_nicht_mit(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Wer eine Zeile aendert, kann die Einrueckung zerschiessen."""
    kaputt = tmp_path / "texte.yaml"
    kaputt.write_text("regeln:\n  - [unausgeglichen\n", encoding="utf-8")
    monkeypatch.setattr(texte, "TEXTE", kaputt)

    assert not texte.bausteine_fuer("order_manager_missing", {})


@pytest.mark.usefixtures("_ohne_gedaechtnis")
def test_eine_datei_mit_einer_liste_statt_regeln_gibt_nichts(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    falsch = tmp_path / "texte.yaml"
    falsch.write_text("- eins\n- zwei\n", encoding="utf-8")
    monkeypatch.setattr(texte, "TEXTE", falsch)

    assert not texte.bausteine_fuer("order_manager_missing", {})


@pytest.mark.usefixtures("_ohne_gedaechtnis")
def test_eine_regel_ohne_saetze_gibt_nichts(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    halb = tmp_path / "texte.yaml"
    halb.write_text("regeln:\n  order_manager_missing: ja\n", encoding="utf-8")
    monkeypatch.setattr(texte, "TEXTE", halb)

    assert not texte.bausteine_fuer("order_manager_missing", {})
