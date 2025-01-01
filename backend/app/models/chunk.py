"""Chunk model."""
from uuid import UUID

from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models._base import OrganizationBase


class Chunk(OrganizationBase):
    """Chunk model."""

    __tablename__ = "chunk"

    sync_job_id: Mapped[UUID] = mapped_column(ForeignKey("sync_job.id"), nullable=False)
    sync_id: Mapped[UUID] = mapped_column(ForeignKey("sync.id"), nullable=False)
    entity_id: Mapped[str] = mapped_column(String, nullable=False)
    hash: Mapped[str] = mapped_column(String, nullable=False)
