"""Refactored source connection schemas with cleaner abstractions and explicit auth paths."""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Literal, Optional
from uuid import UUID

from pydantic import BaseModel, Field, model_validator

from airweave.core.shared_models import SourceConnectionStatus, SyncJobStatus
from airweave.platform.configs._base import ConfigValues

# ===========================
# Authentication Enumerations
# ===========================


class AuthenticationMethod(str, Enum):
    """Explicit authentication methods for source connections."""

    DIRECT = "direct"  # Direct credentials (API keys, passwords, etc.)
    OAUTH_BROWSER = "oauth_browser"  # OAuth flow with browser redirect
    OAUTH_TOKEN = "oauth_token"  # Direct OAuth token injection
    OAUTH_BYOC = "oauth_byoc"  # Bring Your Own Client OAuth - MUST if set
    AUTH_PROVIDER = "auth_provider"  # External auth provider (e.g., Composio)


class OAuthType(str, Enum):
    """OAuth token types for sources."""

    ACCESS_ONLY = "access_only"  # Just access token, no refresh
    WITH_REFRESH = "with_refresh"  # Access + refresh token
    WITH_ROTATING_REFRESH = "with_rotating_refresh"  # Refresh token rotates on use


# ===========================
# Nested Response Objects
# ===========================


class LastSyncJob(BaseModel):
    """Nested object for last sync job information."""

    id: Optional[UUID] = None
    status: Optional[SyncJobStatus] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    duration_seconds: Optional[float] = None

    # Entity metrics
    entities_processed: int = 0
    entities_inserted: int = 0
    entities_updated: int = 0
    entities_deleted: int = 0
    entities_failed: int = 0

    # Error information
    error: Optional[str] = None
    error_details: Optional[Dict[str, Any]] = None

    @property
    def success_rate(self) -> Optional[float]:
        """Calculate success rate of entity processing."""
        if self.entities_processed == 0:
            return None
        return (self.entities_processed - self.entities_failed) / self.entities_processed


class Schedule(BaseModel):
    """Nested object for schedule information."""

    cron_expression: Optional[str] = Field(None, description="Cron schedule expression")
    next_run_at: Optional[datetime] = Field(None, description="Next scheduled run time")
    is_continuous: bool = Field(False, description="Whether sync runs continuously")
    cursor_field: Optional[str] = Field(None, description="Field used for incremental sync")
    cursor_value: Optional[Any] = Field(None, description="Current cursor position")


class AuthenticationInfo(BaseModel):
    """Nested object for authentication information (when depth > 0)."""

    method: AuthenticationMethod
    is_authenticated: bool
    authenticated_at: Optional[datetime] = None
    expires_at: Optional[datetime] = None

    # OAuth-specific
    authentication_url: Optional[str] = Field(None, description="URL to complete OAuth flow")
    authentication_url_expiry: Optional[datetime] = None

    # Auth provider specific
    auth_provider_id: Optional[str] = None
    auth_provider_name: Optional[str] = None

    # Redirect URL
    redirect_url: Optional[str] = None


class EntityState(BaseModel):
    """Nested object for entity state information (when depth > 1)."""

    entity_type: str
    total_count: int
    last_updated_at: Optional[datetime]
    sync_status: Literal["pending", "syncing", "synced", "failed"]
    error: Optional[str] = None


# ===========================
# Input Schemas
# ===========================


class SourceConnectionCreate(BaseModel):
    """Unified creation schema with explicit authentication routing."""

    # Required field
    name: str = Field(..., min_length=4, max_length=42)
    short_name: str = Field(..., description="Source type identifier")
    authentication_method: AuthenticationMethod
    collection: str = Field(..., description="Collection readable ID")

    # Optional fields
    description: Optional[str] = Field(None, max_length=255)
    config_fields: Optional[ConfigValues] = None
    cron_schedule: Optional[str] = None
    sync_immediately: bool = Field(True, description="Run initial sync after creation")

    # Authentication fields (exactly one group must be provided based on method)

    # For DIRECT auth
    auth_fields: Optional[ConfigValues] = Field(
        None, description="Direct authentication credentials (for method=direct)"
    )

    # For OAUTH_BROWSER
    redirect_url: Optional[str] = Field(
        None, description="URL to redirect after OAuth completion (for method=oauth_browser)"
    )

    # For OAUTH_TOKEN
    access_token: Optional[str] = Field(
        None,
        description="OAuth access token (for method=oauth_token)",
        json_schema_extra={"writeOnly": True},
    )
    refresh_token: Optional[str] = Field(
        None,
        description="OAuth refresh token (for method=oauth_token)",
        json_schema_extra={"writeOnly": True},
    )
    token_expires_at: Optional[datetime] = Field(
        None, description="Token expiration time (for method=oauth_token)"
    )

    # For OAUTH_BYOC
    client_id: Optional[str] = Field(
        None,
        description="OAuth client ID (for method=oauth_byoc)",
        json_schema_extra={"writeOnly": True},
    )
    client_secret: Optional[str] = Field(
        None,
        description="OAuth client secret (for method=oauth_byoc)",
        json_schema_extra={"writeOnly": True},
    )

    # For AUTH_PROVIDER
    auth_provider: Optional[str] = Field(
        None, description="Auth provider readable ID (for method=auth_provider)"
    )
    auth_provider_config: Optional[ConfigValues] = Field(
        None, description="Auth provider configuration (for method=auth_provider)"
    )

    @model_validator(mode="after")
    def validate_auth_fields_for_method(self):
        """Ensure correct fields are provided for the authentication method."""
        method = self.authentication_method

        if method == AuthenticationMethod.DIRECT:
            if not self.auth_fields:
                raise ValueError("auth_fields required for direct authentication")

        elif method == AuthenticationMethod.OAUTH_BROWSER:
            # redirect_url is optional, will use default if not provided
            pass

        elif method == AuthenticationMethod.OAUTH_TOKEN:
            if not self.access_token:
                raise ValueError("access_token required for oauth_token method")

        elif method == AuthenticationMethod.OAUTH_BYOC:
            if not self.client_id or not self.client_secret:
                raise ValueError("client_id and client_secret required for oauth_byoc method")

        elif method == AuthenticationMethod.AUTH_PROVIDER:
            if not self.auth_provider:
                raise ValueError("auth_provider required for auth_provider method")

        return self


class SourceConnectionUpdate(BaseModel):
    """Update schema for source connections."""

    name: Optional[str] = Field(None, min_length=4, max_length=42)
    description: Optional[str] = Field(None, max_length=255)
    config_fields: Optional[ConfigValues] = None
    cron_schedule: Optional[str] = None

    # Re-authentication (only for certain methods)
    auth_fields: Optional[ConfigValues] = Field(
        None, description="Update authentication credentials (direct auth only)"
    )


class SourceConnectionValidate(BaseModel):
    """Schema for validating source connection credentials."""

    short_name: str
    authentication_method: AuthenticationMethod
    auth_fields: Optional[ConfigValues] = None
    access_token: Optional[str] = Field(None, json_schema_extra={"writeOnly": True})
    config_fields: Optional[ConfigValues] = None


# ===========================
# Output Schemas
# ===========================


class SourceConnectionListItem(BaseModel):
    """Minimal source connection for list views."""

    id: UUID
    name: str
    short_name: str
    collection: str
    status: SourceConnectionStatus
    is_authenticated: bool
    created_at: datetime
    modified_at: datetime

    # Summary fields
    last_sync_at: Optional[datetime] = None
    next_sync_at: Optional[datetime] = None
    entities_count: int = 0


class SourceConnection(BaseModel):
    """Source connection with optional depth expansion."""

    # Core fields (always present)
    id: UUID
    name: str
    description: Optional[str]
    short_name: str
    collection: str
    status: SourceConnectionStatus
    created_at: datetime
    modified_at: datetime

    # Authentication status (always present)
    is_authenticated: bool
    auth_method: Optional[AuthenticationMethod] = Field(
        None, description="Authentication method used"
    )

    # Config (depth 0+)
    config_fields: Optional[ConfigValues] = None

    # Schedule info (depth 0+)
    schedule: Optional[Schedule] = None

    # Last sync job (depth 0+)
    last_sync_job: Optional[LastSyncJob] = None

    # Expanded fields (depth 1+)
    authentication: Optional[AuthenticationInfo] = None

    # Entity states (depth 2+)
    entity_states: Optional[List[EntityState]] = None

    # Never expose these
    model_config = {"exclude": {"sync_id", "connection_id", "credential_id"}}


class SourceConnectionJob(BaseModel):
    """Individual sync job for a source connection."""

    id: UUID
    source_connection_id: UUID
    status: SyncJobStatus
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    duration_seconds: Optional[float] = None

    # Metrics
    entities_processed: Optional[int] = 0
    entities_inserted: Optional[int] = 0
    entities_updated: Optional[int] = 0
    entities_deleted: Optional[int] = 0
    entities_failed: Optional[int] = 0

    # Error info
    error: Optional[str] = None
    error_details: Optional[Dict[str, Any]] = None
