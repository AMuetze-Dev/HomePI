"""Gemeinsame Basis fuer die Tabellen aller Module.

Alle Module erben von derselben ``Base``, damit das Gateway ihre Tabellen in
einem Durchgang anlegen kann. Mit je eigener Base muesste es jedes Modul
einzeln kennen - genau das soll es nicht.
"""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import DateTime, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class ZeitstempelMixin:
    """angelegt/geaendert, gepflegt von der Datenbank.

    Bewusst serverseitig (``server_default``): so stimmen die Zeiten auch dann,
    wenn ein Datensatz einmal per SQL entsteht - und die Uhr des Pi ist die
    einzige, auf die es ankommt.
    """

    angelegt: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    geaendert: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=lambda: datetime.now(UTC),
        nullable=False,
    )
