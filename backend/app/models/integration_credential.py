"""Integration credential model."""

from enum import Enum
from typing import Optional
from uuid import UUID

from sqlalchemy import JSON, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models._base import OrganizationBase, UserMixin


class IntegrationType(str, Enum):
    """Integration type enum."""

    SOURCE = "source"
    DESTINATION = "destination"
    EMBEDDING_MODEL = "embedding_model"


class IntegrationCredential(OrganizationBase, UserMixin):
    """Integration credential model."""

    __tablename__ = "integration_credential"

    name: Mapped[str] = mapped_column(String, nullable=False)
    integration_short_name: Mapped[str] = mapped_column(String, nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    integration_type: Mapped[IntegrationType] = mapped_column(String, nullable=False)
    auth_credential_type: Mapped[String] = mapped_column(
        String, nullable=False
    )  # TokenCredential, URLAndAPIKeyCredential, etc.
    encrypted_credentials: Mapped[dict] = mapped_column(JSON, nullable=False)
    auth_config_class: Mapped[str] = mapped_column(String, nullable=False)


    # Foreign keys
    source_id: Mapped[Optional[UUID]] = mapped_column(ForeignKey("source.id"), nullable=True)
    destination_id: Mapped[Optional[UUID]] = mapped_column(
        ForeignKey("destination.id"), nullable=True
    )
    embedding_model_id: Mapped[Optional[UUID]] = mapped_column(
        ForeignKey("embedding_model.id"), nullable=True
    )


    def __init__(self, **kwargs):
        """Initialize the integration credential."""
        super().__init__(**kwargs)
        # Ensure only one foreign key is set based on credential_type
        if self.integration_type == IntegrationType.SOURCE:
            self.destination_id = None
            self.embedding_model_id = None
        elif self.integration_type == IntegrationType.DESTINATION:
            self.source_id = None
            self.embedding_model_id = None
        elif self.integration_type == IntegrationType.EMBEDDING_MODEL:
            self.source_id = None
            self.destination_id = None
