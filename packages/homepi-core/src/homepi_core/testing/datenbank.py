"""Die Datenbank, gegen die Integrationstests laufen dürfen.

Zwei Schutzschichten, aus zwei verschiedenen Unfällen entstanden.

**Erste Schicht: nicht irgendeine Datenbank.** Integrationstests rufen
``drop_all`` auf. Zeigt ``DATABASE_URL`` gerade auf die Arbeitsdatenbank - und
auf einem Entwicklungsrechner tut sie das die meiste Zeit -, dann löscht ein
``pytest -m integration`` die Konten, an denen man eben noch gearbeitet hat.
Deshalb entscheidet nicht mehr die Umgebung allein, sondern
:func:`datenbank_fuer_tests`: sie nimmt nur eine Datenbank, die erkennbar zum
Testen da ist, und sagt sonst laut, was los ist.

**Zweite Schicht: nicht dieselbe wie beim letzten Mal.** Auch eine gemeinsame
``test`` bleibt zwischen zwei Läufen bestehen. Was ein abgebrochener Lauf
liegen lässt, sieht der nächste - und ein Test, der nur wegen eines Rests aus
dem Vorlauf grün ist, ist schlimmer als ein roter. Deshalb legt
:func:`anlegen` zu Beginn eine **eigene** Datenbank an, und :func:`wegwerfen`
räumt sie am Ende wieder weg; verdrahtet ist das im pytest-Plugin.

Die Namen hier meiden das Präfix ``test``: pytest sammelt jede importierte
Funktion ein, deren Name damit beginnt, und hätte sie in jeder Datei als
eigenen Testfall aufgerufen.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass

#: Ausdrücklich für Tests. Hat Vorrang vor DATABASE_URL, damit beides
#: nebeneinander gesetzt sein kann: die Arbeitsdatenbank für die Anwendung,
#: die Testdatenbank für pytest.
VARIABLE = "HOMEPI_TEST_DATABASE_URL"

STANDARD = "postgresql+asyncpg://app:app@127.0.0.1:15432/test"

#: Ein Name zählt als Testdatenbank, wenn er "test" ist oder auf "_test"
#: endet. Bewusst eng: "app" soll nicht durchrutschen, weil irgendwo das Wort
#: vorkommt.
ERLAUBTE_ENDUNGEN = ("_test",)

#: Endung der je Lauf angelegten Datenbank. Sie ist eine der erlaubten: was
#: hier entsteht, muss dieselbe Prüfung bestehen wie das Vorgegebene.
NACHSILBE = "_test"

#: Auf "0" gesetzt, bleibt es bei der vorgegebenen Datenbank - für den Fall,
#: dass jemand nach einem Lauf in Ruhe hineinsehen will.
SCHALTER = "HOMEPI_TEST_DATENBANK_JE_LAUF"

#: Postgres begrenzt Bezeichner auf 63 Byte.
NAMENSLAENGE = 63

#: Genau das, was ohne Anführungszeichen als Bezeichner durchgeht. Alles
#: andere kommt hier gar nicht erst in ein SQL-Kommando hinein.
ERLAUBTER_NAME = re.compile(r"^[a-z][a-z0-9_]*$")


class FalscheDatenbank(RuntimeError):
    """Der Versuch, Tests gegen eine Arbeitsdatenbank laufen zu lassen."""


def datenbankname(url: str) -> str:
    """Der letzte Pfadbestandteil, ohne Query."""
    ohne_query = url.split("?", 1)[0]
    return ohne_query.rstrip("/").rsplit("/", 1)[-1]


def ist_testdatenbank(url: str) -> bool:
    name = datenbankname(url)
    return name == "test" or name.endswith(ERLAUBTE_ENDUNGEN)


def datenbank_fuer_tests() -> str:
    """Die URL für Integrationstests - oder ein klarer Abbruch.

    Reihenfolge: ``HOMEPI_TEST_DATABASE_URL``, dann ``DATABASE_URL``, dann die
    Voreinstellung. Was dabei herauskommt, muss eine Testdatenbank sein.
    """
    url = os.environ.get(VARIABLE) or os.environ.get("DATABASE_URL") or STANDARD

    if not ist_testdatenbank(url):
        raise FalscheDatenbank(
            f"'{datenbankname(url)}' sieht nicht nach einer Testdatenbank aus.\n"
            "Integrationstests rufen drop_all auf - gegen die Arbeitsdatenbank "
            "wäre das der Verlust aller Konten.\n"
            f"Setze {VARIABLE} auf eine Datenbank namens 'test' oder '<name>_test', "
            "zum Beispiel:\n"
            f"  export {VARIABLE}='{STANDARD}'"
        )
    return url


# ---------------------------------------------------------------------------
# Eine eigene Datenbank je Lauf


def mit_datenbank(url: str, name: str) -> str:
    """Dieselbe Verbindung, andere Datenbank.

    Benutzer, Passwort, Host, Port und Query bleiben, wie sie sind - getauscht
    wird nur der letzte Pfadbestandteil.
    """
    basis, trenner, query = url.partition("?")
    kopf = basis.rstrip("/").rsplit("/", 1)[0]
    return f"{kopf}/{name}{trenner}{query}"


def dsn(url: str) -> str:
    """Die URL ohne den SQLAlchemy-Treiber, so wie asyncpg sie erwartet.

    ``postgresql+asyncpg://`` ist ein SQLAlchemy-Schema; asyncpg selbst kennt
    nur ``postgresql://``.
    """
    schema, trenner, rest = url.partition("://")
    return f"{schema.split('+', 1)[0]}{trenner}{rest}"


def name_fuer(kennung: str) -> str:
    """Ein Datenbankname, der zum Projekt gehört und als Test erkennbar ist.

    Aus ``homepi-core`` wird ``homepi_core_test``. Bewusst ableitbar statt
    zufällig: so findet man die Datenbank eines fehlgeschlagenen Laufs im psql
    wieder, und ein hart abgebrochener Lauf hinterlässt höchstens diese eine
    statt einer wachsenden Halde.
    """
    sauber = re.sub(r"[^a-z0-9]+", "_", kennung.lower()).strip("_")
    if sauber.endswith(NACHSILBE):
        sauber = sauber[: -len(NACHSILBE)]
    if not sauber or sauber[0].isdigit():
        sauber = f"homepi_{sauber}".rstrip("_")
    return sauber[: NAMENSLAENGE - len(NACHSILBE)] + NACHSILBE


def pruefe_name(name: str) -> str:
    """Lässt nur durch, was gefahrlos in ein CREATE DATABASE passt.

    Der Name kommt aus einem Verzeichnisnamen. Der ist zwar keine
    Benutzereingabe, aber er landet unmaskiert in einem SQL-Kommando - und
    Bezeichner lassen sich nicht als Parameter binden.
    """
    if not ERLAUBTER_NAME.match(name) or not name.endswith(NACHSILBE):
        raise FalscheDatenbank(
            f"'{name}' ist kein Name, unter dem hier eine Datenbank entstehen darf.\n"
            f"Erlaubt sind Kleinbuchstaben, Ziffern und Unterstriche, endend auf "
            f"'{NACHSILBE}'."
        )
    return name


async def _kommando(url: str, sql: str) -> None:
    """Ein einzelnes Kommando gegen die vorgegebene Datenbank.

    Über asyncpg statt über SQLAlchemy: ``CREATE DATABASE`` und
    ``DROP DATABASE`` laufen nicht innerhalb einer Transaktion, und eine
    SQLAlchemy-Engine öffnet für jede Verbindung eine.
    """
    import asyncpg

    verbindung = await asyncpg.connect(dsn(url))
    try:
        await verbindung.execute(sql)
    finally:
        await verbindung.close()


async def anlegen(vorlage: str, name: str) -> str:
    """Legt die Datenbank frisch an und gibt ihre URL zurück.

    Erst weg, dann neu: Was ein abgebrochener Vorlauf hinterlassen hat, soll
    diesen hier nicht beeinflussen. ``WITH (FORCE)`` trennt dabei Verbindungen,
    die noch offen sind - ohne das scheitert ein DROP an jeder vergessenen
    psql-Sitzung. Setzt Postgres 13 oder neuer voraus.
    """
    pruefe_name(name)
    await _kommando(vorlage, f'DROP DATABASE IF EXISTS "{name}" WITH (FORCE)')
    await _kommando(vorlage, f'CREATE DATABASE "{name}"')
    return mit_datenbank(vorlage, name)


async def wegwerfen(vorlage: str, name: str) -> None:
    """Räumt die Datenbank des Laufs wieder weg."""
    pruefe_name(name)
    await _kommando(vorlage, f'DROP DATABASE IF EXISTS "{name}" WITH (FORCE)')


@dataclass(slots=True)
class Lauf:
    """Die Datenbank eines Testlaufs - und was danach wiederhergestellt wird."""

    #: Die vorgegebene Datenbank. Über sie wird angelegt und weggeworfen.
    vorlage: str
    name: str
    url: str
    #: Der Wert von VARIABLE vor dem Lauf. ``None`` heißt: war nicht gesetzt.
    vorher: str | None
    #: Wird beim Aufräumen umgelegt, damit nichts zweimal geschieht.
    offen: bool = True


def abgeschaltet() -> bool:
    """Wahr, wenn ausdrücklich bei der vorgegebenen Datenbank geblieben wird."""
    return os.environ.get(SCHALTER, "1").strip().lower() in {"0", "aus", "false", "nein"}
