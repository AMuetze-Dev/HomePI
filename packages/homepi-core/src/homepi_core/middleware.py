"""Anfrage-Kennung und Zugriffslog."""

from __future__ import annotations

import logging
import time
import uuid
from collections.abc import Awaitable, Callable

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from .logging import request_id_var

log = logging.getLogger("homepi.zugriff")

HEADER = "X-Request-ID"

Weiter = Callable[[Request], Awaitable[Response]]


class RequestIdMiddleware(BaseHTTPMiddleware):
    """Übernimmt eine vorhandene Kennung oder vergibt eine neue.

    Traefik reicht den Header durch, wenn er gesetzt ist. Damit lässt sich ein
    Aufruf über mehrere Services hinweg verfolgen, ohne dass dafür ein
    Tracing-System nötig wäre.
    """

    async def dispatch(self, request: Request, call_next: Weiter) -> Response:
        rid = request.headers.get(HEADER) or uuid.uuid4().hex
        token = request_id_var.set(rid)
        try:
            antwort = await call_next(request)
        finally:
            request_id_var.reset(token)
        antwort.headers[HEADER] = rid
        return antwort


class AccessLogMiddleware(BaseHTTPMiddleware):
    """Eine Zeile pro Anfrage, mit Dauer.

    Healthchecks werden übersprungen: alle 30 Sekunden pro Service eine Zeile
    ergibt am Tag mehrere Tausend Einträge, die nichts aussagen und nur die
    Logrotation füttern.
    """

    STILLE_PFADE = frozenset({"/health", "/ready", "/metrics"})

    async def dispatch(self, request: Request, call_next: Weiter) -> Response:
        if request.url.path in self.STILLE_PFADE:
            return await call_next(request)

        start = time.perf_counter()
        antwort = await call_next(request)
        dauer_ms = (time.perf_counter() - start) * 1000

        log.info(
            "%s %s -> %d (%.1f ms)",
            request.method,
            request.url.path,
            antwort.status_code,
            dauer_ms,
            extra={
                "methode": request.method,
                "pfad": request.url.path,
                "status": antwort.status_code,
                "dauer_ms": round(dauer_ms, 1),
            },
        )
        return antwort


class KeinZwischenspeicherMiddleware(BaseHTTPMiddleware):
    """``Cache-Control: no-store`` auf jede Antwort.

    Dieser Dienst liefert ausschliesslich Daten, die sich aendern - Konten,
    Rechte, Geraete. Ohne diesen Header entscheidet der Browser selbst, ob er
    eine Antwort wiederverwendet, und tut das bei einer unveraenderten Adresse
    gelegentlich auch. Das Ergebnis ist eine Oberflaeche, die eine Aenderung
    nicht zeigt, obwohl sie gespeichert ist - ein Fehler, den man an der
    falschen Stelle sucht.

    Ausgeliefert werden hier keine statischen Dateien; das uebernimmt das
    Frontend. Ein pauschales no-store kostet hier also nichts.
    """

    async def dispatch(self, request: Request, call_next: Weiter) -> Response:
        antwort = await call_next(request)
        antwort.headers.setdefault("Cache-Control", "no-store")
        return antwort
