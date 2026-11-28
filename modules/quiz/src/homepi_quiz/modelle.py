"""Tabellen dieses Artefakts.

Erben von homepi_core.Base - alle Module teilen sich diese Metadata, deshalb
legt das Gateway die Tabellen in einem Durchgang an. In Produktion ist das
``homepi schema anlegen`` im Gateway-Container.

Ein Spieler hat kein Konto. Was ihn ausweist, ist ein Token in seinem Cookie;
hier steht davon nur der SHA-256 - wie bei den Sitzungen in homepi-core. Ein
Datenbankabzug enthaelt damit niemanden, unter dessen Namen man weiterspielen
koennte.
"""

from __future__ import annotations

import datetime as dt
import uuid
from typing import Any

from homepi_core import Base, ZeitstempelMixin
from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    ForeignKey,
    Identity,
    Integer,
    LargeBinary,
    String,
    Text,
    UniqueConstraint,
    func,
    true,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column


def _id() -> Mapped[uuid.UUID]:
    return mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)


class Katalog(Base, ZeitstempelMixin):
    __tablename__ = "quiz_kataloge"

    id: Mapped[uuid.UUID] = _id()
    titel: Mapped[str] = mapped_column(String(120), nullable=False)
    beschreibung: Mapped[str] = mapped_column(Text, nullable=False, default="")


class Frage(Base, ZeitstempelMixin):
    __tablename__ = "quiz_fragen"

    id: Mapped[uuid.UUID] = _id()
    katalog_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("quiz_kataloge.id", ondelete="CASCADE"), nullable=False, index=True
    )
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    kategorie: Mapped[str] = mapped_column(String(60), nullable=False, default="")
    punkte: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    zeitlimit: Mapped[int | None] = mapped_column(Integer, nullable=True)
    #: Typ und typeigene Felder samt Loesung, geprueft von ``schemas.FrageDaten``.
    daten: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)


class Bild(Base):
    """Eigene Tabelle, damit die Liste der Fragen keine Megabytes mitschleppt."""

    __tablename__ = "quiz_bilder"

    frage_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("quiz_fragen.id", ondelete="CASCADE"), primary_key=True
    )
    mime: Mapped[str] = mapped_column(String(40), nullable=False)
    inhalt: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)


class Freigabe(Base):
    """Ein Katalog, aus dem jeder ohne Konto eine Runde starten darf."""

    __tablename__ = "quiz_freigaben"

    katalog_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("quiz_kataloge.id", ondelete="CASCADE"), primary_key=True
    )
    angelegt: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class Medium(Base):
    """Weitere Medien an einer Frage: ``ton`` und ``option-<n>``.

    Eigene Tabelle neben ``quiz_bilder`` und nicht deren Umbau: die laeuft
    schon auf dem Pi, und ein neuer Schluessel waere eine Migration mit
    Datenumzug fuer nichts.
    """

    __tablename__ = "quiz_medien"

    frage_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("quiz_fragen.id", ondelete="CASCADE"), primary_key=True
    )
    schluessel: Mapped[str] = mapped_column(String(20), primary_key=True)
    mime: Mapped[str] = mapped_column(String(40), nullable=False)
    inhalt: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)


class Runde(Base, ZeitstempelMixin):
    __tablename__ = "quiz_runden"

    id: Mapped[uuid.UUID] = _id()
    code: Mapped[str] = mapped_column(String(6), nullable=False, unique=True)
    katalog_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("quiz_kataloge.id", ondelete="CASCADE"), nullable=False, index=True
    )
    status: Mapped[str] = mapped_column(String(10), nullable=False, default="lobby")
    phase: Mapped[str] = mapped_column(String(12), nullable=False, default="keine")
    frage_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("quiz_fragen.id", ondelete="SET NULL"), nullable=True
    )
    bild_sichtbar: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    frist: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    #: Fragen, die in dieser Runde schon aufgeloest wurden.
    erledigt: Mapped[list[str]] = mapped_column(JSONB, nullable=False, default=list)
    #: Nachgetragen: scripts/migrationen/2026-11-28-quiz-beitritt-offen.sql
    beitritt_offen: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default=true()
    )


class Moderation(Base):
    """Wer eine Runde leitet, ohne Konto: der Hash seines Moderatorcodes.

    Eigene Tabelle statt Spalten an ``quiz_runden`` - die laeuft schon auf dem
    Pi, und neue Tabellen legt ``homepi schema anlegen`` ohne Migration an.
    """

    __tablename__ = "quiz_moderation"

    runde_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("quiz_runden.id", ondelete="CASCADE"), primary_key=True
    )
    code_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    #: Ohne Konto gestartet: wird nach zwei Tagen Ruhe aufgeraeumt.
    ohne_konto: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    #: Der Katalog wurde mit der Runde hochgeladen und geht mit ihr.
    eigener_katalog: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    zuletzt_aktiv: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class Team(Base):
    __tablename__ = "quiz_teams"
    __table_args__ = (UniqueConstraint("runde_id", "schluessel", name="uq_quiz_team_name"),)

    id: Mapped[uuid.UUID] = _id()
    runde_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("quiz_runden.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(30), nullable=False)
    schluessel: Mapped[str] = mapped_column(String(100), nullable=False)
    angelegt: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class Spieler(Base):
    __tablename__ = "quiz_spieler"
    __table_args__ = (
        # Die eigentliche Sicherung des Namens: die Datenbank, nicht eine
        # Vorabpruefung, die zwei gleichzeitige Beitritte beide bestuenden.
        UniqueConstraint("runde_id", "schluessel", name="uq_quiz_spieler_name"),
    )

    id: Mapped[uuid.UUID] = _id()
    runde_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("quiz_runden.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(24), nullable=False)
    #: ``casefold`` des Namens - eindeutig je Runde.
    schluessel: Mapped[str] = mapped_column(String(100), nullable=False)
    token_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    wiederkehr_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    wiederkehr_bis: Mapped[dt.datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    beigetreten: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    zuletzt_gesehen: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class Teammitglied(Base):
    """Eigene Tabelle statt einer Spalte an ``quiz_spieler``: die Tabelle
    laeuft schon, und eine neue Fremdschluesselspalte waere eine Migration
    mehr. Ein Spieler ist in hoechstens einem Team - der Primaerschluessel."""

    __tablename__ = "quiz_teammitglieder"

    spieler_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("quiz_spieler.id", ondelete="CASCADE"), primary_key=True
    )
    team_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("quiz_teams.id", ondelete="CASCADE"), nullable=False, index=True
    )


class Antwort(Base):
    __tablename__ = "quiz_antworten"
    __table_args__ = (UniqueConstraint("spieler_id", "frage_id", name="uq_quiz_antwort"),)

    id: Mapped[uuid.UUID] = _id()
    runde_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("quiz_runden.id", ondelete="CASCADE"), nullable=False, index=True
    )
    frage_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("quiz_fragen.id", ondelete="CASCADE"), nullable=False
    )
    spieler_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("quiz_spieler.id", ondelete="CASCADE"), nullable=False
    )
    wert: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    eingeloggt: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    punkte: Mapped[int | None] = mapped_column(Integer, nullable=True)
    richtig: Mapped[bool | None] = mapped_column(Boolean, nullable=True)


class Buzzer(Base):
    __tablename__ = "quiz_buzzer"
    __table_args__ = (UniqueConstraint("spieler_id", "frage_id", name="uq_quiz_buzzer"),)

    id: Mapped[uuid.UUID] = _id()
    #: Reihenfolge des Eintreffens. Eine Sequenz und keine Uhrzeit des
    #: Handys: wer zuerst ankommt, ist zuerst dran.
    reihe: Mapped[int] = mapped_column(BigInteger, Identity(), nullable=False)
    runde_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("quiz_runden.id", ondelete="CASCADE"), nullable=False, index=True
    )
    frage_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("quiz_fragen.id", ondelete="CASCADE"), nullable=False
    )
    spieler_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("quiz_spieler.id", ondelete="CASCADE"), nullable=False
    )
    urteil: Mapped[str] = mapped_column(String(8), nullable=False, default="wartet")
    punkte: Mapped[int | None] = mapped_column(Integer, nullable=True)


class Korrektur(Base):
    """Punkte von Hand, ausserhalb einer Frage: ein Bonus, ein Abzug."""

    __tablename__ = "quiz_korrekturen"

    id: Mapped[uuid.UUID] = _id()
    runde_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("quiz_runden.id", ondelete="CASCADE"), nullable=False, index=True
    )
    spieler_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("quiz_spieler.id", ondelete="CASCADE"), nullable=False
    )
    punkte: Mapped[int] = mapped_column(Integer, nullable=False)
    grund: Mapped[str] = mapped_column(String(120), nullable=False, default="")
    angelegt: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
