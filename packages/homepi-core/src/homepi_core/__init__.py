"""Grundgerüst für HomePI-Microservices.

Die Namen werden **lazy** nachgeladen (PEP 562). Ein ``import homepi_core``
zieht damit nicht FastAPI, SQLAlchemy und Pydantic mit, sondern erst der
Zugriff auf den jeweiligen Namen.

Das hat zwei praktische Gründe:

- ``homepi deploy`` kommt mit der Standardbibliothek aus und startet sofort,
  statt auf Importe zu warten, die es nicht braucht.
- Das pytest-Plugin wird über einen Entry Point geladen, also *bevor*
  pytest-cov aktiv ist. Ohne Lazy-Import zählte coverage das Modul-Level
  jedes Untermoduls als ungetestet und meldete für ein Paket mit über
  hundert grünen Tests 62 %.
"""

from typing import TYPE_CHECKING, Any

__version__ = "0.1.0"

if TYPE_CHECKING:
    from .cache import Cache, CacheNichtVerfuegbar
    from .db import Database
    from .errors import ServiceError
    from .health import HealthRegistry, HealthReport, Status, evaluate
    from .logging import configure_logging, request_id_var
    from .modelle import Base, ZeitstempelMixin
    from .modules import (
        DefektesModul,
        Modul,
        Modulregister,
        Zugang,
        entdecke_module,
        gewuenschte_module,
        register_aus,
    )
    from .service import ServiceContext, create_service
    from .settings import LogFormat, ServiceSettings, Umgebung, get_settings

#: Name -> Untermodul. Eine Zeile je Export, damit ein Tippfehler beim
#: Hinzufügen sofort auffällt statt erst beim ersten Zugriff.
_HERKUNFT: dict[str, str] = {
    "Base": "modelle",
    "Cache": "cache",
    "CacheNichtVerfuegbar": "cache",
    "Database": "db",
    "DefektesModul": "modules",
    "HealthRegistry": "health",
    "HealthReport": "health",
    "LogFormat": "settings",
    "Modul": "modules",
    "Modulregister": "modules",
    "ServiceContext": "service",
    "ServiceError": "errors",
    "ServiceSettings": "settings",
    "Status": "health",
    "Umgebung": "settings",
    "ZeitstempelMixin": "modelle",
    "Zugang": "modules",
    "configure_logging": "logging",
    "create_service": "service",
    "entdecke_module": "modules",
    "gewuenschte_module": "modules",
    "evaluate": "health",
    "get_settings": "settings",
    "register_aus": "modules",
    "request_id_var": "logging",
}

__all__ = [
    "Base",
    "Cache",
    "CacheNichtVerfuegbar",
    "Database",
    "DefektesModul",
    "HealthRegistry",
    "HealthReport",
    "LogFormat",
    "Modul",
    "Modulregister",
    "ServiceContext",
    "ServiceError",
    "ServiceSettings",
    "Status",
    "Umgebung",
    "ZeitstempelMixin",
    "Zugang",
    "__version__",
    "configure_logging",
    "create_service",
    "entdecke_module",
    "evaluate",
    "get_settings",
    "gewuenschte_module",
    "register_aus",
    "request_id_var",
]


def __getattr__(name: str) -> Any:
    modul = _HERKUNFT.get(name)
    if modul is None:
        raise AttributeError(f"module 'homepi_core' has no attribute '{name}'")

    from importlib import import_module

    wert = getattr(import_module(f".{modul}", __name__), name)
    # Zwischenspeichern: der zweite Zugriff geht direkt ins Modul-Dict.
    globals()[name] = wert
    return wert


def __dir__() -> list[str]:
    return list(__all__)
