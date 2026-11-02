"""Die Tabellen. Das Gateway legt sie beim Start an (DB_SCHEMA_ANLEGEN).

Vier Stueck, und jede steht fuer eine Frage, die der Haushalt stellt:
wer teilt (Person), wo liegt das Geld (Konto), wofuer geht es weg
(Kategorie), und was genau passiert jeden Monat (Posten).
"""

from __future__ import annotations

import uuid
from decimal import Decimal

from homepi_core import Base, ZeitstempelMixin
from sqlalchemy import Boolean, ForeignKey, Integer, Numeric, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship


class Person(Base, ZeitstempelMixin):
    """Wer am Haushalt beteiligt ist.

    Bewusst nicht der angemeldete Benutzer: wer die Zahlen pflegt, und wer
    sich die Miete teilt, ist nicht dieselbe Frage. Ein Haushalt laesst sich
    sonst nicht fuehren, solange nicht beide ein Konto auf dem Pi haben.
    """

    __tablename__ = "haushaltsbuch_personen"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(80), nullable=False, unique=True)
    reihenfolge: Mapped[int] = mapped_column(Integer, nullable=False, default=0)


class Kategorie(Base, ZeitstempelMixin):
    __tablename__ = "haushaltsbuch_kategorien"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(80), nullable=False, unique=True)
    # Trennt Ruecklage und Anlage vom Verbrauch. Ohne diese Spalte waere die
    # Sparquote nur zu raten.
    zaehlt_als_sparen: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    reihenfolge: Mapped[int] = mapped_column(Integer, nullable=False, default=0)


class Konto(Base, ZeitstempelMixin):
    __tablename__ = "haushaltsbuch_konten"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(80), nullable=False, unique=True)
    art: Mapped[str] = mapped_column(String(20), nullable=False, default="verbrauch")
    # NULL heisst gemeinschaftlich. Kein eigenes Kennzeichen daneben: zwei
    # Spalten fuer eine Aussage laufen irgendwann auseinander.
    #
    # RESTRICT statt CASCADE: wer eine Person loescht, soll ihre Konten
    # vorher sehen und entscheiden - nicht hinterher suchen.
    inhaber_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("haushaltsbuch_personen.id", ondelete="RESTRICT"),
        nullable=True,
        index=True,
    )
    notiz: Mapped[str] = mapped_column(String(200), nullable=False, default="")
    reihenfolge: Mapped[int] = mapped_column(Integer, nullable=False, default=0)


class Posten(Base, ZeitstempelMixin):
    """Eine wiederkehrende Buchung - Einnahme oder Ausgabe.

    ``betrag`` ist immer das, was die Bank abbucht. Was monatlich
    zurueckzulegen ist, steht nirgends: es wird gerechnet. Zwei Zahlen fuer
    denselben Sachverhalt waeren der sichere Weg, dass eine davon falsch ist.
    """

    __tablename__ = "haushaltsbuch_posten"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(80), nullable=False)
    art: Mapped[str] = mapped_column(String(10), nullable=False, default="ausgabe")
    # Numeric, nicht Float: 0,1 + 0,2 soll 0,3 sein.
    betrag: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False, default=Decimal("0"))
    intervall_monate: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    faelligkeitsmonat: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    abbuchungstag: Mapped[int | None] = mapped_column(Integer, nullable=True, default=None)
    konto_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("haushaltsbuch_konten.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    # SET NULL: eine geloeschte Kategorie darf keinen Posten mitnehmen. Er
    # steht dann unter "Ohne Kategorie" und faellt dort auf.
    kategorie_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("haushaltsbuch_kategorien.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    variabel: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    aktiv: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    # selectin, weil die Auswertung immer alle Anteile braucht: ohne sie
    # faellt je Posten eine eigene Abfrage an.
    anteile: Mapped[list[Anteil]] = relationship(
        cascade="all, delete-orphan", lazy="selectin", order_by="Anteil.person_id"
    )


class Anteil(Base):
    """Wie viel eines gemeinsamen Postens auf eine Person entfaellt.

    Gewicht statt Prozent - siehe schemas.Anteil.
    """

    __tablename__ = "haushaltsbuch_anteile"
    __table_args__ = (UniqueConstraint("posten_id", "person_id", name="uq_anteil_je_person"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    posten_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("haushaltsbuch_posten.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    person_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("haushaltsbuch_personen.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    gewicht: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
