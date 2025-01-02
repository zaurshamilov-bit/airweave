"""Sync model."""

from typing import Optional
from uuid import UUID

from sqlalchemy import ForeignKey, String, UniqueConstraint
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
    cron_schedule: Mapped[str] = mapped_column(String(100), nullable=False)
    white_label_id: Mapped[Optional[UUID]] = mapped_column(
        ForeignKey("white_label.id"), nullable=True
    )
    white_label_user_identifier: Mapped[str] = mapped_column(String(256), nullable=True)


    __table_args__ = (
        UniqueConstraint(
            "white_label_id",
            "white_label_user_identifier",
            name="uq_white_label_user",
        ),
    )
