"""Models for destinations."""

from typing import TYPE_CHECKING, Optional

from sqlalchemy import JSON, String, Text, UniqueConstraint
from sqlalchemy import Enum as SQLAlchemyEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models._base import OrganizationBase, UserMixin
from app.platform.auth.schemas import AuthType

if TYPE_CHECKING:
    from app.models.connection import Connection


class Destination(OrganizationBase, UserMixin):
    """A destination that can consume entities."""

    __tablename__ = "destination"

    name: Mapped[str] = mapped_column(String, nullable=False)
    short_name: Mapped[str] = mapped_column(String, unique=True)
    class_name: Mapped[str] = mapped_column(String, nullable=False)
    auth_config_class: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    auth_type: Mapped[Optional[AuthType]] = mapped_column(SQLAlchemyEnum(AuthType), nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    input_entity_ids: Mapped[Optional[JSON]] = mapped_column(JSON, nullable=False)
    config_schema: Mapped[Optional[JSON]] = mapped_column(JSON, nullable=False)

    # Back-reference to connections
    connections: Mapped[list["Connection"]] = relationship(
        "Connection",
        primaryjoin="and_(foreign(Connection.short_name) == Destination.short_name, "
        "Connection.integration_type == 'DESTINATION')",
        back_populates="destination",
        lazy="noload",
        viewonly=True,
    )

    __table_args__ = (UniqueConstraint("name", "organization_id", name="uq_destination_name_org"),)
