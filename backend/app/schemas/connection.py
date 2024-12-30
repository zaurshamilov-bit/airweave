"""Connection schemas."""

from enum import Enum
from typing import Optional
from uuid import UUID

from pydantic import BaseModel

from app.models.integration_credential import IntegrationType
from app.core.shared_models import ConnectionStatus


class ConnectionBase(BaseModel):
    """Base schema for connections."""

    name: str
    integration_type: IntegrationType
    integration_credential_id: UUID
    status: ConnectionStatus


class ConnectionCreate(ConnectionBase):
    """Schema for creating a connection."""

    source_id: Optional[UUID] = None
    destination_id: Optional[UUID] = None
    embedding_model_id: Optional[UUID] = None


class ConnectionUpdate(BaseModel):
    """Schema for updating a connection."""

    name: Optional[str] = None
    status: Optional[ConnectionStatus] = None


class ConnectionInDBBase(ConnectionBase):
    """Base schema for connection in DB."""

    id: UUID
    organization_id: UUID

    created_by_email: str
    modified_by_email: str
    source_id: Optional[UUID] = None
    destination_id: Optional[UUID] = None
    embedding_model_id: Optional[UUID] = None

    class Config:
        """Pydantic configuration."""

        from_attributes = True


class Connection(ConnectionInDBBase):
    """Schema for connection with config fields."""

    destination_id: Optional[UUID] = None
    source_id: Optional[UUID] = None
    embedding_model_id: Optional[UUID] = None


class DestinationConnection(ConnectionBase):
    """Schema for destination connection."""

    id: UUID
    organization_id: UUID
    created_by_email: str
    modified_by_email: str
    destination_id: UUID


class SourceConnection(ConnectionBase):
    """Schema for source connection."""

    id: UUID
    organization_id: UUID
    created_by_email: str
    modified_by_email: str
    source_id: UUID


class EmbeddingModelConnection(ConnectionBase):
    """Schema for embedding model connection."""

    id: UUID
    organization_id: UUID
    created_by_email: str
    modified_by_email: str
    embedding_model_id: UUID
