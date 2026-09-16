"""Einheitliches Fehlerformat nach RFC 9457 (problem+json).

Der Grund für ein gemeinsames Format: das Frontend soll einen Fehler von
*jedem* Service gleich behandeln können. Ohne das schreibt man pro Service
eine eigene Fehlerbehandlung - und vergisst sie beim vierten.

    {
      "type":     "about:blank",
      "title":    "Nicht gefunden",
      "status":   404,
      "detail":   "Gerät 42 existiert nicht",
      "instance": "/geraete/42",
      "request_id": "0b1f..."
    }
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from .logging import request_id_var

log = logging.getLogger(__name__)

PROBLEM_JSON = "application/problem+json"


class ServiceError(Exception):
    """Basis für fachliche Fehler. Services leiten davon ab:

    class GeraetUnbekannt(ServiceError):
        status = 404
        title = "Gerät unbekannt"
    """

    status: int = 500
    title: str = "Interner Fehler"
    type_: str = "about:blank"

    def __init__(self, detail: str | None = None, **zusatz: Any) -> None:
        super().__init__(detail or self.title)
        self.detail = detail
        self.zusatz = zusatz


def _problem(
    status: int,
    title: str,
    *,
    detail: str | None = None,
    instance: str | None = None,
    type_: str = "about:blank",
    **zusatz: Any,
) -> JSONResponse:
    koerper: dict[str, Any] = {"type": type_, "title": title, "status": status}
    if detail:
        koerper["detail"] = detail
    if instance:
        koerper["instance"] = instance
    if (rid := request_id_var.get()) is not None:
        koerper["request_id"] = rid
    koerper.update(zusatz)
    return JSONResponse(koerper, status_code=status, media_type=PROBLEM_JSON)


def install_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(ServiceError)
    async def _service_error(request: Request, exc: ServiceError) -> JSONResponse:
        return _problem(
            exc.status,
            exc.title,
            detail=exc.detail,
            instance=request.url.path,
            type_=exc.type_,
            **exc.zusatz,
        )

    @app.exception_handler(HTTPException)
    async def _http_error(request: Request, exc: HTTPException) -> JSONResponse:
        return _problem(
            exc.status_code,
            exc.detail if isinstance(exc.detail, str) else "Fehler",
            instance=request.url.path,
        )

    @app.exception_handler(RequestValidationError)
    async def _validierung(request: Request, exc: RequestValidationError) -> JSONResponse:
        return _problem(
            422,
            "Ungültige Anfrage",
            detail="Die Anfrage entspricht nicht dem erwarteten Schema",
            instance=request.url.path,
            fehler=[
                {"feld": ".".join(str(t) for t in f["loc"]), "problem": f["msg"]}
                for f in exc.errors()
            ],
        )

    @app.exception_handler(Exception)
    async def _unerwartet(request: Request, exc: Exception) -> JSONResponse:
        # Der Stacktrace gehört ins Log, nicht in die Antwort: er verrät
        # Dateipfade und Bibliotheksversionen.
        log.exception("Unbehandelter Fehler bei %s %s", request.method, request.url.path)
        return _problem(
            500,
            "Interner Fehler",
            detail="Die Anfrage konnte nicht verarbeitet werden",
            instance=request.url.path,
        )
