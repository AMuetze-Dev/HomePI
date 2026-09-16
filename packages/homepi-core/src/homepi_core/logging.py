"""Einheitliches Logging über alle Services.

In Produktion JSON-Zeilen, damit Dozzle und spätere Auswertungen damit
umgehen können; in der Entwicklung lesbarer Text. Es kommt bewusst keine
Logging-Bibliothek dazu - das Standardmodul reicht, und jeder zusätzliche
Prozess auf dem Pi kostet Speicher.
"""

from __future__ import annotations

import contextvars
import json
import logging
import sys
from datetime import UTC, datetime
from typing import Any

from .settings import LogFormat

#: Die Anfrage-Kennung wird von der Middleware gesetzt und landet automatisch
#: in jeder Logzeile, die währenddessen entsteht - ohne sie durchreichen zu
#: müssen. Genau dafür gibt es ContextVar.
request_id_var: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "request_id", default=None
)

_STANDARD_FELDER = frozenset(logging.LogRecord("", 0, "", 0, "", None, None).__dict__) | {
    "message",
    "asctime",
    "taskName",
}


class JsonFormatter(logging.Formatter):
    def __init__(self, service: str, version: str) -> None:
        super().__init__()
        self._service = service
        self._version = version

    def format(self, record: logging.LogRecord) -> str:
        eintrag: dict[str, Any] = {
            "zeit": datetime.fromtimestamp(record.created, UTC).isoformat(),
            "level": record.levelname.lower(),
            "service": self._service,
            "version": self._version,
            "logger": record.name,
            "nachricht": record.getMessage(),
        }

        if (rid := request_id_var.get()) is not None:
            eintrag["request_id"] = rid

        if record.exc_info:
            eintrag["fehler"] = self.formatException(record.exc_info)

        # Alles, was per logger.info("...", extra={...}) mitgegeben wurde
        for schluessel, wert in record.__dict__.items():
            if schluessel not in _STANDARD_FELDER and not schluessel.startswith("_"):
                eintrag[schluessel] = wert

        return json.dumps(eintrag, ensure_ascii=False, default=str)


class TextFormatter(logging.Formatter):
    def __init__(self) -> None:
        super().__init__(
            fmt="%(asctime)s %(levelname)-7s %(name)s: %(message)s",
            datefmt="%H:%M:%S",
        )

    def format(self, record: logging.LogRecord) -> str:
        zeile = super().format(record)
        if (rid := request_id_var.get()) is not None:
            zeile = f"{zeile}  [{rid[:8]}]"
        return zeile


def configure_logging(
    *,
    service: str,
    version: str,
    level: str = "info",
    format_: LogFormat = LogFormat.TEXT,
) -> None:
    """Richtet das Root-Logging ein. Mehrfacher Aufruf ist unschädlich."""
    formatter: logging.Formatter = (
        JsonFormatter(service, version) if format_ is LogFormat.JSON else TextFormatter()
    )

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(formatter)

    root = logging.getLogger()
    # Vorhandene Handler ersetzen, sonst erscheint nach einem zweiten Aufruf
    # jede Zeile doppelt.
    for alt in list(root.handlers):
        root.removeHandler(alt)
    root.addHandler(handler)
    root.setLevel(level.upper())

    # uvicorn bringt eigene Handler mit und würde sonst in einem anderen
    # Format schreiben als der Rest des Service.
    for name in ("uvicorn", "uvicorn.error", "uvicorn.access"):
        logger = logging.getLogger(name)
        logger.handlers.clear()
        logger.propagate = True

    # SQLAlchemy loggt auf INFO jede einzelne Anweisung. Das ist beim
    # Debuggen nützlich und im Betrieb nur Lärm.
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
