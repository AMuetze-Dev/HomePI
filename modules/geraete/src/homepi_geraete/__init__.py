"""HomePI-Artefakt: Geräte im Haus."""

from homepi_core import Modul, Zugang

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
    # Die Geraete im Haus sind niemandes Sache ausser der eigenen. Wer kein
    # Recht "geraete" hat, sieht das Artefakt nicht einmal im Manifest.
    zugang=Zugang.GESCHUETZT,
)

__all__ = ["__version__", "modul", "router"]
