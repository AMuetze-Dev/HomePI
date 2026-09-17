"""Die Tabellen. Das Gateway legt sie beim Start an (DB_SCHEMA_ANLEGEN)."""

from __future__ import annotations

import datetime as dt
import uuid

from homepi_core import Base, ZeitstempelMixin
from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship


class Staffel(Base, ZeitstempelMixin):
    __tablename__ = "staffelpilot_staffeln"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(120), nullable=False, unique=True)
    altersklasse: Mapped[str] = mapped_column(String(20), nullable=False)
    # Die Spielklasse, wie sie in DFBnet heisst -- "1.Kreisklasse". Sie ist
    # nicht eindeutig: dieselbe Klasse gibt es fuer Herren und fuer Ue35.
    spielklasse: Mapped[str] = mapped_column(String(120), nullable=False)
    saison: Mapped[str] = mapped_column(String(10), nullable=False, default="")
    aktiv: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    spiele: Mapped[list[Spielbericht]] = relationship(
        back_populates="staffel", cascade="all, delete-orphan"
    )


class Spielbericht(Base, ZeitstempelMixin):
    __tablename__ = "staffelpilot_spielberichte"
    # Dieselbe DFBnet-Kennung darf in zwei Staffeln vorkommen, in einer nicht
    # zweimal. Geprueft von der Datenbank, nicht vom Code: eine Vorabpruefung
    # waere ein Rennen zwischen zwei gleichzeitigen Importen.
    __table_args__ = (UniqueConstraint("staffel_id", "dfbnet_id", name="uq_spiel_je_staffel"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    staffel_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("staffelpilot_staffeln.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    dfbnet_id: Mapped[str] = mapped_column(String(120), nullable=False)
    datum: Mapped[dt.date] = mapped_column(Date, nullable=False, index=True)
    heim: Mapped[str] = mapped_column(String(120), nullable=False)
    gast: Mapped[str] = mapped_column(String(120), nullable=False)
    ergebnis: Mapped[str] = mapped_column(String(120), nullable=False, default="")
    abgehakt: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    abgehakt_am: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True), default=None)

    staffel: Mapped[Staffel] = relationship(back_populates="spiele")
    befunde: Mapped[list[Befund]] = relationship(
        back_populates="spiel", cascade="all, delete-orphan", lazy="selectin"
    )


class Befund(Base, ZeitstempelMixin):
    __tablename__ = "staffelpilot_befunde"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    spiel_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("staffelpilot_spielberichte.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    regel: Mapped[str] = mapped_column(String(120), nullable=False)
    schwere: Mapped[str] = mapped_column(String(20), nullable=False)
    titel: Mapped[str] = mapped_column(String(120), nullable=False)
    text: Mapped[str] = mapped_column(String(2000), nullable=False, default="")
    person: Mapped[str] = mapped_column(String(120), nullable=False, default="")
    mannschaft: Mapped[str] = mapped_column(String(120), nullable=False, default="")
    entscheidung: Mapped[str] = mapped_column(String(20), nullable=False, default="offen")
    grund: Mapped[str] = mapped_column(String(500), nullable=False, default="")
    entschieden_am: Mapped[dt.datetime | None] = mapped_column(
        DateTime(timezone=True), default=None
    )
    # Die Reihenfolge, in der der Prueflauf sie gemeldet hat. Ohne sie ist die
    # Reihenfolge innerhalb einer Schwere zufaellig und springt bei jedem Laden.
    rang: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    spiel: Mapped[Spielbericht] = relationship(back_populates="befunde")
