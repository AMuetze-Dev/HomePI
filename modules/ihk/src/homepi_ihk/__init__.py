"""HomePI-Artefakt: Prüfung."""

from homepi_core import Modul, Zugang

from .router import router

__version__ = "0.1.0"

#: Der Entry Point in pyproject.toml zeigt hierauf. Mehr braucht das Gateway
#: nicht, um das Artefakt unter /ihk einzuhaengen und auf der
#: Startseite als Kachel anzuzeigen.
modul = Modul(
    id="ihk",
    titel="Prüfung",
    router=router,
    beschreibung="IHK-Abschlussprüfungen FIAE bewerten",
    icon="kachel",
    version=__version__,
    # Wer darf das sehen und benutzen?
    #   Zugang.GESCHUETZT  - nur mit Recht "ihk" (Voreinstellung)
    #   Zugang.OEFFENTLICH - ohne Anmeldung, fuer jeden sichtbar
    #   Zugang.SELBST      - das Artefakt prueft Endpunkt fuer Endpunkt
    # Rechte vergeben: homepi benutzer recht <name> ihk <rolle>
    zugang=Zugang.GESCHUETZT,
)

__all__ = ["__version__", "modul", "router"]
