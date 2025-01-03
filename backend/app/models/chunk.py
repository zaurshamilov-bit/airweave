"""Chunk model."""
from uuid import UUID

from sqlalchemy import ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models._base import OrganizationBase


class Chunk(OrganizationBase):
    """Chunk model."""

    __tablename__ = "chunk"

    sync_job_id: Mapped[UUID] = mapped_column(ForeignKey("sync_job.id"), nullable=False)
    sync_id: Mapped[UUID] = mapped_column(ForeignKey("sync.id"), nullable=False)
    entity_id: Mapped[str] = mapped_column(String, nullable=False)
    hash: Mapped[str] = mapped_column(String, nullable=False)

    __table_args__ = (
        UniqueConstraint(
            "sync_id",
            "entity_id",
            name="uq_sync_id_entity_id",
        ),
    )
