from __future__ import annotations

import json
import logging

from homepi_core.logging import JsonFormatter, TextFormatter, request_id_var


def _record(nachricht: str = "hallo", **extra: object) -> logging.LogRecord:
    record = logging.LogRecord("test", logging.INFO, "pfad.py", 1, nachricht, None, None)
    for schluessel, wert in extra.items():
        setattr(record, schluessel, wert)
    return record


def test_json_zeile_ist_gueltiges_json() -> None:
    zeile = JsonFormatter("geraete", "1.2.3").format(_record())
    eintrag = json.loads(zeile)

    assert eintrag["service"] == "geraete"
    assert eintrag["version"] == "1.2.3"
    assert eintrag["nachricht"] == "hallo"
    assert eintrag["level"] == "info"


def test_extra_felder_landen_im_json() -> None:
    zeile = JsonFormatter("x", "0").format(_record(dauer_ms=12.5, pfad="/a"))
    eintrag = json.loads(zeile)

    assert eintrag["dauer_ms"] == 12.5
    assert eintrag["pfad"] == "/a"


def test_request_id_wird_automatisch_ergaenzt() -> None:
    token = request_id_var.set("abc123")
    try:
        eintrag = json.loads(JsonFormatter("x", "0").format(_record()))
    finally:
        request_id_var.reset(token)

    assert eintrag["request_id"] == "abc123"


def test_ohne_request_id_fehlt_das_feld() -> None:
    eintrag = json.loads(JsonFormatter("x", "0").format(_record()))

    assert "request_id" not in eintrag


def test_textformat_haengt_die_kennung_an() -> None:
    token = request_id_var.set("abcdef0123456789")
    try:
        zeile = TextFormatter().format(_record())
    finally:
        request_id_var.reset(token)

    assert zeile.endswith("[abcdef01]")
