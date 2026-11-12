"""HomePI-Artefakt: Tischtennisturnier."""

from homepi_core import Modul, Zugang

from .router import router

__version__ = "0.1.0"

#: Der Entry Point in pyproject.toml zeigt hierauf. Mehr braucht das Gateway
#: nicht, um das Artefakt unter /tischtennis einzuhaengen und auf der
#: Startseite als Kachel anzuzeigen.
modul = Modul(
    id="tischtennis",
    titel="Tischtennisturnier",
    router=router,
    beschreibung="Spielplan auswuerfeln, Ergebnisse erfassen, Dashboard fuer alle",
    icon="kachel",
    version=__version__,
    # OEFFENTLICH und damit die Ausnahme in diesem Haus: die Dashboard-
    # Ansicht soll jeder Kollege ohne Konto sehen koennen, ueber die Kachel
    # und nicht nur ueber einen weitergegebenen Link. Dass die Kachel damit
    # auch unangemeldet erscheint, ist gewollt.
    #
    # Der Preis steht in docs/11-anmeldung.md: die Pruefung haengt nicht mehr
    # am Router. Jeder schreibende Endpunkt traegt sein eigenes `erfordert`,
    # und ein Test in tests/unit/test_anmeldung.py geht alle Routen durch und
    # verlangt das - sonst waere der vergessene Endpunkt der, der das Loch
    # reisst. Rechte vergeben: homepi benutzer recht <name> tischtennis nutzer
    zugang=Zugang.OEFFENTLICH,
)

__all__ = ["__version__", "modul", "router"]
