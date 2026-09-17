"""Passwoerter und Sitzungstoken haschen.

Argon2id: gewinnt die Password Hashing Competition und ist der Stand, den man
2026 nimmt. Kein bcrypt (72-Byte-Grenze), kein SHA-irgendwas (viel zu schnell).

Die Parameter sind fuer einen Raspberry Pi 5 gewaehlt: 64 MB und zwei
Durchlaeufe brauchen dort rund 100 ms. Deutlich mehr wuerde eine Anmeldung
spuerbar zaeh machen, deutlich weniger verschenkt Schutz.
"""

from __future__ import annotations

import hashlib
import hmac

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerifyMismatchError

_hasher = PasswordHasher(
    time_cost=2,
    memory_cost=64 * 1024,  # 64 MB
    parallelism=1,
    hash_len=32,
    salt_len=16,
)


def hashe_passwort(passwort: str) -> str:
    return _hasher.hash(passwort)


def passwort_stimmt(hash_: str, passwort: str) -> bool:
    """Prueft. Wirft nicht - ein unbekannter Benutzer und ein falsches
    Passwort sollen von aussen ununterscheidbar sein."""
    try:
        return _hasher.verify(hash_, passwort)
    except (VerifyMismatchError, InvalidHashError, Exception):
        return False


def muss_neu_gehasht_werden(hash_: str) -> bool:
    """True, wenn die Parameter inzwischen strenger sind als beim Anlegen.
    Dann lohnt es sich, beim naechsten erfolgreichen Anmelden neu zu hashen."""
    try:
        return _hasher.check_needs_rehash(hash_)
    except InvalidHashError:
        return True


# --- Sitzungstoken ---------------------------------------------------------


def hashe_token(token: str) -> str:
    """SHA-256, nicht Argon2.

    Anders als ein Passwort hat das Token volle 256 Bit Entropie - es ist
    nicht ratbar, also braucht es keine kuenstliche Verlangsamung. Und bei
    jeder einzelnen Anfrage 100 ms zu rechnen waere untragbar.

    Gehasht wird es trotzdem: ein Datenbankabzug soll keine lebenden
    Sitzungen enthalten.
    """
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def token_stimmt(gespeicherter_hash: str, token: str) -> bool:
    # compare_digest, damit die Laufzeit nichts ueber den Treffer verraet.
    return hmac.compare_digest(gespeicherter_hash, hashe_token(token))
