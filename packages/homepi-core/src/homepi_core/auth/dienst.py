"""Die Entscheidungen der Anmeldung.

Rein: keine Datenbank, kein await. Passwort-Hashing steht in ``passwoerter``,
Datenbankzugriff in ``speicher``.

Sicherheitsrelevante Regeln gehören hierher und nirgends sonst - so lassen sie
sich vollständig durchtesten, ohne dass ein Test eine Datenbank braucht.
"""

from __future__ import annotations

import re
import secrets
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from enum import StrEnum

from homepi_core import ServiceError


class Rolle(StrEnum):
    """Rechte je Artefakt. Absichtlich nur drei - jede weitere Stufe macht die
    Frage 'darf der das?' schwerer zu beantworten, nicht leichter."""

    LESER = "leser"
    NUTZER = "nutzer"
    VERWALTER = "verwalter"

    @property
    def rang(self) -> int:
        return {"leser": 1, "nutzer": 2, "verwalter": 3}[self.value]

    def deckt(self, benoetigt: Rolle) -> bool:
        """Verwalter darf alles, was ein Nutzer darf; Nutzer alles, was ein
        Leser darf."""
        return self.rang >= benoetigt.rang


# --- Fehler ----------------------------------------------------------------


class AnmeldungFehlgeschlagen(ServiceError):
    status = 401
    title = "Anmeldung fehlgeschlagen"


class NichtAngemeldet(ServiceError):
    status = 401
    title = "Nicht angemeldet"


class ZugriffVerweigert(ServiceError):
    status = 403
    title = "Zugriff verweigert"


class PasswortUngeeignet(ServiceError):
    status = 422
    title = "Passwort ungeeignet"


class BenutzerVergeben(ServiceError):
    status = 409
    title = "Benutzername bereits vergeben"


# --- Sitzungen -------------------------------------------------------------

#: 32 Byte aus secrets: 256 Bit Entropie. Kurzer als 16 Byte waere ratbar,
#: laenger bringt nichts.
TOKEN_BYTES = 32

SITZUNGSDAUER = timedelta(days=14)

#: Ab wann eine Sitzung beim Zugriff verlaengert wird. Ohne diese Schwelle
#: schriebe jede einzelne Anfrage in die Datenbank.
VERLAENGERN_AB = timedelta(days=1)


def neues_token() -> str:
    """Das Token, das der Benutzer als Cookie bekommt. Nur dieser eine Wert
    ist geheim - in der Datenbank liegt ausschliesslich sein Hash."""
    return secrets.token_urlsafe(TOKEN_BYTES)


def laeuft_ab_am(jetzt: datetime | None = None) -> datetime:
    return (jetzt or datetime.now(UTC)) + SITZUNGSDAUER


@dataclass(frozen=True, slots=True)
class Sitzungspruefung:
    gueltig: bool
    verlaengern: bool = False
    grund: str = ""


def pruefe_sitzung(laeuft_ab: datetime, jetzt: datetime | None = None) -> Sitzungspruefung:
    """Gueltig? Und lohnt sich eine Verlaengerung?

    Die Verlaengerung passiert nicht bei jedem Zugriff, sondern erst, wenn
    weniger als VERLAENGERN_AB uebrig ist - sonst schreibt jede Anfrage.
    """
    jetzt = jetzt or datetime.now(UTC)
    if laeuft_ab.tzinfo is None:
        # Aus der Datenbank kann ein naiver Zeitstempel kommen; ohne Zone
        # waere der Vergleich unten schlicht falsch.
        laeuft_ab = laeuft_ab.replace(tzinfo=UTC)

    if laeuft_ab <= jetzt:
        return Sitzungspruefung(False, grund="Sitzung abgelaufen")

    return Sitzungspruefung(True, verlaengern=(laeuft_ab - jetzt) < VERLAENGERN_AB)


# --- Passwortregeln --------------------------------------------------------

MIN_LAENGE = 12
MAX_LAENGE = 200

#: Die Klassiker. Keine vollstaendige Liste - sie faengt nur ab, was sonst
#: als erstes probiert wird.
VERBOTEN = frozenset(
    {
        "passwort1234",
        "password1234",
        "123456789012",
        "qwertzuiopas",
        "administrator",
    }
)


def pruefe_passwort(passwort: str, benutzername: str = "") -> None:
    """Wirft, wenn das Passwort untauglich ist.

    Laenge statt Zeichenklassen: eine erzwungene Sonderzeichenregel erzeugt
    'Passwort1!' und macht das Passwort nicht besser. Zwoelf Zeichen sind die
    untere Grenze, ab der eine Passphrase sinnvoll wird.
    """
    if len(passwort) < MIN_LAENGE:
        raise PasswortUngeeignet(f"Mindestens {MIN_LAENGE} Zeichen nötig")
    if len(passwort) > MAX_LAENGE:
        # Nicht aus Strenge, sondern weil Argon2 sonst beliebig lange rechnet.
        raise PasswortUngeeignet(f"Höchstens {MAX_LAENGE} Zeichen erlaubt")
    if passwort.lower() in VERBOTEN:
        raise PasswortUngeeignet("Dieses Passwort ist zu verbreitet")
    if benutzername and benutzername.lower() in passwort.lower():
        raise PasswortUngeeignet("Das Passwort darf den Benutzernamen nicht enthalten")


BENUTZERNAME_MUSTER = re.compile(r"^[a-z0-9]([a-z0-9._-]{1,30})[a-z0-9]$")


def pruefe_benutzername(name: str) -> str:
    """Normalisiert und prueft. Gibt den zu speichernden Namen zurueck."""
    normalisiert = name.strip().lower()
    if not BENUTZERNAME_MUSTER.match(normalisiert):
        raise PasswortUngeeignet(
            "Benutzername: 3 bis 32 Zeichen, Kleinbuchstaben, Ziffern, Punkt, "
            "Bindestrich, Unterstrich; nicht am Rand"
        )
    return normalisiert


# --- Rechte ----------------------------------------------------------------


def darf(rechte: dict[str, Rolle], artefakt: str, benoetigt: Rolle) -> bool:
    """Hat der Benutzer für dieses Artefakt mindestens diese Rolle?

    Rechte sind ausdrücklich **je Artefakt**. Es gibt bewusst keinen globalen
    Administrator: wer StaffelPilot verwaltet, hat damit keinerlei Zugriff auf
    die Geräte im Haus.
    """
    vorhanden = rechte.get(artefakt)
    return vorhanden is not None and vorhanden.deckt(benoetigt)
