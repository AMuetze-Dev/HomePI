"""HomePI-Artefakt: Kinderzimmer."""

from homepi_core import Modul, Zugang

from .router import router

__version__ = "0.1.0"

#: Der Entry Point in pyproject.toml zeigt hierauf. Mehr braucht das Gateway
#: nicht, um das Artefakt unter /kinderzimmer einzuhaengen und auf der
#: Startseite als Kachel anzuzeigen.
modul = Modul(
    id="kinderzimmer",
    titel="Kinderzimmer",
    router=router,
    beschreibung="Spiele für die Kleinste: Figuren, Klänge, Stimmen",
    icon="kinderzimmer",
    version=__version__,
    # SELBST, weil das Geraet kein Benutzerkonto hat: /geraet/... prueft ein
    # Token, alles andere die Rechte der Eltern. Beide Pruefungen haengen an
    # je einem Router (router.py), und tests/unit/test_anmeldung.py verlangt
    # eine davon an jeder Route.
    zugang=Zugang.SELBST,
)

__all__ = ["__version__", "modul", "router"]
