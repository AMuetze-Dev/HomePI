"""HomePI-Artefakt: Haushaltsbuch."""

from homepi_core import Modul, Zugang

from .router import router

__version__ = "0.1.0"

#: Der Entry Point in pyproject.toml zeigt hierauf. Mehr braucht das Gateway
#: nicht, um das Artefakt unter /haushaltsbuch einzuhaengen und auf der
#: Startseite als Kachel anzuzeigen.
modul = Modul(
    id="haushaltsbuch",
    titel="Haushaltsbuch",
    router=router,
    beschreibung="Konten, Fixkosten und Rücklagen",
    icon="sparschwein",
    version=__version__,
    # Wer darf das sehen und benutzen?
    #   Zugang.GESCHUETZT  - nur mit Recht "haushaltsbuch" (Voreinstellung)
    #   Zugang.OEFFENTLICH - ohne Anmeldung, fuer jeden sichtbar
    #   Zugang.SELBST      - das Artefakt prueft Endpunkt fuer Endpunkt
    # Rechte vergeben: homepi benutzer recht <name> haushaltsbuch <rolle>
    zugang=Zugang.GESCHUETZT,
)

__all__ = ["__version__", "modul", "router"]
