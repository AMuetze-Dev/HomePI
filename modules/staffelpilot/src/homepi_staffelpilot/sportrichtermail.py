"""Die Mail, die einen Sportgerichtsfall begleitet.

Woertlich uebernommen aus
`D:/DevLibrary/StaffelPilot/src/core/sportrichtermail.py`. Der Wortlaut stammt
vom Staffelleiter, uebergeben am 30.08.2026:

    Guten Tag,

    ich habe heute den Sportgerichtsfall der Spielers Redlingshoefer, Tom
    aufgrund des folgenden Sachverhalts angelegt und bitte um Bearbeitung
    dessen.

    Die Kerndaten:
    Aktenzeichen: 00042-26/27-SPG_DD
    Verein: SV Pillnitz
    Spieler: Redlingshoefer, Tom
    Grund: Feldverweis aufgrund Beleidigung
    Anlagen: Sonderbericht des Schiedsrichter

    Hinweis: Ich habe bisher keine Stellungnahmen angefordert.

Zwei Schreibfehler sind berichtigt ("des Spielers", "des Schiedsrichters") und
der Satz ist gestrafft; Aufbau, Reihenfolge der Kerndaten und Tonfall sind
seine. **Nichts wird formuliert und nichts erzeugt:** derselbe Tatbestand
ergibt jedes Mal dasselbe Schreiben, denn dieses kann vor dem Sportgericht
landen.

**Und nichts wird versendet.** Dieses Modul baut einen Entwurf, mehr nicht --
abgeschickt wird er von einem Menschen in seinem Mailprogramm. Dass es dabei
bleibt, haelt `tests/unit/test_kein_mailversand.py` fest.

Warum das Schreiben erst **nach** der Fallanlage entsteht: es beruft sich auf
das Aktenzeichen, das DFBnet vergibt. Vorher gibt es keines, und eines zu
erfinden hiesse, einem Sportrichter eine Akte zu nennen, die es nicht gibt.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

#: Das Aktenzeichen, wie der SFV es schreibt: Nummer, Saison, Kammer.
#:
#: Geprueft und nicht zerlegt -- die Nummer kommt von DFBnet, und dieses
#: Artefakt hat ihr keine Bedeutung zu entnehmen, sondern nur einen Tippfehler
#: anzusehen.
AKTENZEICHEN_MUSTER = re.compile(r"^\d{4,6}-\d{2}/\d{2}-[A-Z_]+$")

ANREDE = "Guten Tag,"

#: Steht unter dem Hinweisfeld als erster Vorschlag, weil es der Normalfall
#: ist. Keine Voreinstellung: das Feld darf mit Absicht leer bleiben.
HINWEIS_VORSCHLAG = "Ich habe bisher keine Stellungnahmen angefordert."


@dataclass(frozen=True)
class Fall:
    """Ein Sportgerichtsfall, soweit die Mail ihn braucht."""

    #: Von DFBnet. Leer, bis der Fall wirklich angelegt wurde -- und ein
    #: leeres ist der Grund, eine Mail **nicht** vorzubereiten, statt sie mit
    #: einer Luecke hinauszugeben.
    aktenzeichen: str = ""
    #: Der Verein, gegen den der Fall geht, nicht der Heimverein.
    verein: str = ""
    #: "Nachname, Vorname" -- so fuehrt DFBnet seine Spieler.
    angeklagter: str = ""
    #: Warum, in den Worten des Staffelleiters: "Feldverweis aufgrund
    #: Beleidigung".
    grund: str = ""
    #: Freitext, von Fall zu Fall derselbe. Leer laesst die Zeile weg.
    anlagen: str = ""
    #: Freitext, leer erlaubt. Meistens `HINWEIS_VORSCHLAG`, aber das
    #: entscheidet der Staffelleiter je Fall.
    hinweis: str = ""

    def fehlende_felder(self) -> list[str]:
        """Was noch fehlt, bevor dieser Fall hinausgehen kann."""
        pflicht = {
            "Aktenzeichen": self.aktenzeichen,
            "Verein": self.verein,
            "Angeklagter": self.angeklagter,
            "Grund": self.grund,
        }
        return [name for name, wert in pflicht.items() if not wert.strip()]

    @property
    def vollstaendig(self) -> bool:
        return not self.fehlende_felder()

    @property
    def aktenzeichen_plausibel(self) -> bool:
        """Ob das Aktenzeichen wie eines aussieht. Ein Hinweis, keine Sperre.

        Der Verband darf das Format aendern, und ein Fall darf nicht
        unversendbar werden, weil StaffelPilot sich an einem Bindestrich
        stoert.
        """
        return bool(AKTENZEICHEN_MUSTER.match(self.aktenzeichen.strip()))


def _einzeilig(wert: str) -> str:
    """Eine Zeile, was immer eingegeben wurde. Ein Betreff haelt keinen
    Umbruch."""
    return " ".join((wert or "").split())


def betreff(fall: Fall) -> str:
    """`[Aktenzeichen], Verein, Angeklagter` -- die Klammern gehoeren dazu.

    So sortiert der Sportrichter seine Eingaenge; es ist kein Schmuck.
    """
    return (
        f"[{_einzeilig(fall.aktenzeichen)}], "
        f"{_einzeilig(fall.verein)}, {_einzeilig(fall.angeklagter)}"
    )


def _kerndaten(fall: Fall) -> list[str]:
    zeilen = [
        f"Aktenzeichen: {fall.aktenzeichen.strip()}",
        f"Verein: {fall.verein.strip()}",
        f"Spieler: {fall.angeklagter.strip()}",
        f"Grund: {fall.grund.strip()}",
    ]
    # Eine leere Anlagenzeile liest sich wie "ich habe es vergessen" -- also
    # faellt sie weg.
    if fall.anlagen.strip():
        zeilen.append(f"Anlagen: {fall.anlagen.strip()}")
    return zeilen


def text(fall: Fall) -> str:
    """Der Text der Mail. Er endet nach dem Hinweis -- ohne Gruss, so
    entschieden."""
    absaetze = [
        ANREDE,
        (
            f"ich habe heute den Sportgerichtsfall des Spielers "
            f"{fall.angeklagter.strip()} aufgrund des folgenden Sachverhalts "
            "angelegt und bitte um Bearbeitung."
        ),
        "Die Kerndaten:\n" + "\n".join(_kerndaten(fall)),
    ]
    if fall.hinweis.strip():
        absaetze.append(f"Hinweis: {fall.hinweis.strip()}")
    return "\n\n".join(absaetze) + "\n"
