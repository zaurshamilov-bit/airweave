"""Destination model."""

from sqlalchemy import String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models._base import Base


class Destination(Base):
    """Destination model."""

    __tablename__ = "destination"

    name: Mapped[str] = mapped_column(String, nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    short_name: Mapped[str] = mapped_column(String, unique=True)
    class_name: Mapped[str] = mapped_column(String, nullable=False)
