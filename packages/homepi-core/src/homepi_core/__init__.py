"""Grundgerüst für HomePI-Microservices."""

from .cache import Cache, CacheNichtVerfuegbar
from .db import Database
from .errors import ServiceError
from .health import HealthRegistry, HealthReport, Status, evaluate
from .logging import configure_logging, request_id_var
from .service import ServiceContext, create_service
from .settings import LogFormat, ServiceSettings, Umgebung, get_settings

__version__ = "0.1.0"

__all__ = [
    "Cache",
    "CacheNichtVerfuegbar",
    "Database",
    "HealthRegistry",
    "HealthReport",
    "LogFormat",
    "ServiceContext",
    "ServiceError",
    "ServiceSettings",
    "Status",
    "Umgebung",
    "__version__",
    "configure_logging",
    "create_service",
    "evaluate",
    "get_settings",
    "request_id_var",
]
