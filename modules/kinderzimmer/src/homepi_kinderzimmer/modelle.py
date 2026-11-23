"""Tabellen dieses Artefakts.

Alle mit dem Praefix ``kinderzimmer_``: sie teilen sich die Datenbank mit
allen anderen Artefakten.
"""

from __future__ import annotations

import datetime as dt
import uuid
from typing import Any

from homepi_core import Base, ZeitstempelMixin
from sqlalchemy import (
    BigInteger,
    Date,
    DateTime,
    ForeignKey,
    Identity,
    Integer,
    LargeBinary,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, deferred, mapped_column


class Aufnahme(Base, ZeitstempelMixin):
    __tablename__ = "kinderzimmer_aufnahmen"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    titel: Mapped[str] = mapped_column(String(80), nullable=False, unique=True)
    art: Mapped[str] = mapped_column(String(10), nullable=False)
    # deferred: Listen und Manifest brauchen die Bytes nicht. Ohne das laedt
    # jede Liste alle Aufnahmen komplett aus der Datenbank.
    daten: Mapped[bytes] = deferred(mapped_column(LargeBinary, nullable=False))
    sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    dauer_ms: Mapped[int] = mapped_column(Integer, nullable=False)
    # Nicht "bytes": der Name verdeckte im Klassenrumpf den eingebauten Typ,
    # mit dem die Spalte "daten" annotiert ist.
    groesse: Mapped[int] = mapped_column("bytes", Integer, nullable=False)


class Figur(Base, ZeitstempelMixin):
    __tablename__ = "kinderzimmer_figuren"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    uid: Mapped[str] = mapped_column(String(20), nullable=False, unique=True)
    name: Mapped[str] = mapped_column(String(60), nullable=False, unique=True)
    art: Mapped[str] = mapped_column(String(20), nullable=False)
    farbe: Mapped[str | None] = mapped_column(String(20))
    form: Mapped[str | None] = mapped_column(String(20))
    menge: Mapped[int | None] = mapped_column(Integer)
    # RESTRICT: Das Loeschen einer benutzten Aufnahme lehnt schon dienst.py
    # ab. Die Datenbank ist die zweite Linie, falls zwei Anfragen sich kreuzen.
    stimme_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("kinderzimmer_aufnahmen.id", ondelete="RESTRICT")
    )
    klang_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("kinderzimmer_aufnahmen.id", ondelete="RESTRICT")
    )


class EinstellungenZeile(Base, ZeitstempelMixin):
    """Genau eine Zeile. Fehlt sie, gelten die Voreinstellungen aus schemas.py."""

    __tablename__ = "kinderzimmer_einstellungen"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, default=1)
    werte: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)


class Geraet(Base, ZeitstempelMixin):
    __tablename__ = "kinderzimmer_geraete"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(60), nullable=False, unique=True)
    token_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    zuletzt_gesehen: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True))
    firmware: Mapped[str | None] = mapped_column(String(40))
    #: Der Stand, den das Geraet zuletzt gemeldet hat
    stand: Mapped[str | None] = mapped_column(String(64))


class Ereignis(Base):
    __tablename__ = "kinderzimmer_ereignisse"
    # Doppelt senden ist harmlos: nach einem Verbindungsabbruch weiss das
    # Geraet nicht, ob die letzte Sendung ankam, und schickt sie noch einmal.
    __table_args__ = (UniqueConstraint("geraet_id", "start", "nr"),)

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    geraet_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("kinderzimmer_geraete.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    start: Mapped[int] = mapped_column(Integer, nullable=False)
    nr: Mapped[int] = mapped_column(Integer, nullable=False)
    art: Mapped[str] = mapped_column(String(20), nullable=False)
    knopf: Mapped[int | None] = mapped_column(Integer)
    uid: Mapped[str | None] = mapped_column(String(20))
    spiel: Mapped[str | None] = mapped_column(String(40))
    zeitpunkt: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True))
    empfangen: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )


class Tagebucheintrag(Base, ZeitstempelMixin):
    __tablename__ = "kinderzimmer_tagebuch"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    datum: Mapped[dt.date] = mapped_column(Date, nullable=False, index=True)
    text: Mapped[str] = mapped_column(Text, nullable=False)
