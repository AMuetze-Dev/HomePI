"""HomePI-Artefakt: Benutzer und Rechte verwalten."""

from homepi_core import Modul, Zugang
from homepi_core.auth import VERWALTUNG, Rolle

from .router import router

__version__ = "0.1.0"

#: Der Entry Point in pyproject.toml zeigt hierauf.
#:
#: Die Kennung ist nicht frei gewaehlt: ``homepi_core.auth.VERWALTUNG`` ist
#: dieselbe Zeichenkette, und an ihr haengt die Frage "gibt es hier schon einen
#: Verwalter?". Wer sie hier aendert, muss sie dort aendern - deshalb steht sie
#: nur an einer Stelle.
modul = Modul(
    id=VERWALTUNG,
    titel="Verwaltung",
    router=router,
    beschreibung="Konten, Rollen und wer was darf",
    icon="schluessel",
    version=__version__,
    # Das strengste Artefakt der Installation: wer es darf, vergibt Rechte -
    # auch sich selbst. Deshalb VERWALTER und nicht LESER.
    zugang=Zugang.GESCHUETZT,
    mindestrolle=Rolle.VERWALTER,
)

__all__ = ["__version__", "modul", "router"]
