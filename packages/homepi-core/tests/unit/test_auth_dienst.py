"""Die Entscheidungen der Anmeldung - rein, ohne Datenbank, Millisekunden.

Sicherheitsrelevante Regeln gehören hierher, damit sie sich vollständig
durchtesten lassen.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from homepi_core.auth.dienst import (
    MIN_LAENGE,
    SITZUNGSDAUER,
    PasswortUngeeignet,
    Rolle,
    darf,
    laeuft_ab_am,
    neues_token,
    pruefe_benutzername,
    pruefe_passwort,
    pruefe_sitzung,
)


class TestRollen:
    def test_verwalter_deckt_alles(self) -> None:
        assert Rolle.VERWALTER.deckt(Rolle.LESER)
        assert Rolle.VERWALTER.deckt(Rolle.NUTZER)
        assert Rolle.VERWALTER.deckt(Rolle.VERWALTER)

    def test_leser_deckt_nur_sich(self) -> None:
        assert Rolle.LESER.deckt(Rolle.LESER)
        assert not Rolle.LESER.deckt(Rolle.NUTZER)

    def test_rechte_gelten_je_artefakt(self) -> None:
        # Der Kern des Modells: wer StaffelPilot verwaltet, hat damit keinen
        # Zugriff auf die Geräte im Haus.
        rechte = {"staffelpilot": Rolle.VERWALTER}

        assert darf(rechte, "staffelpilot", Rolle.VERWALTER)
        assert not darf(rechte, "geraete", Rolle.LESER)

    def test_ohne_eintrag_kein_zugriff(self) -> None:
        assert not darf({}, "geraete", Rolle.LESER)


class TestSitzung:
    def test_token_ist_lang_genug(self) -> None:
        token = neues_token()

        # 32 Byte urlsafe-base64 -> mindestens 43 Zeichen
        assert len(token) >= 43

    def test_tokens_wiederholen_sich_nicht(self) -> None:
        assert len({neues_token() for _ in range(200)}) == 200

    def test_frische_sitzung_ist_gueltig(self) -> None:
        pruefung = pruefe_sitzung(laeuft_ab_am())

        assert pruefung.gueltig
        assert not pruefung.verlaengern

    def test_abgelaufene_sitzung_ist_ungueltig(self) -> None:
        pruefung = pruefe_sitzung(datetime.now(UTC) - timedelta(seconds=1))

        assert not pruefung.gueltig
        assert "abgelaufen" in pruefung.grund

    def test_genau_jetzt_abgelaufen_zaehlt_als_ungueltig(self) -> None:
        jetzt = datetime.now(UTC)

        assert not pruefe_sitzung(jetzt, jetzt).gueltig

    def test_kurz_vor_ablauf_wird_verlaengert(self) -> None:
        # Nicht bei jedem Zugriff - sonst schreibt jede Anfrage in die DB.
        pruefung = pruefe_sitzung(datetime.now(UTC) + timedelta(hours=12))

        assert pruefung.gueltig
        assert pruefung.verlaengern

    def test_naiver_zeitstempel_wird_als_utc_gelesen(self) -> None:
        """Aus der Datenbank kann ein Zeitstempel ohne Zone kommen; ohne
        diese Annahme wäre der Vergleich schlicht falsch."""
        naiv = (datetime.now(UTC) + SITZUNGSDAUER).replace(tzinfo=None)

        assert pruefe_sitzung(naiv).gueltig


class TestPasswortregeln:
    def test_langes_passwort_geht_durch(self) -> None:
        pruefe_passwort("korrekt-pferd-batterie-heftklammer")

    def test_zu_kurz_wird_abgelehnt(self) -> None:
        with pytest.raises(PasswortUngeeignet, match=str(MIN_LAENGE)):
            pruefe_passwort("x" * (MIN_LAENGE - 1))

    def test_absurd_lang_wird_abgelehnt(self) -> None:
        # Nicht aus Strenge: Argon2 würde sonst beliebig lange rechnen.
        with pytest.raises(PasswortUngeeignet, match="Höchstens"):
            pruefe_passwort("x" * 500)

    def test_verbreitetes_passwort_wird_abgelehnt(self) -> None:
        with pytest.raises(PasswortUngeeignet, match="verbreitet"):
            pruefe_passwort("passwort1234")

    def test_gross_klein_hilft_nicht(self) -> None:
        with pytest.raises(PasswortUngeeignet, match="verbreitet"):
            pruefe_passwort("Passwort1234")

    def test_passwort_darf_den_benutzernamen_nicht_enthalten(self) -> None:
        with pytest.raises(PasswortUngeeignet, match="Benutzernamen"):
            pruefe_passwort("aaron-ist-hier-drin", "aaron")

    def test_keine_zeichenklassenpflicht(self) -> None:
        """Eine erzwungene Sonderzeichenregel erzeugt 'Passwort1!' und macht
        das Passwort nicht besser."""
        pruefe_passwort("nurkleinbuchstabenaberlang")


class TestBenutzername:
    def test_wird_normalisiert(self) -> None:
        assert pruefe_benutzername("  Aaron.M  ") == "aaron.m"

    @pytest.mark.parametrize(
        "name",
        ["ab", "-aaron", "aaron-", ".aaron", "aaron mit leer", "aaron@example.com", "x" * 40],
    )
    def test_unbrauchbare_namen(self, name: str) -> None:
        with pytest.raises(PasswortUngeeignet):
            pruefe_benutzername(name)

    @pytest.mark.parametrize("name", ["aaron", "aaron.m", "aaron_m", "aaron-m", "a1b"])
    def test_brauchbare_namen(self, name: str) -> None:
        assert pruefe_benutzername(name) == name
