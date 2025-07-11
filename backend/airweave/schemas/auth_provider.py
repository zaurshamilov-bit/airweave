"""Auth provider schemas."""

from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field

from airweave.platform.auth.schemas import AuthType
from airweave.schemas.source_connection import ConfigValues


class AuthProviderBase(BaseModel):
    """Base schema for auth providers."""

    name: str = Field(
        ...,
        min_length=1,
        max_length=255,
        description="Human-readable name of the auth provider (e.g., 'Google OAuth', 'GitHub')",
    )
    short_name: str = Field(
        ...,
        min_length=1,
        max_length=100,
        description="Technical identifier used internally to reference this auth provider. "
        "Must be unique.",
    )
    class_name: str = Field(
        ...,
        description="Python class name of the auth provider implementation",
    )
    auth_config_class: str = Field(
        ...,
        description="Python class name that defines the authentication configuration fields",
    )
    config_class: str = Field(
        ...,
        description="Python class name that defines the auth provider-specific configuration",
    )
    auth_type: AuthType = Field(
        ...,
        description="Type of authentication mechanism used by this provider",
    )
    description: Optional[str] = Field(
        None,
        max_length=1000,
        description="Detailed description explaining what this auth provider offers",
    )
    organization_id: Optional[UUID] = Field(
        None,
        description="Organization identifier for custom auth providers. System providers have "
        "this set to null.",
    )

    class Config:
        """Pydantic configuration."""

        from_attributes = True


class AuthProviderCreate(AuthProviderBase):
    """Schema for creating an auth provider."""

    pass


class AuthProviderUpdate(BaseModel):
    """Schema for updating an auth provider."""

    name: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = Field(None, max_length=1000)

    class Config:
        """Pydantic configuration."""

        from_attributes = True


class AuthProviderInDBBase(AuthProviderBase):
    """Base schema for auth provider in DB."""

    id: UUID
    created_at: datetime
    modified_at: datetime

    class Config:
        """Pydantic configuration."""

        from_attributes = True


class AuthProvider(AuthProviderInDBBase):
    """Schema for auth provider response."""

    pass


# Auth Provider Connection Schemas


class AuthProviderConnectionCreate(BaseModel):
    """Schema for creating an auth provider connection with credentials."""

    name: str = Field(
        ...,
        min_length=1,
        max_length=255,
        description="Human-readable name for this auth provider connection",
    )
    description: Optional[str] = Field(
        None,
        description="Optional detailed description of what this auth provider connection provides.",
    )
    short_name: str = Field(
        ...,
        description=("Technical identifier of the auth provider"),
    )
    auth_fields: Optional[ConfigValues] = Field(
        None,
        description=(
            "Authentication credentials required to access the auth provider. The required fields "
            "vary by auth provider type."
        ),
    )
    config_fields: Optional[ConfigValues] = Field(
        None,
        description=(
            "Auth provider-specific configuration parameters required for data extraction. "
            "These vary by auth provider type."
        ),
    )

    class Config:
        """Pydantic configuration."""

        json_schema_extra = {
            "example": {
                "name": "My Composio Connection",
                "short_name": "composio",
                "description": "My Composio Connection",
                "auth_fields": {"api_key": "comp_1234567890abcdef"},
                "config_fields": {"environment": "production", "timeout": 30},
            }
        }


class AuthProviderConnection(BaseModel):
    """Schema for auth provider connection response."""

    id: UUID
    name: str
    short_name: str
    description: Optional[str] = Field(None, description="Description of the connection")
    config_fields: Optional[ConfigValues] = Field(
        None, description="Configuration fields for the connection"
    )
    status: str = Field(description="Connection status (ACTIVE, INACTIVE, ERROR)")
    created_at: datetime
    modified_at: datetime

    class Config:
        """Pydantic configuration."""

        from_attributes = True
