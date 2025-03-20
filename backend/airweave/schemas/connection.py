"""Connection schemas."""

from typing import Optional
from uuid import UUID

from pydantic import BaseModel

from airweave.core.shared_models import ConnectionStatus, IntegrationType


class ConnectionBase(BaseModel):
    """Base schema for connections."""

    name: str
    integration_type: IntegrationType
    integration_credential_id: Optional[UUID] = None
    status: ConnectionStatus
    short_name: str

    class Config:
        """Pydantic configuration."""

        from_attributes = True


class ConnectionCreate(ConnectionBase):
    """Schema for creating a connection."""


class ConnectionUpdate(BaseModel):
    """Schema for updating a connection."""

    name: Optional[str] = None
    status: Optional[ConnectionStatus] = None


class ConnectionInDBBase(ConnectionBase):
    """Base schema for connection in DB."""

    id: UUID
    organization_id: Optional[UUID] = None
    created_by_email: Optional[str] = None
    modified_by_email: Optional[str] = None

    class Config:
        """Pydantic configuration."""

        from_attributes = True


class Connection(ConnectionInDBBase):
    """Schema for connection with config fields."""
