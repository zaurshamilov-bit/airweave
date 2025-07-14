"""White label schema."""

from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field


class WhiteLabelBase(BaseModel):
    """Base schema for WhiteLabel."""

    name: str = Field(
        ...,
        description=(
            "Human-readable name for the white label integration. This helps you identify the "
            "integration in the UI and should clearly describe its purpose (e.g., 'Customer "
            "Portal Slack Integration', 'Enterprise Google Drive Access')."
        ),
        min_length=1,
        max_length=64,
        examples=[
            "Customer Portal Slack Integration",
            "Enterprise Google Drive Access",
            "Support Team GitHub Integration",
        ],
    )
    source_short_name: str = Field(
        ...,
        description=(
            "Technical identifier of the source type that this integration supports "
            "(e.g., 'slack', 'google_drive', 'github'). This determines which service provider "
            "the OAuth integration connects to."
        ),
        examples=["slack", "google_drive", "github"],
    )
    redirect_url: str = Field(
        ...,
        description=(
            "OAuth2 callback URL where users are redirected after completing authentication. "
            "This must be a valid HTTPS URL that your application can handle to receive the "
            "authorization code."
        ),
        examples=["https://yourapp.com/auth/callback", "https://api.company.com/oauth/complete"],
    )
    client_id: str = Field(
        ...,
        description=(
            "OAuth2 client identifier provided by the service provider. This identifies your "
            "application during the OAuth consent flow and must match the client ID configured "
            "in the service provider's developer console."
        ),
        examples=["1234567890.1234567890987", "GOCSPX-abcdef1234567890"],
    )
    client_secret: str = Field(
        ...,
        description=(
            "OAuth2 client secret from your registered application. This is used to securely "
            "authenticate your application when exchanging authorization codes for access tokens. "
            "Keep this value secure and never expose it in client-side code."
        ),
        examples=[
            "abcdefghijklmnopqrstuvwxyz123456",
            "GOCSPX-your-oauth-secret-here",
            "1234567890abcdef1234567890abcdef12345678",
        ],
    )
    allowed_origins: str = Field(
        ...,
        description=(
            "Comma-separated list of allowed domains for OAuth flows and CORS. This prevents "
            "unauthorized websites from using your OAuth credentials and should include all "
            "domains where your application is hosted."
        ),
        examples=["https://yourapp.com,https://api.yourapp.com", "https://company.com"],
    )

    class Config:
        """Pydantic config for WhiteLabelBase."""

        from_attributes = True


class WhiteLabelCreate(WhiteLabelBase):
    """Schema for creating a WhiteLabel object."""

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "name": "Customer Portal Slack Integration",
                    "source_short_name": "slack",
                    "redirect_url": "https://yourapp.com/auth/slack/callback",
                    "client_id": "1234567890.1234567890123",
                    "client_secret": "abcdefghijklmnopqrstuvwxyz123456",
                    "allowed_origins": "https://yourapp.com,https://app.yourapp.com",
                },
            ]
        }
    }


class WhiteLabelUpdate(BaseModel):
    """Schema for updating a WhiteLabel object."""

    name: Optional[str] = Field(
        None,
        description="Updated name for the white label integration.",
        min_length=4,
        max_length=100,
        examples=["Updated Customer Portal Integration", "Revised Enterprise Access"],
    )
    redirect_url: Optional[str] = Field(
        None,
        description=(
            "Updated OAuth callback URL. Must be a valid HTTPS URL that matches your "
            "OAuth application configuration."
        ),
        examples=["https://newdomain.com/auth/callback", "https://v2.yourapp.com/oauth/complete"],
    )
    client_id: Optional[str] = Field(
        None,
        description=(
            "Updated OAuth2 client ID. Must match the client ID in your service provider's "
            "developer console."
        ),
        examples=["9876543210.9876543210987", "updated-client-id-here"],
    )
    client_secret: Optional[str] = Field(
        None,
        description=(
            "Updated OAuth2 client secret. This will replace the existing secret and affect "
            "all future OAuth flows."
        ),
        examples=["new-secret-key-abcdef123456", "GOCSPX-updated-oauth-secret"],
    )
    allowed_origins: Optional[str] = Field(
        None,
        description="Updated comma-separated list of allowed domains for OAuth flows.",
        examples=["https://newapp.com,https://api.newapp.com", "https://updated-domain.com"],
    )

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "name": "Updated Customer Portal Integration",
                    "redirect_url": "https://v2.yourapp.com/auth/slack/callback",
                    "allowed_origins": "https://v2.yourapp.com,https://api.yourapp.com",
                },
            ]
        }
    }


class WhiteLabelInDBBase(WhiteLabelBase):
    """Base schema for WhiteLabel stored in DB."""

    id: UUID = Field(
        ...,
        description=(
            "Unique system identifier for the white label integration. This UUID is generated "
            "automatically and used for API operations and OAuth flow tracking."
        ),
    )
    organization_id: UUID = Field(
        ...,
        description=(
            "Identifier of the organization that owns this white label integration. "
            "White label integrations are isolated per organization for security and multi-tenancy."
        ),
    )
    created_at: datetime = Field(
        ...,
        description="Timestamp when the white label integration was created (ISO 8601 format).",
    )
    modified_at: datetime = Field(
        ...,
        description=(
            "Timestamp when the white label integration was last modified (ISO 8601 format)."
        ),
    )
    created_by_email: Optional[EmailStr] = Field(
        None,
        description="Email address of the user who created this white label integration.",
    )
    modified_by_email: Optional[EmailStr] = Field(
        None,
        description="Email address of the user who last modified this white label integration.",
    )

    class Config:
        """Pydantic config for WhiteLabelInDBBase."""

        from_attributes = True


class WhiteLabel(WhiteLabelInDBBase):
    """Complete white label integration representation returned by the API."""

    model_config = {
        "from_attributes": True,
        "json_schema_extra": {
            "examples": [
                {
                    "id": "white123-4567-89ab-cdef-012345678901",
                    "name": "Customer Portal Slack Integration",
                    "source_short_name": "slack",
                    "redirect_url": "https://yourapp.com/auth/slack/callback",
                    "client_id": "1234567890.1234567890123",
                    "client_secret": "abcdefghijklmnopqrstuvwxyz123456",
                    "allowed_origins": "https://yourapp.com,https://app.yourapp.com",
                    "organization_id": "org12345-6789-abcd-ef01-234567890abc",
                    "created_at": "2024-01-10T08:15:00Z",
                    "modified_at": "2024-01-15T09:30:00Z",
                    "created_by_email": "admin@company.com",
                    "modified_by_email": "devops@company.com",
                },
            ]
        },
    }
