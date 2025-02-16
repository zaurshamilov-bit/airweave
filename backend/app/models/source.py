"""Models for sources."""

from typing import TYPE_CHECKING, Optional

from sqlalchemy import JSON, Column, String, UniqueConstraint
from sqlalchemy import Enum as SQLAlchemyEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models._base import OrganizationBase, UserMixin
from app.platform.auth.schemas import AuthType

if TYPE_CHECKING:
    from app.models.connection import Connection


class Source(OrganizationBase, UserMixin):
    """A source that can produce entities."""

    __tablename__ = "source"

    name = Column(String, nullable=False)
    short_name: Mapped[str] = mapped_column(String, unique=True)
    class_name: Mapped[str] = mapped_column(String, nullable=False)
    auth_config_class: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    auth_type: Mapped[Optional[AuthType]] = mapped_column(SQLAlchemyEnum(AuthType), nullable=True)
    description = Column(String)
    # List of entity IDs this source can output
    output_entity_ids = Column(JSON, nullable=False)
    config_schema = Column(JSON, nullable=False)  # JSON Schema for configuration

    __table_args__ = (UniqueConstraint("name", "organization_id", name="uq_source_name_org"),)

    # Back-reference to connections
    connections: Mapped[list["Connection"]] = relationship(
        "Connection",
        primaryjoin="and_(foreign(Connection.short_name) == Source.short_name, "
        "Connection.integration_type == 'SOURCE')",
        back_populates="source",
        lazy="noload",
        viewonly=True,
    )
