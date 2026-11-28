"""HomePI-Artefakt: Quiz."""

from homepi_core import Modul, Zugang

from .router import router

__version__ = "0.1.0"

#: Der Entry Point in pyproject.toml zeigt hierauf. Mehr braucht das Gateway
#: nicht, um das Artefakt unter /quiz einzuhaengen und auf der
#: Startseite als Kachel anzuzeigen.
modul = Modul(
    id="quiz",
    titel="Quiz",
    router=router,
    beschreibung="Quizrunden leiten, mitspielen ohne Konto, Anzeigetafel fuer alle",
    icon="kachel",
    version=__version__,
    # OEFFENTLICH wie das Tischtennisturnier: Mitspieler brauchen kein Konto
    # und finden das Quiz ueber die Kachel. Geleitet wird nur mit Konto.
    #
    # Der Preis steht in docs/11-anmeldung.md: die Pruefung haengt nicht am
    # Router. Jeder Endpunkt der Leitung traegt sein eigenes `erfordert`, und
    # tests/unit/test_anmeldung.py kennt die offenen Endpunkte namentlich.
    # Rechte vergeben: homepi benutzer recht <name> quiz nutzer
    zugang=Zugang.OEFFENTLICH,
)

__all__ = ["__version__", "modul", "router"]
