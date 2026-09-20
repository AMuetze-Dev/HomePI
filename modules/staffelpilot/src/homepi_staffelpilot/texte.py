"""Die Sätze, die in einem Schreiben stehen — je Vergehen einer.

Übernommen aus `config/regeln/texte.yaml` der alten Anwendung.

Für denselben Verstoß steht jedes Mal derselbe Satz. Das ist der Sinn der
Sache: ein Schreiben, das vor dem Sportgericht landen kann, muss ein halbes
Jahr später noch erklärbar sein — Satz für Satz, ohne dass jemand nachlesen
muss, was ein Sprachmodell an dem Tag gerade formuliert hat.

**Hier wird nichts erzeugt.** Eine Vorlage wird gefüllt, und wo nichts
einzusetzen ist, verschwindet der Satzteil, statt eine Lücke zu hinterlassen.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

import yaml

#: Die Vorlagen, im Paket neben dem Vordruck.
TEXTE = Path(__file__).resolve().parent / "vordrucke" / "texte.yaml"

#: Ein Abschnitt in eckigen Klammern verschwindet ganz, wenn einer seiner
#: Platzhalter leer bleibt. So steht nirgends "erst am " mit einer Lücke
#: dahinter.
_KLAMMER = re.compile(r"\[([^\[\]]*)\]")

#: Ein Platzhalter, wie er in der Vorlage steht.
_PLATZHALTER = re.compile(r"\{(\w+)\}")


@dataclass(frozen=True)
class Bausteine:
    """Was zu einer Regel im Schreiben steht.

    Leer, wenn die Vorlage diese Regel nicht kennt. Dann bleibt es beim Text
    des Befundes -- der sagt, was war, nur eben in der Sprache der Prüfung und
    nicht in der des Verbandes.
    """

    sachverhalt: str = ""
    hinweis: str = ""

    def __bool__(self) -> bool:
        return bool(self.sachverhalt or self.hinweis)


@lru_cache(maxsize=1)
def _vorlagen() -> dict[str, object]:
    """Die Datei, einmal gelesen.

    Fehlt sie oder ist sie kaputt, gibt es keine Bausteine -- und die
    Schreiben entstehen wie vorher aus dem Befundtext. Ein Entwurf ohne die
    schöneren Sätze ist besser als keiner.
    """
    if not TEXTE.is_file():
        return {}
    try:
        geladen = yaml.safe_load(TEXTE.read_text(encoding="utf-8")) or {}
    except yaml.YAMLError:
        return {}
    return geladen if isinstance(geladen, dict) else {}


def folgesatz() -> str:
    """Der Satz, der eine Mahnung zur Mahnung macht.

    Ohne ihn wäre sie eine Notiz; ein späterer Sportgerichtsantrag beruft sich
    auf ihn.
    """
    return str(_vorlagen().get("folgesatz") or "").strip()


def bausteine_fuer(regel: str, werte: dict[str, str]) -> Bausteine:
    """Sachverhalt und Hinweis zu einer Regel, mit eingesetzten Werten."""
    regeln = _vorlagen().get("regeln")
    if not isinstance(regeln, dict):
        return Bausteine()
    eintrag = regeln.get(regel)
    if not isinstance(eintrag, dict):
        return Bausteine()
    return Bausteine(
        sachverhalt=fuellen(str(eintrag.get("sachverhalt") or ""), werte),
        hinweis=fuellen(str(eintrag.get("hinweis") or ""), werte),
    )


def fuellen(vorlage: str, werte: dict[str, str]) -> str:
    """Platzhalter einsetzen -- und weglassen, was ohne Wert dasteht.

    Zwei Regeln, und die zweite ist die wichtigere:

    * `{person}` wird zum Namen.
    * Ein Abschnitt in `[ ]` fällt **ganz** weg, sobald einer seiner
      Platzhalter leer ist. "erst am {signed_at}" ohne Zeitstempel wäre sonst
      ein angefangener Satz auf einem Schreiben an einen Verein.

    Ein Platzhalter, den niemand kennt, bleibt außerhalb der Klammern stehen,
    wie er ist: so fällt er beim Lesen auf, statt still zu verschwinden.
    """
    if not vorlage:
        return ""

    def klammer(treffer: re.Match[str]) -> str:
        inhalt = treffer.group(1)
        namen = _PLATZHALTER.findall(inhalt)
        if any(not (werte.get(name) or "").strip() for name in namen):
            return ""
        return inhalt

    text = _KLAMMER.sub(klammer, vorlage)

    def platzhalter(treffer: re.Match[str]) -> str:
        wert = werte.get(treffer.group(1))
        return wert if wert else treffer.group(0)

    return " ".join(_PLATZHALTER.sub(platzhalter, text).split())
