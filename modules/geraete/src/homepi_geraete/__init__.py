"""HomePI-Artefakt: Geräte im Haus."""

from homepi_core import Modul

from .router import router

__version__ = "0.1.0"

#: Der Entry Point in pyproject.toml zeigt hierauf. Mehr braucht das Gateway
#: nicht, um das Artefakt unter /geraete einzuhaengen und auf der Startseite
#: als Kachel anzuzeigen.
modul = Modul(
    id="geraete",
    titel="Geräte",
    router=router,
    beschreibung="Was im Haus an- und ausgeht",
    icon="steckdose",
    version=__version__,
)

__all__ = ["__version__", "modul", "router"]
