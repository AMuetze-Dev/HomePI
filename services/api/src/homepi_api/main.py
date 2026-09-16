"""FastAPI-Anwendung. Verdrahtung, keine Logik."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from . import __version__, db
from .config import get_settings
from .health import evaluate


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    yield
    await db.dispose_engine()


def create_app() -> FastAPI:
    """Factory statt Modul-Singleton: Tests bekommen eine frische Instanz."""
    settings = get_settings()
    app = FastAPI(title="HomePI API", version=__version__, lifespan=lifespan)

    if settings.cors_origin_list:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=settings.cors_origin_list,
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )

    @app.get("/health")
    async def health() -> JSONResponse:
        report = evaluate({"database": await db.ping()})
        payload: dict[str, Any] = {
            "status": report.status.value,
            "version": __version__,
            "checks": report.checks,
        }
        return JSONResponse(payload, status_code=report.http_status)

    return app


app = create_app()
