"""HomePI-Artefakt: Spielberichte pruefen.

Der Kern der Arbeit eines Staffelleiters: geprüfte Spielberichte kommen herein,
ihre Befunde werden entschieden, und erst dann gilt ein Bericht als erledigt.

Was hier **nicht** liegt und bewusst spaeter kommt: die DFBnet-Automation. Sie
faehrt minutenlang einen Browser und gehoert nach docs/06-artefakte.md in einen
eigenen Dienst. Die Naht dafuer ist `POST /staffelpilot/import`.
"""

from homepi_core import Modul

from .router import router

__version__ = "0.1.0"

#: Der Entry Point in pyproject.toml zeigt hierauf. Mehr braucht das Gateway
#: nicht, um das Artefakt unter /staffelpilot einzuhaengen und auf der
#: Startseite als Kachel anzuzeigen.
modul = Modul(
    id="staffelpilot",
    titel="StaffelPilot",
    router=router,
    beschreibung="Spielberichte prüfen und abhaken",
    icon="pfeife",
    version=__version__,
)

__all__ = ["__version__", "modul", "router"]
