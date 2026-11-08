"""Tabellen dieses Artefakts.

Erben von homepi_core.Base - alle Module teilen sich diese Metadata, deshalb
legt das Gateway die Tabellen in einem Durchgang an.

Der Zuschnitt in einem Satz: ein Turnier hat Teilnehmer, die Teilnehmer
stehen in Gruppen, und die Spiele sind eine fortlaufend numerierte Liste, die
Gruppenphase und KO-Raster gemeinsam traegt. Ein KO-Spiel kennt seine
Gegner anfangs nicht - es verweist auf die Nummern der Spiele, deren Sieger
bei ihm einlaufen. Deshalb steht das ganze Raster, bevor der erste Ball
gespielt ist.
"""

from __future__ import annotations

import datetime as dt
import uuid

from homepi_core import Base, ZeitstempelMixin
from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship


class Turnier(Base, ZeitstempelMixin):
    __tablename__ = "tischtennis_turniere"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)

    #: gruppen_ko | ko | schweizer
    modus: Mapped[str] = mapped_column(String(20), nullable=False, default="gruppen_ko")
    #: planung | laufend | beendet
    zustand: Mapped[str] = mapped_column(String(20), nullable=False, default="planung")

    tische: Mapped[int] = mapped_column(Integer, nullable=False, default=2)
    best_of: Mapped[int] = mapped_column(Integer, nullable=False, default=5)
    punkte_bis: Mapped[int] = mapped_column(Integer, nullable=False, default=11)
    minuten_pro_spiel: Mapped[int] = mapped_column(Integer, nullable=False, default=12)

    #: nur bei gruppen_ko
    anzahl_gruppen: Mapped[int] = mapped_column(Integer, nullable=False, default=2)
    weiter_pro_gruppe: Mapped[int] = mapped_column(Integer, nullable=False, default=2)
    #: nur bei schweizer
    runden: Mapped[int] = mapped_column(Integer, nullable=False, default=4)

    #: Die Saat, mit der ausgelost wurde. Steht hier, damit "so wurde
    #: ausgewuerfelt" eine nachvollziehbare Auskunft ist und keine
    #: Behauptung - mit derselben Saat entsteht dasselbe Los.
    saat: Mapped[int | None] = mapped_column(Integer, nullable=True, default=None)

    #: Welche Runde im Schweizer System bzw. welche KO-Runde zuletzt
    #: angesetzt wurde. Bei gruppen_ko bleibt es 0, bis das Raster steht.
    runde_angesetzt: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    #: Steht das KO-Raster schon? Nur bei gruppen_ko von Belang.
    ko_steht: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    teilnehmer: Mapped[list[Teilnehmer]] = relationship(
        back_populates="turnier", cascade="all, delete-orphan"
    )
    gruppen: Mapped[list[Gruppe]] = relationship(
        back_populates="turnier", cascade="all, delete-orphan"
    )
    spiele: Mapped[list[Spiel]] = relationship(
        back_populates="turnier", cascade="all, delete-orphan"
    )


class Gruppe(Base, ZeitstempelMixin):
    __tablename__ = "tischtennis_gruppen"
    __table_args__ = (UniqueConstraint("turnier_id", "nummer", name="uq_gruppe_je_turnier"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    turnier_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tischtennis_turniere.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    #: 0-basiert, wie im Los.
    nummer: Mapped[int] = mapped_column(Integer, nullable=False)
    #: "Gruppe A", "Gruppe B", ...
    name: Mapped[str] = mapped_column(String(20), nullable=False)

    turnier: Mapped[Turnier] = relationship(back_populates="gruppen")


class Teilnehmer(Base, ZeitstempelMixin):
    __tablename__ = "tischtennis_teilnehmer"
    __table_args__ = (UniqueConstraint("turnier_id", "name", name="uq_teilnehmer_je_turnier"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    turnier_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tischtennis_turniere.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    #: Abteilung, Standort, Spitzname - was beim Zuordnen hilft.
    notiz: Mapped[str] = mapped_column(String(100), nullable=False, default="")

    gruppe_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tischtennis_gruppen.id", ondelete="SET NULL"),
        nullable=True,
        default=None,
    )
    #: Wie oft dieser Teilnehmer im Schweizer System ein Freilos hatte.
    #: Zweimal soll niemand eines bekommen.
    freilose: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    turnier: Mapped[Turnier] = relationship(back_populates="teilnehmer")


class Spiel(Base, ZeitstempelMixin):
    __tablename__ = "tischtennis_spiele"
    __table_args__ = (UniqueConstraint("turnier_id", "nummer", name="uq_spiel_je_turnier"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    turnier_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tischtennis_turniere.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    #: Fortlaufend ab 1 und gleichzeitig die Reihenfolge des Spielplans.
    #: KO-Spiele verweisen ueber diese Nummer aufeinander.
    nummer: Mapped[int] = mapped_column(Integer, nullable=False)

    #: gruppe | ko | runde (Schweizer System)
    phase: Mapped[str] = mapped_column(String(10), nullable=False)
    runde: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    #: "Gruppe A - Runde 1", "Halbfinale", "Runde 3". Steht in der Datenbank
    #: und nicht im Frontend: welche KO-Runde ein Halbfinale ist, haengt an
    #: der Rastergroesse, und die kennt nur der, der es angelegt hat.
    bezeichnung: Mapped[str] = mapped_column(String(40), nullable=False, default="")

    gruppe_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tischtennis_gruppen.id", ondelete="CASCADE"),
        nullable=True,
        default=None,
    )

    heim_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tischtennis_teilnehmer.id", ondelete="CASCADE"),
        nullable=True,
        default=None,
    )
    gast_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tischtennis_teilnehmer.id", ondelete="CASCADE"),
        nullable=True,
        default=None,
    )
    #: Nummer des Spiels, dessen Sieger hier einlaeuft - solange er noch
    #: nicht feststeht.
    heim_aus_spiel: Mapped[int | None] = mapped_column(Integer, nullable=True, default=None)
    gast_aus_spiel: Mapped[int | None] = mapped_column(Integer, nullable=True, default=None)

    #: geplant | laeuft | beendet
    zustand: Mapped[str] = mapped_column(String(10), nullable=False, default="geplant")
    tisch: Mapped[int | None] = mapped_column(Integer, nullable=True, default=None)
    begonnen_am: Mapped[dt.datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, default=None
    )
    beendet_am: Mapped[dt.datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, default=None
    )

    #: [[11, 9], [9, 11], ...] - Satz fuer Satz, Heim zuerst. JSONB und
    #: keine zehn Spalten, von denen sieben leer sind.
    saetze: Mapped[list[list[int]]] = mapped_column(JSONB, nullable=False, default=list)
    sieger_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tischtennis_teilnehmer.id", ondelete="SET NULL"),
        nullable=True,
        default=None,
    )
    #: Ein Spiel ohne Gegner: im Schweizer System bei ungerader Zahl. Es ist
    #: beendet, sobald es angesetzt ist, und niemand steht dafuer am Tisch.
    freilos: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    turnier: Mapped[Turnier] = relationship(back_populates="spiele")
