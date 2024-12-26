"""Sync job model."""


from sqlalchemy import UUID, Column, ForeignKey, Integer

from app.models._base import OrganizationBase, UserMixin


class SyncJob(OrganizationBase, UserMixin):
    """Sync job model."""

    __tablename__ = "sync_job"
    chunks_detected = Column(Integer, nullable=False)
    chunks_inserted = Column(Integer, nullable=False)
    chunks_deleted = Column(Integer, nullable=False)
    chunks_skipped = Column(Integer, nullable=False)
    sync_id = Column(UUID, ForeignKey("sync.id"), nullable=False)
