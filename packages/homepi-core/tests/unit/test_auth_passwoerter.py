"""Hashing. Argon2id fuer Passwoerter, SHA-256 fuer Sitzungstoken."""

from __future__ import annotations

from homepi_core.auth.passwoerter import (
    hashe_passwort,
    hashe_token,
    muss_neu_gehasht_werden,
    passwort_stimmt,
    token_stimmt,
)


class TestPasswoerter:
    def test_richtiges_passwort_stimmt(self) -> None:
        assert passwort_stimmt(hashe_passwort("korrekt-pferd-batterie"), "korrekt-pferd-batterie")

    def test_falsches_passwort_stimmt_nicht(self) -> None:
        assert not passwort_stimmt(hashe_passwort("korrekt-pferd-batterie"), "falsch")

    def test_gleiches_passwort_ergibt_verschiedene_hashes(self) -> None:
        # Zufaelliges Salt: zwei Benutzer mit demselben Passwort duerfen in
        # der Datenbank nicht gleich aussehen.
        assert hashe_passwort("dasselbe-passwort") != hashe_passwort("dasselbe-passwort")

    def test_es_ist_argon2id(self) -> None:
        assert hashe_passwort("irgendwas-langes").startswith("$argon2id$")

    def test_kaputter_hash_wirft_nicht(self) -> None:
        # Ein unbekannter Benutzer und ein falsches Passwort sollen von
        # aussen ununterscheidbar sein - dafuer darf hier nichts fliegen.
        assert not passwort_stimmt("kein gueltiger hash", "egal")
        assert not passwort_stimmt("", "egal")

    def test_frischer_hash_braucht_kein_rehash(self) -> None:
        assert not muss_neu_gehasht_werden(hashe_passwort("korrekt-pferd-batterie"))

    def test_unbrauchbarer_hash_gilt_als_veraltet(self) -> None:
        assert muss_neu_gehasht_werden("$2b$12$alteswerk")


class TestToken:
    def test_token_stimmt(self) -> None:
        assert token_stimmt(hashe_token("abc"), "abc")

    def test_falsches_token_stimmt_nicht(self) -> None:
        assert not token_stimmt(hashe_token("abc"), "abd")

    def test_hash_ist_deterministisch(self) -> None:
        # Anders als beim Passwort: der Hash muss suchbar sein.
        assert hashe_token("abc") == hashe_token("abc")

    def test_token_taucht_im_hash_nicht_auf(self) -> None:
        assert "geheim" not in hashe_token("geheim")

    def test_hash_hat_feste_laenge(self) -> None:
        assert len(hashe_token("x")) == 64
        assert len(hashe_token("y" * 1000)) == 64
