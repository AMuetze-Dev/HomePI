"""Die Fabrik, die aus Einstellungen einen fertigen Service macht.

    from homepi_core import ServiceSettings, create_service

    class Settings(ServiceSettings):
        service_name: str = "geraete"

    settings = Settings()
    app = create_service(settings)

    @app.get("/geraete")
    async def liste() -> list[str]:
        ...

Was der Aufruf mitbringt: Logging, ``/health`` und ``/info``, CORS,
Anfrage-Kennung, Zugriffslog, einheitliches Fehlerformat, sauberes Schließen
von Datenbank und Cache beim Herunterfahren.
"""

from __future__ import annotations

import contextlib
import logging
from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager
from dataclasses import dataclass
from typing import Any

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from .cache import Cache
from .db import Database
from .errors import install_error_handlers
from .health import HealthRegistry
from .logging import configure_logging
from .middleware import AccessLogMiddleware, RequestIdMiddleware
from .modules import Modul, Modulregister, Zugang
from .settings import ServiceSettings

log = logging.getLogger(__name__)

MANIFEST_BESCHREIBUNG = (
    "Die Startseite baut ihre Kacheln aus genau dieser Liste. Ein neues Artefakt "
    "erscheint dort, sobald das Gateway es geladen hat - ohne Änderung am "
    "Frontend. Defekte Module stehen mit status='fehler' drin, damit sie nicht "
    "stillschweigend fehlen."
)


@dataclass
class ServiceContext:
    """Was der Service zur Laufzeit zur Verfügung hat.

    Liegt unter ``app.state.homepi``, damit Endpunkte per Dependency
    darankommen, ohne globale Variablen anzulegen.
    """

    settings: ServiceSettings
    health: HealthRegistry
    db: Database | None = None
    cache: Cache | None = None
    module: Modulregister | None = None

    def require_db(self) -> Database:
        if self.db is None:
            raise RuntimeError("Dieser Service hat keine DATABASE_URL konfiguriert")
        return self.db

    def require_cache(self) -> Cache:
        if self.cache is None:
            raise RuntimeError("Dieser Service hat keine REDIS_URL konfiguriert")
        return self.cache


def create_service(
    settings: ServiceSettings,
    *,
    module: Modulregister | None = None,
    anmeldung: bool = False,
    on_startup: Callable[[ServiceContext], AsyncIterator[None]] | None = None,
    **fastapi_kwargs: object,
) -> FastAPI:
    configure_logging(
        service=settings.service_name,
        version=settings.service_version,
        level=settings.log_level,
        format_=settings.effektives_log_format,
    )

    kontext = ServiceContext(settings=settings, health=HealthRegistry(), module=module)

    if settings.database_url:
        kontext.db = Database(settings.database_url)
        kontext.health.register("database", kontext.db.ping, essential=True)

    if anmeldung and kontext.db is None:
        # Frueh und deutlich: Benutzer und Sitzungen liegen in der Datenbank,
        # ohne sie kaeme der Fehler erst beim ersten Anmeldeversuch.
        raise RuntimeError(
            "anmeldung=True braucht eine DATABASE_URL - Benutzer und "
            "Sitzungen liegen in der Datenbank."
        )

    if settings.redis_url:
        kontext.cache = Cache(settings.redis_url)
        # Ein Cache ist selten essenziell: ohne ihn wird der Service langsamer,
        # nicht unbrauchbar. Deshalb "degraded" statt "down".
        kontext.health.register("cache", kontext.cache.ping, essential=False)

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        log.info(
            "%s %s startet (%s)",
            settings.service_name,
            settings.service_version,
            settings.environment.value,
        )
        if on_startup is not None:
            async with _als_kontext(on_startup, kontext):
                yield
        else:
            yield
        log.info("%s fährt herunter", settings.service_name)
        if kontext.db is not None:
            await kontext.db.dispose()
        if kontext.cache is not None:
            await kontext.cache.dispose()

    if anmeldung and settings.ist_produktion and "openapi_url" not in fastapi_kwargs:
        # Das OpenAPI-Schema listet jeden Pfad jedes Artefakts, auch die, die
        # der Aufrufer nicht sehen darf. Auf einem Dienst mit Anmeldung ist das
        # ein Verzeichnis der internen Artefakte - in Produktion zu.
        fastapi_kwargs["openapi_url"] = None

    app = FastAPI(
        title=settings.service_name,
        version=settings.service_version,
        root_path=settings.root_path,
        lifespan=lifespan,
        **fastapi_kwargs,  # type: ignore[arg-type]
    )
    app.state.homepi = kontext

    # Reihenfolge ist wichtig: die Anfrage-Kennung muss VOR dem Zugriffslog
    # gesetzt sein. Starlette führt zuletzt hinzugefügte Middleware zuerst aus.
    app.add_middleware(AccessLogMiddleware)
    app.add_middleware(RequestIdMiddleware)

    if settings.cors_origin_list:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=settings.cors_origin_list,
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )

    install_error_handlers(app)
    _install_standard_routen(app, kontext, anmeldung=anmeldung)

    if anmeldung:
        # Erst hier importieren: ein Service ohne Anmeldung soll weder
        # argon2 noch die Auth-Tabellen laden.
        from .auth import anmelde_router

        app.include_router(anmelde_router, prefix="/auth")

    if module is not None:
        _mounte_module(app, module, anmeldung=anmeldung)

    return app


def _mounte_module(app: FastAPI, register: Modulregister, *, anmeldung: bool) -> None:
    if register.braucht_anmeldung and not anmeldung:
        # Lieber gar nicht starten als offen stehen. Ein Artefakt ist per
        # Voreinstellung geschuetzt; ohne Anmeldung gaebe es niemanden, der
        # das pruefen koennte - und die Pruefung fiele stillschweigend aus.
        verschlossen = [m.id for m in register.module if m.zugang.braucht_anmeldung]
        raise RuntimeError(
            f"Die Artefakte {', '.join(sorted(verschlossen))} sind nicht öffentlich. "
            "Dieser Service braucht create_service(..., anmeldung=True), sonst "
            "wäre die Zugriffsprüfung wirkungslos."
        )

    for modul in register.module:
        app.include_router(
            modul.router,
            prefix=modul.praefix,
            tags=[modul.id],
            dependencies=_zugriffspruefung(modul),
        )
    if register.defekte:
        log.error(
            "%d Modul(e) konnten nicht geladen werden: %s",
            len(register.defekte),
            ", ".join(d.id for d in register.defekte),
        )


def _zugriffspruefung(modul: Modul) -> list[Any]:
    """Die Pruefung haengt am ganzen Router, nicht an einzelnen Endpunkten.

    Ein Artefakt bekommt im Lauf der Zeit Endpunkte dazu; haenge die Pruefung
    an jedem einzelnen, ist der vergessene der, der das Loch reisst.
    """
    if modul.zugang is not Zugang.GESCHUETZT:
        return []

    from .auth import erfordert

    return [erfordert(modul.id, modul.mindestrolle)]


@asynccontextmanager
async def _als_kontext(
    fn: Callable[[ServiceContext], AsyncIterator[None]], kontext: ServiceContext
) -> AsyncIterator[None]:
    generator = fn(kontext)
    await anext(generator)
    try:
        yield
    finally:
        # Der Generator soll nach dem yield noch aufraeumen duerfen; dass er
        # dabei endet, ist der Normalfall und kein Fehler.
        with contextlib.suppress(StopAsyncIteration):
            await anext(generator)


def _install_standard_routen(app: FastAPI, kontext: ServiceContext, *, anmeldung: bool) -> None:
    einstellungen = kontext.settings

    @app.get("/health", tags=["betrieb"], summary="Zustand des Service")
    async def health() -> JSONResponse:
        bericht = await kontext.health.run()
        return JSONResponse(
            {
                **bericht.as_dict(),
                "service": einstellungen.service_name,
                "version": einstellungen.service_version,
            },
            status_code=bericht.http_status,
        )

    @app.get("/info", tags=["betrieb"], summary="Was hier läuft")
    async def info() -> dict[str, object]:
        """Nach einem Deploy die schnellste Antwort auf die Frage, welche
        Fassung tatsächlich auf dem Pi angekommen ist."""
        return {
            "service": einstellungen.service_name,
            "version": einstellungen.service_version,
            "environment": einstellungen.environment.value,
            "abhaengigkeiten": sorted(kontext.health.names),
            # Bewusst nur die Anzahl: /info braucht keine Anmeldung, und die
            # Namen der Artefakte gehen nur den etwas an, der sie sehen darf.
            # Wer wissen will, welche es sind, fragt /module.
            "module": len(kontext.module.ids) if kontext.module else 0,
        }

    if kontext.module is not None:
        register = kontext.module

        if anmeldung:
            # Gefiltert, nicht gesperrt: ein Artefakt, fuer das dieser Benutzer
            # kein Recht hat, taucht gar nicht erst auf. Es soll fuer ihn nicht
            # existieren - auch nicht als graue Kachel.
            from .auth.manifest import manifest_router

            app.include_router(manifest_router(register))
            return

        @app.get(
            "/module",
            tags=["betrieb"],
            summary="Welche Artefakte hier laufen",
            description=MANIFEST_BESCHREIBUNG,
        )
        async def module() -> list[dict[str, object]]:
            # Ohne Anmeldung gibt es keine Rechte, nach denen sich filtern
            # liesse. Ein solcher Dienst ist per Definition intern.
            return register.manifest()
