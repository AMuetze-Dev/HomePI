"""`@regel(...)` — was eine Regel über sich selbst sagt.

Die Angaben stehen bewusst **an der Regel** und nicht in einer Tabelle
woanders. Vorher lagen sie an drei Stellen verteilt: die Schwere im
`Violation`-Aufruf im Regelcode, die Zuordnung zum Mahnungsformular in
`REGEL_ZU_BAGATELLE`, die Sportgerichtsfähigkeit in `FALLFAEHIG`. Wer eine
Regel hinzufügte, musste alle drei kennen — und wer eine entfernte, ließ
verlässlich Einträge zurück.

Jetzt gilt: eine Regel, ein Block, alles was über sie zu wissen ist.
"""

from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass, field

#: Was eine technische Regel-ID sein darf. Bewusst eng: sie landet in
#: Dateinamen, in SQL, in HTML-Attributen und in `data-`-Selektoren.
ID_MUSTER = re.compile(r"^[a-z][a-z0-9_]*$")

#: Umlaute und ß werden ausgeschrieben, nicht weggeworfen. „Größe" ergibt
#: `groesse`, nicht `gre` — eine ID soll wiedererkennbar bleiben.
UMSCHRIFT = {
    "ä": "ae",
    "ö": "oe",
    "ü": "ue",
    "Ä": "ae",
    "Ö": "oe",
    "Ü": "ue",
    "ß": "ss",
}


def id_aus_name(name: str) -> str:
    """Eine technische ID aus einem Anzeigenamen.

    Für eigene Regeln, damit `@regel(name="…")` allein genügt. Die
    mitgelieferten führen ihre ID ausdrücklich: dort wäre eine abgeleitete
    gefährlich, weil sie sich beim Umbenennen mitändert.
    """
    text = "".join(UMSCHRIFT.get(z, z) for z in (name or ""))
    text = text.lower()
    text = re.sub(r"[^a-z0-9]+", "_", text)
    text = text.strip("_")
    # Eine ID muss mit einem Buchstaben beginnen — „§ 58 Verwarnung" ergäbe
    # sonst `58_verwarnung`, was als Bezeichner unbrauchbar wäre. Führende
    # Ziffern bleiben trotzdem erhalten, nur nicht an erster Stelle allein.
    return text


#: Wie schwer der Befund wiegt. Die Namen sind die der Oberfläche.
SCHWEREN = ("hinweis", "warnung", "kritisch")

#: Welchen Weg ein Befund nimmt.
#:
#: * ``hinweis``      — nur anzeigen, kein Schriftstück
#: * ``mahnung``      — Mahnungsformular an den Verein (Bagatellsache)
#: * ``sportgericht`` — Antrag an das Sportgericht
#: * ``beides``       — beides möglich, der Staffelleiter entscheidet am Fall
WEGE = ("hinweis", "mahnung", "sportgericht", "beides")


@dataclass(frozen=True)
class Regel:
    """Eine geladene Regel mit allem, was über sie bekannt ist."""

    #: Technischer Schlüssel. Steht in der Datenbank, in der Triage-Zuordnung
    #: und auf dem Mahnungsformular — und ändert sich nie.
    id: str
    #: Was der Staffelleiter liest. Frei, mit Leerzeichen und Umlauten.
    name: str
    funktion: Callable
    schwere: str = "warnung"
    weg: str = "hinweis"
    #: Ankreuzfeld auf dem Mahnungsformular. Die Liste des Verbandes ist
    #: geschlossen — ohne Zuordnung kann diese Regel keine Mahnung erzeugen,
    #: und ein geratenes Kreuz stünde auf einem Schriftstück, das rausgeht.
    bagatelle: str = ""
    #: Der Grund, wie er im Sportgerichtsfall steht.
    grund: str = ""
    #: Fundstelle in der Spielordnung. Erscheint im Befund, damit ein Verein
    #: nachlesen kann, worauf er sich beruft.
    paragraf: str = ""
    beschreibung: str = ""
    #: Woher die Regel kam — für die Fehlermeldung, wenn sie stolpert.
    quelle: str = "eingebaut"

    @property
    def darf_mahnen(self) -> bool:
        return self.weg in ("mahnung", "beides") and bool(self.bagatelle)

    @property
    def darf_vor_gericht(self) -> bool:
        return self.weg in ("sportgericht", "beides")


class Registry:
    """Die Regeln einer Ladung. Eine je ID — die letzte gewinnt.

    Absichtlich überschreibbar: so kann eine eigene Regeldatei eine
    mitgelieferte ersetzen, ohne dass am Programm etwas geändert wird. Genau
    dafür ist sie da.
    """

    def __init__(self):
        self._regeln: dict[str, Regel] = {}
        self._ersetzt: list[str] = []

    def hinzufuegen(self, regel: Regel) -> None:
        if regel.id in self._regeln:
            self._ersetzt.append(regel.id)
        self._regeln[regel.id] = regel

    def __iter__(self):
        return iter(self._regeln.values())

    def __len__(self) -> int:
        return len(self._regeln)

    def __contains__(self, kennung: str) -> bool:
        return kennung in self._regeln

    def get(self, kennung: str) -> Regel | None:
        return self._regeln.get(kennung)

    @property
    def kennungen(self) -> list[str]:
        return sorted(self._regeln)

    @property
    def ersetzte(self) -> list[str]:
        return list(self._ersetzt)


@dataclass
class Sammler:
    """Nimmt die `@regel`-Angaben einer Datei entgegen.

    Je geladener Datei einer, damit `quelle` stimmt und zwei Dateien sich beim
    Laden nicht ins Gehege kommen.
    """

    quelle: str = "eingebaut"
    regeln: list[Regel] = field(default_factory=list)

    def dekorator(self):
        """Das `@regel(...)`, das in der Regeldatei sichtbar ist."""

        def regel(
            name: str,
            *,
            id: str = "",
            schwere: str = "warnung",
            weg: str = "hinweis",
            bagatelle: str = "",
            grund: str = "",
            paragraf: str = "",
            beschreibung: str = "",
        ):
            kennung = id or id_aus_name(name)
            if not kennung:
                raise ValueError(
                    f'Regel {name!r}: daraus lässt sich keine Kennung bilden. Bitte id="…" angeben.'
                )
            if not ID_MUSTER.match(kennung):
                raise ValueError(
                    f"Regel {name!r}: id={kennung!r} ist unbrauchbar. Erlaubt "
                    "sind Kleinbuchstaben, Ziffern und Unterstriche, beginnend "
                    "mit einem Buchstaben."
                )
            if any(r.id == kennung for r in self.regeln):
                raise ValueError(
                    f"Die Kennung {kennung!r} wird in dieser Datei zweimal "
                    "vergeben. Zwischen zwei Dateien ist das Absicht — so "
                    "ersetzt man eine Regel —, in einer Datei verschwindet die "
                    "zweite stillschweigend."
                )
            if schwere not in SCHWEREN:
                raise ValueError(
                    f"Regel {name!r}: schwere={schwere!r} gibt es nicht. "
                    f"Möglich: {', '.join(SCHWEREN)}."
                )
            if weg not in WEGE:
                raise ValueError(
                    f"Regel {name!r}: weg={weg!r} gibt es nicht. Möglich: {', '.join(WEGE)}."
                )
            if weg in ("mahnung", "beides") and not bagatelle:
                raise ValueError(
                    f"Regel {name!r}: weg={weg!r} braucht ein bagatelle=…, "
                    "sonst gibt es kein Feld zum Ankreuzen."
                )

            def einsammeln(funktion):
                self.regeln.append(
                    Regel(
                        id=kennung,
                        name=name,
                        funktion=funktion,
                        schwere=schwere,
                        weg=weg,
                        bagatelle=bagatelle,
                        grund=grund,
                        paragraf=paragraf,
                        beschreibung=beschreibung or (funktion.__doc__ or "").strip(),
                        quelle=self.quelle,
                    )
                )
                return funktion

            return einsammeln

        return regel
