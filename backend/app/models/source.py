"""Source model."""

from typing import Optional

from sqlalchemy import Enum as SQLAlchemyEnum
from sqlalchemy import String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models._base import Base
from app.platform.auth.schemas import AuthType


class Source(Base):
    """Source model."""

    __tablename__ = "source"

    name: Mapped[str] = mapped_column(String, unique=True)
    short_name: Mapped[str] = mapped_column(String, unique=True)
    class_name: Mapped[str] = mapped_column(String, nullable=False)
    auth_config_class: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    auth_type: Mapped[Optional[AuthType]] = mapped_column(SQLAlchemyEnum(AuthType), nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
