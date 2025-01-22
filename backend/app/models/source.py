"""Source model."""

from typing import TYPE_CHECKING, Optional

from sqlalchemy import Enum as SQLAlchemyEnum
from sqlalchemy import String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models._base import Base
from app.platform.auth.schemas import AuthType

if TYPE_CHECKING:
    from app.models.connection import Connection


class Source(Base):
    """Source model."""

    __tablename__ = "source"

    name: Mapped[str] = mapped_column(String, unique=True)
    short_name: Mapped[str] = mapped_column(String, unique=True)
    class_name: Mapped[str] = mapped_column(String, nullable=False)
    auth_config_class: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    auth_type: Mapped[Optional[AuthType]] = mapped_column(SQLAlchemyEnum(AuthType), nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Back-reference to connections
    connections: Mapped[list["Connection"]] = relationship(
        "Connection",
        primaryjoin="and_(foreign(Connection.short_name) == Source.short_name, "
        "Connection.integration_type == 'SOURCE')",
        back_populates="source",
        lazy="noload",
        viewonly=True,
    )
