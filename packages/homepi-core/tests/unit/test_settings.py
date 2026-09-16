from __future__ import annotations

import pytest
from pydantic import ValidationError

from homepi_core.settings import LogFormat, ServiceSettings, Umgebung


def test_liest_aus_der_umgebung(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SERVICE_NAME", "geraete")
    monkeypatch.setenv("PORT", "9000")

    einstellungen = ServiceSettings()

    assert einstellungen.service_name == "geraete"
    assert einstellungen.port == 9000


def test_cors_wird_zu_einer_liste() -> None:
    einstellungen = ServiceSettings(cors_origins="https://a.de, https://b.de ,")

    assert einstellungen.cors_origin_list == ["https://a.de", "https://b.de"]


def test_log_format_folgt_der_umgebung() -> None:
    """Lokal lesbar, in Produktion maschinenlesbar - ohne dass man es setzt."""
    assert ServiceSettings().effektives_log_format is LogFormat.TEXT
    assert (
        ServiceSettings(environment=Umgebung.PRODUKTION, service_name="x").effektives_log_format
        is LogFormat.JSON
    )


def test_explizites_log_format_hat_vorrang() -> None:
    einstellungen = ServiceSettings(
        environment=Umgebung.PRODUKTION, service_name="x", log_format=LogFormat.TEXT
    )

    assert einstellungen.effektives_log_format is LogFormat.TEXT


def test_produktion_ohne_service_namen_startet_nicht() -> None:
    """Sonst sind die Logs mehrerer Services nicht auseinanderzuhalten."""
    with pytest.raises(ValidationError, match="SERVICE_NAME"):
        ServiceSettings(environment=Umgebung.PRODUKTION)


def test_produktion_mit_offenem_cors_startet_nicht() -> None:
    with pytest.raises(ValidationError, match="CORS_ORIGINS"):
        ServiceSettings(environment=Umgebung.PRODUKTION, service_name="x", cors_origins="*")


def test_entwicklung_darf_alles() -> None:
    einstellungen = ServiceSettings(cors_origins="*")

    assert einstellungen.ist_produktion is False


def test_worker_anzahl_ist_begrenzt() -> None:
    """Auf einem Vier-Kern-Pi ist ein zweistelliger Wert immer ein Versehen."""
    with pytest.raises(ValidationError):
        ServiceSettings(web_concurrency=99)
