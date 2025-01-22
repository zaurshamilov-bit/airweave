"""Chunk model."""

from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models._base import OrganizationBase

if TYPE_CHECKING:
    from app.models.sync import Sync
    from app.models.sync_job import SyncJob


class Chunk(OrganizationBase):
    """Chunk model."""

    __tablename__ = "chunk"

    sync_job_id: Mapped[UUID] = mapped_column(
        ForeignKey("sync_job.id", ondelete="CASCADE"), nullable=False
    )
    sync_id: Mapped[UUID] = mapped_column(ForeignKey("sync.id", ondelete="CASCADE"), nullable=False)
    entity_id: Mapped[str] = mapped_column(String, nullable=False)
    hash: Mapped[str] = mapped_column(String, nullable=False)

    # Add back references
    sync_job: Mapped["SyncJob"] = relationship(
        "SyncJob",
        back_populates="chunks",
        lazy="noload",
    )

    sync: Mapped["Sync"] = relationship(
        "Sync",
        back_populates="chunks",
        lazy="noload",
    )

    __table_args__ = (
        UniqueConstraint(
            "sync_id",
            "entity_id",
            name="uq_sync_id_entity_id",
        ),
    )
