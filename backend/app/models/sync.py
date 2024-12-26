"""Sync model."""

from typing import Optional
from uuid import UUID

from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models._base import OrganizationBase, UserMixin


class Sync(OrganizationBase, UserMixin):
    """Sync model."""

    __tablename__ = "sync"

    name: Mapped[str] = mapped_column(String, nullable=False)
    schedule: Mapped[str] = mapped_column(String(100), nullable=False)
    source_integration_credential_id: Mapped[UUID] = mapped_column(
        ForeignKey("integration_credential.id"), nullable=False
    )
    destination_integration_credential_id: Mapped[Optional[UUID]] = mapped_column(
        ForeignKey("integration_credential.id"), nullable=True
    )
    embedding_model_integration_credential_id: Mapped[Optional[UUID]] = mapped_column(
        ForeignKey("integration_credential.id"), nullable=True
    )
