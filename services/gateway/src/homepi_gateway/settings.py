from homepi_core import ServiceSettings

from . import __version__


class Settings(ServiceSettings):
    """Einstellungen des Gateways.

    Alles Allgemeine - DATABASE_URL, REDIS_URL, LOG_LEVEL, CORS_ORIGINS,
    PORT, WEB_CONCURRENCY - kommt aus ServiceSettings.
    """

    service_name: str = "gateway"
    service_version: str = __version__

    #: Legt beim Start fehlende Tabellen an.
    #:
    #: Das ist ein Startwerkzeug, kein Migrationssystem: es erzeugt fehlende
    #: Tabellen, aendert aber keine vorhandenen. Sobald sich ein Schema zum
    #: ersten Mal aendert, gehoert hier Alembic hin. Bis dahin spart es in der
    #: Entwicklung den Schritt, die Tabellen von Hand anzulegen.
    db_schema_anlegen: bool = True
