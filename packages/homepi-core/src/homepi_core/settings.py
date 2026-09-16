"""Konfiguration, die jeder Microservice braucht.

Eigene Services erben und ergänzen:

    class Settings(ServiceSettings):
        service_name: str = "geraete"
        mqtt_host: str = "mosquitto"

    settings = Settings()

Es gibt bewusst **keinen** Env-Präfix: die Variablennamen sind genau die, die
schon in den Compose-Dateien stehen (``DATABASE_URL``, ``REDIS_URL``, ``TZ``).
Ein Präfix würde nur dazu führen, dass dieselbe Information zweimal existiert.
"""

from __future__ import annotations

from enum import StrEnum
from functools import lru_cache
from typing import Self

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Umgebung(StrEnum):
    ENTWICKLUNG = "entwicklung"
    PRODUKTION = "produktion"
    TEST = "test"


class LogFormat(StrEnum):
    JSON = "json"
    TEXT = "text"


class ServiceSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=None,
        extra="ignore",
        case_sensitive=False,
        # Damit ein Tippfehler wie SERVICE_NMAE nicht still ignoriert wird,
        # sondern beim Start auffällt - siehe validate_bekannte_felder unten.
        validate_default=True,
    )

    # --- Identität -----------------------------------------------------
    service_name: str = "unbenannt"
    service_version: str = "0.0.0"
    environment: Umgebung = Umgebung.ENTWICKLUNG

    # --- Laufzeit ------------------------------------------------------
    host: str = "0.0.0.0"
    port: int = 8000
    # uvicorn-Konvention. Default 1: auf einem Vier-Kern-Pi mit mehreren
    # Services kostet jeder zusätzliche Worker ~120 MB und bringt nichts,
    # solange der Service I/O-gebunden ist.
    web_concurrency: int = Field(default=1, ge=1, le=8)
    root_path: str = ""

    # --- Logging -------------------------------------------------------
    log_level: str = "info"
    log_format: LogFormat | None = None

    # --- Abhängigkeiten ------------------------------------------------
    database_url: str | None = None
    redis_url: str | None = None

    # --- HTTP ----------------------------------------------------------
    cors_origins: str = ""

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def ist_produktion(self) -> bool:
        return self.environment is Umgebung.PRODUKTION

    @property
    def effektives_log_format(self) -> LogFormat:
        """In Produktion JSON (maschinenlesbar), sonst Text (menschenlesbar).

        Explizit gesetztes LOG_FORMAT hat immer Vorrang.
        """
        if self.log_format is not None:
            return self.log_format
        return LogFormat.JSON if self.ist_produktion else LogFormat.TEXT

    @model_validator(mode="after")
    def _pruefe_produktionsbedingungen(self) -> Self:
        """Fehler, die in Produktion teuer sind, sollen beim Start auffallen
        und nicht erst, wenn jemand die Oberfläche aufruft."""
        if not self.ist_produktion:
            return self

        if self.service_name == "unbenannt":
            raise ValueError(
                "SERVICE_NAME muss in Produktion gesetzt sein - sonst sind Logs "
                "und Metriken mehrerer Services nicht auseinanderzuhalten"
            )
        if self.cors_origins.strip() == "*":
            raise ValueError(
                "CORS_ORIGINS='*' zusammen mit Cookies ist in Produktion nicht "
                "zulässig; trage die konkreten Ursprünge ein"
            )
        return self


@lru_cache
def get_settings() -> ServiceSettings:
    """Zwischengespeichert, damit Settings nicht bei jedem Zugriff die Umgebung
    neu liest. In Tests mit ``get_settings.cache_clear()`` zurücksetzen."""
    return ServiceSettings()
