"""Source connection model."""

from typing import TYPE_CHECKING, List, Optional
from uuid import UUID

from sqlalchemy import JSON, ForeignKey, String, Text
from sqlalchemy import Enum as SQLAlchemyEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from airweave.core.shared_models import SourceConnectionStatus
from airweave.models._base import OrganizationBase, UserMixin

if TYPE_CHECKING:
    from airweave.models.collection import Collection
    from airweave.models.connection import Connection
    from airweave.models.sync import Sync


class SourceConnection(OrganizationBase, UserMixin):
    """Source connection model for connecting to external data sources.

    This is a user-facing model that encompasses the connection and sync information for a
    specific source. Not to be confused with the connection model, which is a system table
    that contains the connection information for all integrations.
    """

    __tablename__ = "source_connection"

    name: Mapped[str] = mapped_column(String, nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    short_name: Mapped[str] = mapped_column(String, nullable=False)  # Source short name

    # Configuration fields for the source connection
    config_fields: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)

    # Related objects
    readable_collection_id: Mapped[Optional[UUID]] = mapped_column(
        ForeignKey("collection.readable_id", ondelete="CASCADE"), nullable=True
    )
    connection_id: Mapped[Optional[UUID]] = mapped_column(
        ForeignKey("connection.id", ondelete="CASCADE"), nullable=True
    )
    status: Mapped[SourceConnectionStatus] = mapped_column(
        SQLAlchemyEnum(SourceConnectionStatus), default=SourceConnectionStatus.ACTIVE
    )

    # Relationships
    syncs: Mapped[List["Sync"]] = relationship(
        "Sync",
        back_populates="source_connection",
        lazy="noload",
        cascade="all, delete-orphan",
    )
    collection: Mapped[Optional["Collection"]] = relationship(
        "Collection",
        foreign_keys=[readable_collection_id],
        back_populates="source_connections",
        lazy="noload",
        primaryjoin="SourceConnection.readable_collection_id == Collection.readable_id",
    )
    connection: Mapped[Optional["Connection"]] = relationship(
        "Connection",
        back_populates="source_connection",
        lazy="noload",
        cascade="all, delete-orphan",
        single_parent=True,
    )
