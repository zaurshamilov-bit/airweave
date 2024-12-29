"""Integration credential model."""

from enum import Enum
from typing import TYPE_CHECKING

from sqlalchemy import String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models._base import OrganizationBase, UserMixin
from app.platform.auth.schemas import AuthType

if TYPE_CHECKING:
    pass

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
    auth_type: Mapped[AuthType] = mapped_column(String, nullable=False)
    encrypted_credentials: Mapped[str] = mapped_column(Text, nullable=False)
    auth_config_class: Mapped[str | None] = mapped_column(String, nullable=True)
