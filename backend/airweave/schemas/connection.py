"""Connection schemas.

This is a system table that contains the connection information for all integrations.
Not to be confused with the source connection model, which is a user-facing model that
encompasses the connection and sync information for a specific source.

"""

from typing import Any, Dict, Optional
from uuid import UUID

from pydantic import BaseModel, EmailStr

from airweave.core.shared_models import ConnectionStatus, IntegrationType


class ConnectionBase(BaseModel):
    """Base schema for connections."""

    name: str
    description: Optional[str] = None
    config_fields: Optional[Dict[str, Any]] = None
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
    description: Optional[str] = None
    config_fields: Optional[Dict[str, Any]] = None
    status: Optional[ConnectionStatus] = None


class ConnectionInDBBase(ConnectionBase):
    """Base schema for connection in DB."""

    id: UUID
    organization_id: Optional[UUID] = None
    created_by_email: Optional[EmailStr] = None
    modified_by_email: Optional[EmailStr] = None

    class Config:
        """Pydantic configuration."""

        from_attributes = True


class Connection(ConnectionInDBBase):
    """Schema for connection with config fields."""
