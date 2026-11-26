"""Tabellen dieses Artefakts.

Ein Prüfling trägt seine Bewertung und seine Teilnoten als JSON - so wie der
ExamManager einen Datensatz je Prüfling hielt. Es gibt genau einen Prüfer je
Bogen; Teilschreibvorgänge, die sich in die Quere kommen, sind nicht der Fall,
gegen den man hier Tabellen normalisieren müsste.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import Any

from homepi_core import Base, ZeitstempelMixin
from sqlalchemy import Date, DateTime, ForeignKey, Integer, LargeBinary, String
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, deferred, mapped_column


def _status() -> dict[str, bool]:
    return {
        "runtergeladen": False,
        "kontrolliert": False,
        "abgestimmt": False,
        "hochgeladen": False,
    }


class Pruefungstag(Base, ZeitstempelMixin):
    __tablename__ = "ihk_pruefungstage"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    datum: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    ort: Mapped[str] = mapped_column(String(100), nullable=False, default="")
    korrektor: Mapped[str] = mapped_column(String(100), nullable=False, default="")


class Pruefling(Base, ZeitstempelMixin):
    __tablename__ = "ihk_prueflinge"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tag_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("ihk_pruefungstage.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    reihenfolge: Mapped[int] = mapped_column(Integer, nullable=False)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    ident: Mapped[str] = mapped_column(String(40), nullable=False, default="")
    korrekturart: Mapped[str] = mapped_column(String(20), nullable=False, default="Erstkorrektur")
    status: Mapped[dict[str, bool]] = mapped_column(JSONB, nullable=False, default=_status)
    bewertung: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    teilnoten: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    praesi_start: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    praesi_ende: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    fg_start: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    fg_ende: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class Dokument(Base, ZeitstempelMixin):
    __tablename__ = "ihk_dokumente"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    pruefling_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("ihk_prueflinge.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    art: Mapped[str] = mapped_column(String(10), nullable=False)
    dateiname: Mapped[str] = mapped_column(String(200), nullable=False)
    groesse: Mapped[int] = mapped_column(Integer, nullable=False)
    # deferred: Die Liste der Dokumente braucht die Bytes nicht. Ohne das
    # laedt jede Prueflingsansicht alle PDFs komplett aus der Datenbank.
    daten: Mapped[bytes] = deferred(mapped_column(LargeBinary, nullable=False))
