"""Die Datenbank, gegen die Integrationstests laufen dürfen.

Der Grund für dieses Modul: Integrationstests rufen ``drop_all`` auf. Zeigt
``DATABASE_URL`` gerade auf die Arbeitsdatenbank - und auf einem
Entwicklungsrechner tut sie das die meiste Zeit -, dann löscht ein
``pytest -m integration`` die Konten, an denen man eben noch gearbeitet hat.

Deshalb entscheidet nicht mehr die Umgebung allein, sondern diese Funktion:
sie nimmt nur eine Datenbank, die erkennbar zum Testen da ist, und sagt sonst
laut, was los ist.

Der Name meidet das Präfix ``test``: pytest sammelt jede importierte
Funktion ein, deren Name damit beginnt, und hätte sie in jeder Datei als
eigenen Testfall aufgerufen.
"""

from __future__ import annotations

import os

#: Ausdrücklich für Tests. Hat Vorrang vor DATABASE_URL, damit beides
#: nebeneinander gesetzt sein kann: die Arbeitsdatenbank für die Anwendung,
#: die Testdatenbank für pytest.
VARIABLE = "HOMEPI_TEST_DATABASE_URL"

STANDARD = "postgresql+asyncpg://app:app@127.0.0.1:15432/test"

#: Ein Name zählt als Testdatenbank, wenn er "test" ist oder auf "_test"
#: endet. Bewusst eng: "app" soll nicht durchrutschen, weil irgendwo das Wort
#: vorkommt.
ERLAUBTE_ENDUNGEN = ("_test",)


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
