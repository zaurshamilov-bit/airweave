"""Source connection model."""

from typing import TYPE_CHECKING, Optional
from uuid import UUID

from sqlalchemy import JSON, ForeignKey, String, Text
from sqlalchemy import Enum as SQLAlchemyEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from airweave.core.shared_models import SourceConnectionStatus
from airweave.models._base import OrganizationBase, UserMixin

if TYPE_CHECKING:
    from airweave.models.collection import Collection
    from airweave.models.dag import SyncDag
    from airweave.models.integration_credential import IntegrationCredential
    from airweave.models.sync import Sync


class SourceConnection(OrganizationBase, UserMixin):
    """Source connection model for connecting to external data sources."""

    __tablename__ = "source_connection"

    name: Mapped[str] = mapped_column(String, nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    short_name: Mapped[str] = mapped_column(String, nullable=False)  # Source short name

    # Configuration fields for the source connection
    config_fields: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)

    # Related objects
    dag_id: Mapped[Optional[UUID]] = mapped_column(
        ForeignKey("sync_dag.id", ondelete="SET NULL"), nullable=True
    )
    sync_id: Mapped[Optional[UUID]] = mapped_column(
        ForeignKey("sync.id", ondelete="SET NULL"), nullable=True
    )
    integration_credential_id: Mapped[Optional[UUID]] = mapped_column(
        ForeignKey("integration_credential.id", ondelete="SET NULL"), nullable=True
    )
    readable_collection_id: Mapped[Optional[UUID]] = mapped_column(
        ForeignKey("collection.readable_id", ondelete="SET NULL"), nullable=True
    )
    status: Mapped[SourceConnectionStatus] = mapped_column(
        SQLAlchemyEnum(SourceConnectionStatus), default=SourceConnectionStatus.ACTIVE
    )
    cron_schedule: Mapped[Optional[str]] = mapped_column(String, nullable=True)

    # Relationships
    sync: Mapped[Optional["Sync"]] = relationship(
        "Sync", back_populates="source_connection", lazy="noload"
    )
    integration_credential: Mapped[Optional["IntegrationCredential"]] = relationship(
        "IntegrationCredential", foreign_keys=[integration_credential_id], lazy="noload"
    )
    dag: Mapped[Optional["SyncDag"]] = relationship("SyncDag", foreign_keys=[dag_id], lazy="noload")
    collection: Mapped[Optional["Collection"]] = relationship(
        "Collection", foreign_keys=[readable_collection_id], lazy="noload"
    )
