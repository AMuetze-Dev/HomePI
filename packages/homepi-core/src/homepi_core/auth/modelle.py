"""Tabellen der Anmeldung."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..modelle import Base, ZeitstempelMixin


class Benutzer(Base, ZeitstempelMixin):
    __tablename__ = "benutzer"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(32), nullable=False, unique=True, index=True)
    anzeigename: Mapped[str] = mapped_column(String(100), nullable=False)
    passwort_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    aktiv: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    rechte: Mapped[list[Recht]] = relationship(
        back_populates="benutzer", cascade="all, delete-orphan", lazy="selectin"
    )
    sitzungen: Mapped[list[Sitzung]] = relationship(
        back_populates="benutzer", cascade="all, delete-orphan"
    )


class Recht(Base):
    """Eine Rolle je Benutzer und Artefakt.

    Es gibt bewusst keinen globalen Administrator: wer StaffelPilot verwaltet,
    hat damit keinerlei Zugriff auf die Geraete im Haus.
    """

    __tablename__ = "benutzer_rechte"
    __table_args__ = (UniqueConstraint("benutzer_id", "artefakt", name="uq_recht_je_artefakt"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    benutzer_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("benutzer.id", ondelete="CASCADE"), nullable=False, index=True
    )
    artefakt: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    rolle: Mapped[str] = mapped_column(String(20), nullable=False)

    benutzer: Mapped[Benutzer] = relationship(back_populates="rechte")


class Sitzung(Base):
    __tablename__ = "sitzungen"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    # Nur der Hash. Ein Datenbankabzug soll keine lebenden Sitzungen enthalten.
    token_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True, index=True)
    benutzer_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("benutzer.id", ondelete="CASCADE"), nullable=False, index=True
    )
    laeuft_ab: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    angelegt: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    benutzer: Mapped[Benutzer] = relationship(back_populates="sitzungen", lazy="selectin")


class Einrichtung(Base):
    """Das Token, mit dem sich der erste Verwalter anlegen laesst.

    Hoechstens eine Zeile: sie entsteht beim Start, solange es keinen
    Verwalter gibt, und verschwindet, sobald einer da ist. Wie bei den
    Sitzungen steht hier nur der Hash - der Klartext steht einmal im Log und
    sonst nirgends.
    """

    __tablename__ = "einrichtung"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    token_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    angelegt: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
