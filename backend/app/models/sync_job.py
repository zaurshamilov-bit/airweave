"""Sync job model."""

from datetime import datetime
from typing import TYPE_CHECKING, Optional
from uuid import UUID

from sqlalchemy import DateTime, ForeignKey, Integer, String
from sqlalchemy import Enum as SQLAlchemyEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.shared_models import SyncJobStatus
from app.models._base import OrganizationBase, UserMixin

if TYPE_CHECKING:
    from app.models.chunk import Chunk
    from app.models.sync import Sync


class SyncJob(OrganizationBase, UserMixin):
    """Sync job model."""

    __tablename__ = "sync_job"

    sync_id: Mapped[UUID] = mapped_column(ForeignKey("sync.id", ondelete="CASCADE"), nullable=False)
    status: Mapped[SyncJobStatus] = mapped_column(
        SQLAlchemyEnum(SyncJobStatus), default=SyncJobStatus.PENDING
    )
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    failed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    chunks_detected: Mapped[int] = mapped_column(Integer, default=0)
    chunks_inserted: Mapped[int] = mapped_column(Integer, default=0)
    chunks_deleted: Mapped[int] = mapped_column(Integer, default=0)
    chunks_skipped: Mapped[int] = mapped_column(Integer, default=0)
    error: Mapped[Optional[str]] = mapped_column(String, nullable=True)

    sync: Mapped["Sync"] = relationship(
        "Sync",
        back_populates="jobs",
        lazy="noload",
    )

    chunks: Mapped[list["Chunk"]] = relationship(
        "Chunk",
        back_populates="sync_job",
        lazy="noload",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
