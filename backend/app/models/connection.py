"""Connection model."""

from typing import Optional
from uuid import UUID

from sqlalchemy import Enum as SQLAlchemyEnum
from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models._base import OrganizationBase, UserMixin
from app.models.integration_credential import IntegrationType
from app.core.shared_models import ConnectionStatus


class Connection(OrganizationBase, UserMixin):
    """Connection model to manage relationships between integrations and their credentials."""

    __tablename__ = "connection"

    name: Mapped[str] = mapped_column(String, nullable=False)
    integration_type: Mapped[IntegrationType] = mapped_column(
        SQLAlchemyEnum(IntegrationType), nullable=False
    )
    status: Mapped[ConnectionStatus] = mapped_column(
        SQLAlchemyEnum(ConnectionStatus), default=ConnectionStatus.ACTIVE
    )

    # Foreign keys
    integration_credential_id: Mapped[UUID] = mapped_column(
        ForeignKey("integration_credential.id"), nullable=False
    )
    source_id: Mapped[Optional[UUID]] = mapped_column(ForeignKey("source.id"), nullable=True)
    destination_id: Mapped[Optional[UUID]] = mapped_column(
        ForeignKey("destination.id"), nullable=True
    )
    embedding_model_id: Mapped[Optional[UUID]] = mapped_column(
        ForeignKey("embedding_model.id"), nullable=True
    )

    def __init__(self, **kwargs):
        """Initialize the connection ensuring only one integration type is set."""
        super().__init__(**kwargs)
        if not self.source_id and not self.destination_id and not self.embedding_model_id:
            raise ValueError("At least one integration type must be set.")

        if self.integration_type == IntegrationType.SOURCE:
            self.destination_id = None
            self.embedding_model_id = None
        elif self.integration_type == IntegrationType.DESTINATION:
            self.source_id = None
            self.embedding_model_id = None
        elif self.integration_type == IntegrationType.EMBEDDING_MODEL:
            self.source_id = None
            self.destination_id = None
