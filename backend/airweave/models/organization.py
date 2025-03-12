"""Organization models."""

from typing import TYPE_CHECKING

from sqlalchemy import String, Text
from sqlalchemy.orm import Mapped, mapped_column

from airweave.models._base import Base

if TYPE_CHECKING:
    pass


class Organization(Base):
    """Organization model."""

    __tablename__ = "organization"

    name: Mapped[str] = mapped_column(String, unique=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
