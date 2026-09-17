"""Die Tabellen. Das Gateway legt sie beim Start an (DB_SCHEMA_ANLEGEN)."""

from __future__ import annotations

import datetime as dt
import uuid

from homepi_core import Base, ZeitstempelMixin
from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
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
    # Wohin der Befund fuehrt, wenn er stehen bleibt. Kommt vom Prueflauf:
    # dieses Artefakt kennt die Spielordnung nicht.
    weg: Mapped[str] = mapped_column(String(20), nullable=False, default="kein")
    entscheidung: Mapped[str] = mapped_column(String(20), nullable=False, default="offen")
    grund: Mapped[str] = mapped_column(String(500), nullable=False, default="")
    entschieden_am: Mapped[dt.datetime | None] = mapped_column(
        DateTime(timezone=True), default=None
    )
    # Die Reihenfolge, in der der Prueflauf sie gemeldet hat. Ohne sie ist die
    # Reihenfolge innerhalb einer Schwere zufaellig und springt bei jedem Laden.
    rang: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    spiel: Mapped[Spielbericht] = relationship(back_populates="befunde")


class Einstellung(Base, ZeitstempelMixin):
    """Was fuer die ganze Installation gilt, als Schluessel und Wert.

    Eine Zeile je Schluessel und keine Tabelle mit festen Spalten: eine
    Einstellung dazuzunehmen soll keine Wanderung der Datenbank kosten.
    Gelesen wird sie ueber `dienst.einstellungen_aus`, das aus den rohen
    Zeichenketten geprueft Werte macht -- die Pruefung steht damit an einer
    Stelle und nicht bei jedem Aufrufer.
    """

    __tablename__ = "staffelpilot_einstellungen"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    schluessel: Mapped[str] = mapped_column(String(60), nullable=False, unique=True)
    wert: Mapped[str] = mapped_column(String(500), nullable=False, default="")


class Mannschaft(Base, ZeitstempelMixin):
    """Eine Mannschaft einer Staffel, mit den hoeherklassigen dahinter.

    Welche Mannschaft eines Vereins ueber welcher steht, liefert DFBnet nicht
    mit -- es wird aus dem Namenszusatz geraten. Ein falscher Schluss faellt
    nicht laut auf: er aendert still, wessen Einsaetze als Stammspieler
    zaehlen. Deshalb steht die Zuordnung hier und ist von Hand korrigierbar.
    """

    __tablename__ = "staffelpilot_mannschaften"
    __table_args__ = (UniqueConstraint("staffel_id", "name", name="uq_mannschaft_je_staffel"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    staffel_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("staffelpilot_staffeln.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    verein: Mapped[str] = mapped_column(String(120), nullable=False, default="")
    nummer: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    ist_sg: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    #: Namen der hoeherklassigen Mannschaften desselben Vereins.
    hoehere: Mapped[list[str]] = mapped_column(JSONB, nullable=False, default=list)
    #: True, sobald jemand die Zuordnung von Hand bestaetigt oder geaendert
    #: hat. Danach ueberschreibt kein Ratevorgang sie mehr.
    bestaetigt: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)


class Vorgang(Base, ZeitstempelMixin):
    """Was aus einem Befund nach aussen geht: Mahnung oder Sportgerichtsfall.

    **Hier wird nichts versendet.** Der Vorgang ist ein Entwurf mit einem
    Text, der aus einer Vorlage entsteht -- Wort fuer Wort vorhersagbar, ohne
    erzeugte Sprache. Wer ihn abschickt, ist ein Mensch, und er tut es in
    seinem Mailprogramm.
    """

    __tablename__ = "staffelpilot_vorgaenge"
    # Ein Befund traegt genau einen Vorgang. Zwei Mahnungen zu demselben
    # Vorfall waeren fuer den Verein nicht unterscheidbar.
    __table_args__ = (UniqueConstraint("befund_id", name="uq_vorgang_je_befund"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    befund_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("staffelpilot_befunde.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    art: Mapped[str] = mapped_column(String(20), nullable=False)
    #: Fortlaufend je Saison, vergeben beim Anlegen. Steht auf jedem Schreiben.
    aktenzeichen: Mapped[str] = mapped_column(String(40), nullable=False, unique=True)
    verein: Mapped[str] = mapped_column(String(120), nullable=False, default="")
    betroffener: Mapped[str] = mapped_column(String(120), nullable=False, default="")
    grund: Mapped[str] = mapped_column(String(500), nullable=False, default="")
    empfaenger: Mapped[str] = mapped_column(String(200), nullable=False, default="")
    betreff: Mapped[str] = mapped_column(String(200), nullable=False, default="")
    text: Mapped[str] = mapped_column(Text, nullable=False, default="")
    zustand: Mapped[str] = mapped_column(String(20), nullable=False, default="entwurf")
    #: Wann ein Mensch gesagt hat, dass er es abgeschickt hat. Nicht, wann das
    #: Programm etwas gesendet haette -- das tut es nie.
    versandt_am: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True), default=None)

    befund: Mapped[Befund] = relationship()


class Regel(Base, ZeitstempelMixin):
    """Was der Pruefdienst prueft, und ob der Staffelleiter das will.

    Der Katalog kommt von aussen: dieses Artefakt kennt die Spielordnung
    nicht. Was es haelt, ist die eine Entscheidung, die dem Staffelleiter
    gehoert -- `aktiv`. Ein erneutes Einspielen des Katalogs laesst sie
    stehen, sonst waere jedes Abschalten bis zum naechsten Start haltbar.
    """

    __tablename__ = "staffelpilot_regeln"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    #: Die technische Kennung, wie sie auch am Befund steht.
    schluessel: Mapped[str] = mapped_column(String(120), nullable=False, unique=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    beschreibung: Mapped[str] = mapped_column(String(1000), nullable=False, default="")
    schwere: Mapped[str] = mapped_column(String(20), nullable=False, default="hinweis")
    weg: Mapped[str] = mapped_column(String(20), nullable=False, default="kein")
    aktiv: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
