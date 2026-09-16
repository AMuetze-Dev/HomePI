from __future__ import annotations

import uuid

from homepi_core import Base, ZeitstempelMixin
from sqlalchemy import Boolean, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column


class Geraet(Base, ZeitstempelMixin):
    __tablename__ = "geraete"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)
    raum: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    # "wartung" heisst: vorhanden, aber nicht schaltbar
    zustand: Mapped[str] = mapped_column(String(20), nullable=False, default="bereit")
    eingeschaltet: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
