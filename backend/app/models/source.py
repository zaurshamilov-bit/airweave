"""Source model."""

from sqlalchemy import JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models._base import Base
from app.platform.auth.schemas import AuthType


class Source(Base):
    """Source model."""

    __tablename__ = "source"

    name: Mapped[str] = mapped_column(String, unique=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    auth_types: Mapped[list[AuthType]] = mapped_column(JSON, nullable=True)
    short_name: Mapped[str] = mapped_column(String, unique=True)
    class_name: Mapped[str] = mapped_column(String, nullable=False)
