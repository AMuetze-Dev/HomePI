"""StaffelPilot versendet keine Mail. Nie.

Eine Nachricht an einen Sportrichter eröffnet ein Verfahren gegen eine
benannte Person, eine Mahnung geht an einen Verein. Beides wird hier
vorbereitet und von einem Menschen abgeschickt, nachdem er es gelesen hat. Das
ist eine stehende Entscheidung und keine Voreinstellung.

Bis zum 30.08.2026 war es in der alten Anwendung nur eine Entscheidung:
`postfach.auto_send` war ein Schalter in den Einstellungen, und wer ihn
umlegte, ließ das Programm im DFBnet-Postfach auf „Senden" klicken. Diese
Datei macht aus der Entscheidung eine Eigenschaft — sie scheitert, sobald ein
Versandweg zurückkommt, von wem auch immer und mit welcher Begründung.

**Warum sie über das eigene Paket hinausreicht.** Der Versand wäre hier nicht
zu bauen: dieses Artefakt hat keinen Browser. Gefährlich ist der Prüfdienst,
der mit einer angemeldeten DFBnet-Sitzung vor dem Verbandspostfach steht.
Geprüft wird deshalb das ganze Haus und nicht nur dieses Zimmer.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

#: Die Wurzel des Mehrfachpakets: modules/staffelpilot/tests/unit -> HomePI.
WURZEL = Path(__file__).resolve().parents[4]

#: Was nicht uns gehoert. Fremder Code darf Mail versenden koennen; er tut es
#: in dieser Anwendung nur nicht.
FREMD = (".venv", "node_modules", "dist", "build", "__pycache__", ".git", "test-results")

#: Bibliotheken, mit denen sich eine Mail abschicken liesse. Der Import allein
#: ist der Befund -- ohne ihn geht es nicht, mit ihm ist es eine Zeile.
MAILBIBLIOTHEKEN = {
    "smtplib",
    "aiosmtplib",
    "yagmail",
    "sendgrid",
    "mailjet",
    "postmarker",
    "mailersend",
    "redmail",
}

#: Namen, die nur eines bedeuten koennen.
VERSANDNAMEN = {
    "send",
    "senden",
    "send_mail",
    "sendmail",
    "mail_senden",
    "versenden",
    "mail_versenden",
    "nachricht_senden",
}

#: Woerter, die in einem Selektor oder einem zugaenglichen Namen stehen, wenn
#: jemand im Verbandspostfach auf Senden klickt. Geprueft werden **nur
#: Zeichenketten**, nicht Bezeichner: `SUCHE_ABSENDEN = "input[name='SEARCH']"`
#: schickt eine Suche ab und keine Mail, und die Zeichenkette sagt das.
POSTFACHWOERTER = ("postfach", "nachricht senden", "mail senden", "mailto:")

#: Schalter, die den Versand einmal automatisch gemacht haben.
VERBOTENE_SCHALTER = ("auto_send", "autoSend", "autosend", "autoversand", "auto_versand")


#: Diese Datei selbst. Sie nennt jedes verbotene Wort und waere sonst der
#: erste Treffer jeder Suche -- eine Wache, die sich selbst verhaftet.
SELBST = Path(__file__).resolve()


def _eigene(endungen: tuple[str, ...]) -> list[Path]:
    return sorted(
        p
        for e in endungen
        for p in WURZEL.rglob(f"*{e}")
        if not any(teil in FREMD for teil in p.parts) and p.resolve() != SELBST
    )


def _docstrings(baum: ast.AST) -> set[int]:
    """Welche Zeichenketten Prosa sind und kein Selektor.

    "Er laeuft ueber das Verbandspostfach" ist eine Erklaerung und kein Weg
    dorthin. Eine Wache, die Erklaerungen verbietet, bekommt Code ohne
    Erklaerungen -- das waere der schlechteste Tausch von allen.
    """
    zeilen: set[int] = set()
    for knoten in ast.walk(baum):
        if not isinstance(
            knoten, ast.Module | ast.ClassDef | ast.FunctionDef | ast.AsyncFunctionDef
        ):
            continue
        erste = next(iter(getattr(knoten, "body", [])), None)
        if (
            isinstance(erste, ast.Expr)
            and isinstance(erste.value, ast.Constant)
            and isinstance(erste.value.value, str)
        ):
            zeilen.update(range(erste.lineno, (erste.end_lineno or erste.lineno) + 1))
    return zeilen


PYTHON = _eigene((".py",))
OBERFLAECHE = _eigene((".ts", ".tsx", ".js"))


def test_es_gibt_eigene_quellen_zu_pruefen() -> None:
    """Die Wache selbst bewachen.

    Ein falscher Pfad liesse jede Zusicherung unten gruen werden, ohne eine
    Zeile angesehen zu haben -- das waere die gefaehrlichste Art, gruen zu
    sein.
    """
    assert len(PYTHON) > 50, f"Nur {len(PYTHON)} Python-Dateien unter {WURZEL} gefunden"
    assert len(OBERFLAECHE) > 20, f"Nur {len(OBERFLAECHE)} Oberflaechendateien gefunden"
    assert any("homepi_pruefdienst" in str(p) for p in PYTHON), "Der Pruefdienst fehlt"


def test_keine_mailbibliothek_wird_importiert() -> None:
    treffer: list[str] = []
    for datei in PYTHON:
        baum = ast.parse(datei.read_text(encoding="utf-8"), filename=str(datei))
        for knoten in ast.walk(baum):
            namen: list[str] = []
            if isinstance(knoten, ast.Import):
                namen = [a.name for a in knoten.names]
            elif isinstance(knoten, ast.ImportFrom):
                namen = [knoten.module or ""]
            for name in namen:
                if name.split(".")[0] in MAILBIBLIOTHEKEN:
                    treffer.append(f"{datei.relative_to(WURZEL)}: {name}")
    assert treffer == [], "Ein Versandweg ist zurueck: " + ", ".join(treffer)


def test_keine_funktion_heisst_wie_ein_versand() -> None:
    """Faengt einen Weg, dessen Selektoren diese Datei nicht kennt."""
    verdaechtig: list[str] = []
    for datei in PYTHON:
        baum = ast.parse(datei.read_text(encoding="utf-8"), filename=str(datei))
        for knoten in ast.walk(baum):
            if (
                isinstance(knoten, ast.FunctionDef | ast.AsyncFunctionDef)
                and knoten.name.lower() in VERSANDNAMEN
            ):
                verdaechtig.append(f"{datei.relative_to(WURZEL)}:{knoten.name}")
    assert verdaechtig == [], ", ".join(verdaechtig)


def test_kein_selektor_zeigt_auf_ein_postfach() -> None:
    """Nur Zeichenketten, keine Bezeichner.

    Der Pruefdienst steht mit einer angemeldeten Sitzung vor DFBnet. Ein
    Selektor, der das Postfach meint, ist der erste Schritt zu einem Klick auf
    Senden -- und der zweite waere eine Zeile.
    """
    treffer: list[str] = []
    for datei in PYTHON:
        baum = ast.parse(datei.read_text(encoding="utf-8"), filename=str(datei))
        prosa = _docstrings(baum)
        for knoten in ast.walk(baum):
            if isinstance(knoten, ast.Constant) and isinstance(knoten.value, str):
                if knoten.lineno in prosa:
                    continue
                klein = knoten.value.lower()
                for wort in POSTFACHWOERTER:
                    if wort in klein:
                        treffer.append(f"{datei.relative_to(WURZEL)}:{knoten.lineno}: {wort}")
    assert treffer == [], ", ".join(treffer)


@pytest.mark.parametrize("schalter", VERBOTENE_SCHALTER)
def test_kein_schalter_kann_versand_einschalten(schalter: str) -> None:
    treffer = [
        str(datei.relative_to(WURZEL))
        for datei in [*PYTHON, *OBERFLAECHE]
        if schalter in datei.read_text(encoding="utf-8")
    ]
    assert treffer == [], f"{schalter!r} lebt wieder in: {', '.join(treffer)}"


def test_die_einstellungen_kennen_keinen_versand() -> None:
    """Die Liste der setzbaren Felder ist der einzige Weg in die Einstellungen.

    Steht dort nichts von Versand, kann ihn auch niemand ueber die Oberflaeche
    einschalten -- unabhaengig davon, was eine Ansicht anzeigt.
    """
    from homepi_staffelpilot.schemas import EinstellungenSetzen

    # Genau und nicht ungefaehr: "absender" ist die Adresse, die in einem
    # Entwurf als Absender vorgeschlagen wird. Sie verschickt nichts, und eine
    # Wache, die sie verbietet, treibt nur dazu, sie umzubenennen.
    verdaechtig = [
        feld
        for feld in EinstellungenSetzen.model_fields
        if feld.lower() in VERBOTENE_SCHALTER
        or feld.lower().startswith(("senden", "versand", "versenden", "mailversand"))
    ]
    assert verdaechtig == [], ", ".join(verdaechtig)


def test_der_mailentwurf_traegt_keinen_weg_nach_draussen() -> None:
    """Was die Oberflaeche bekommt, ist Text und ein Verweis auf den Anhang.

    Kein Feld, das nach einem Versand aussieht: wer eines einfuehrt, muss
    diesen Test aendern -- und das ist der Punkt.
    """
    from homepi_staffelpilot.schemas import MailEntwurf

    assert set(MailEntwurf.model_fields) == {
        "empfaenger",
        "betreff",
        "text",
        "anhang",
        "fehlende_felder",
    }
