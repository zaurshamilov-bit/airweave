"""Clean source connection schemas with automatic auth method inference."""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, Optional
from uuid import UUID

from pydantic import BaseModel, Field, model_validator

from airweave.core.shared_models import SourceConnectionStatus, SyncJobStatus


class AuthenticationMethod(str, Enum):
    """Authentication methods for source connections."""

    DIRECT = "direct"
    OAUTH_BROWSER = "oauth_browser"
    OAUTH_TOKEN = "oauth_token"
    OAUTH_BYOC = "oauth_byoc"
    AUTH_PROVIDER = "auth_provider"


class OAuthType(str, Enum):
    """OAuth token types for sources."""

    ACCESS_ONLY = "access_only"  # Just access token, no refresh
    WITH_REFRESH = "with_refresh"  # Access + refresh token
    WITH_ROTATING_REFRESH = "with_rotating_refresh"  # Refresh token rotates on use


# ===========================
# Schedule Configuration
# ===========================


class ScheduleConfig(BaseModel):
    """Schedule configuration for syncs."""

    cron: Optional[str] = Field(None, description="Cron expression for scheduled syncs")
    continuous: bool = Field(False, description="Enable continuous sync mode")
    cursor_field: Optional[str] = Field(None, description="Field for incremental sync")


# ===========================
# Input Schema - Single unified create with smart inference
# ===========================


class SourceConnectionCreate(BaseModel):
    """Unified creation schema with automatic auth method inference.

    The authentication method is automatically determined based on which fields are provided:
    - If `credentials` is provided -> DIRECT auth
    - If `access_token` is provided -> OAUTH_TOKEN
    - If `client_id` and `client_secret` are provided -> OAUTH_BYOC
    - If `provider_id` is provided -> AUTH_PROVIDER
    - Otherwise -> OAUTH_BROWSER (default OAuth flow)
    """

    # Required fields
    name: str = Field(..., min_length=4, max_length=42)
    short_name: str = Field(
        ..., description="Source short_name identifier (e.g., 'slack', 'github')"
    )
    readable_collection_id: str = Field(..., description="Collection readable ID")

    # Optional fields
    description: Optional[str] = Field(None, max_length=255)
    config: Optional[Dict[str, Any]] = Field(None, description="Source-specific configuration")
    schedule: Optional[ScheduleConfig] = None
    sync_immediately: bool = Field(True, description="Run initial sync after creation")

    # Auth fields - presence determines method
    # Direct auth
    credentials: Optional[Dict[str, Any]] = Field(
        None, description="Direct auth credentials (API keys, passwords)"
    )

    # OAuth token injection
    access_token: Optional[str] = Field(None, description="Pre-obtained OAuth access token")
    refresh_token: Optional[str] = Field(None, description="OAuth refresh token")
    token_expires_at: Optional[datetime] = Field(None, description="Token expiration time")

    # OAuth BYOC or custom client for browser flow
    client_id: Optional[str] = Field(None, description="OAuth client ID")
    client_secret: Optional[str] = Field(None, description="OAuth client secret")

    # OAuth browser flow
    redirect_url: Optional[str] = Field(None, description="OAuth callback redirect URL")

    # External auth provider
    provider_id: Optional[str] = Field(None, description="Auth provider connection ID")
    provider_config: Optional[Dict[str, Any]] = Field(None, description="Provider-specific config")

    # Computed field - not provided by user
    _auth_method: Optional[AuthenticationMethod] = None

    @model_validator(mode="after")
    def infer_auth_method(self):
        """Automatically determine authentication method from provided fields."""
        # Priority order for inference:
        # 1. Direct credentials
        if self.credentials:
            self._auth_method = AuthenticationMethod.DIRECT

        # 2. OAuth token injection
        elif self.access_token:
            self._auth_method = AuthenticationMethod.OAUTH_TOKEN

        # 3. OAuth BYOC (requires both client credentials)
        elif self.client_id and self.client_secret:
            self._auth_method = AuthenticationMethod.OAUTH_BYOC

        # 4. External auth provider
        elif self.provider_id:
            self._auth_method = AuthenticationMethod.AUTH_PROVIDER

        # 5. Default to OAuth browser flow
        else:
            self._auth_method = AuthenticationMethod.OAUTH_BROWSER

        return self

    @model_validator(mode="after")
    def validate_auth_fields(self):
        """Validate that required fields are present for the inferred auth method."""
        if self._auth_method == AuthenticationMethod.DIRECT:
            if not self.credentials:
                raise ValueError("Direct authentication requires credentials")

        elif self._auth_method == AuthenticationMethod.OAUTH_TOKEN:
            if not self.access_token:
                raise ValueError("OAuth token authentication requires access_token")
            # Validate token not expired if expiry provided
            if self.token_expires_at and self.token_expires_at < datetime.utcnow():
                raise ValueError("Token has already expired")

        elif self._auth_method == AuthenticationMethod.OAUTH_BYOC:
            if not self.client_id or not self.client_secret:
                raise ValueError("BYOC OAuth requires both client_id and client_secret")

        elif self._auth_method == AuthenticationMethod.AUTH_PROVIDER:
            if not self.provider_id:
                raise ValueError("Auth provider authentication requires provider_id")

        # OAuth browser has no required fields (redirect_url is optional)

        return self

    @property
    def auth_method(self) -> AuthenticationMethod:
        """Get the inferred authentication method."""
        if self._auth_method is None:
            # This should not happen after validation, but provide fallback
            self.infer_auth_method()
        return self._auth_method


class SourceConnectionUpdate(BaseModel):
    """Update schema for source connections."""

    name: Optional[str] = Field(None, min_length=4, max_length=42)
    description: Optional[str] = Field(None, max_length=255)
    config: Optional[Dict[str, Any]] = Field(None, description="Source-specific configuration")
    schedule: Optional[ScheduleConfig] = None

    # Re-authentication only for direct auth
    credentials: Optional[Dict[str, Any]] = Field(
        None, description="Update credentials (direct auth only)"
    )

    @model_validator(mode="after")
    def validate_minimal_change(self):
        """Ensure at least one field is being updated."""
        if not any([self.name, self.description, self.config, self.schedule, self.credentials]):
            raise ValueError("At least one field must be provided for update")
        return self


class SourceConnectionValidate(BaseModel):
    """Schema for validating source connection credentials."""

    short_name: str = Field(..., description="Source short_name identifier")
    config: Optional[Dict[str, Any]] = Field(None, description="Source-specific configuration")

    # Auth fields - same inference logic as create
    credentials: Optional[Dict[str, Any]] = None
    access_token: Optional[str] = None

    # Computed field
    _auth_method: Optional[AuthenticationMethod] = None

    @model_validator(mode="after")
    def infer_auth_method(self):
        """Determine auth method for validation."""
        if self.credentials:
            self._auth_method = AuthenticationMethod.DIRECT
        elif self.access_token:
            self._auth_method = AuthenticationMethod.OAUTH_TOKEN
        else:
            raise ValueError("Either credentials or access_token must be provided for validation")
        return self

    @property
    def auth_method(self) -> AuthenticationMethod:
        """Get the inferred authentication method."""
        return self._auth_method


# ===========================
# Output Schemas
# ===========================


class SyncSummary(BaseModel):
    """Sync summary for list views."""

    last_run: Optional[datetime] = None
    next_run: Optional[datetime] = None
    success_rate: Optional[float] = None


class SourceConnectionListItem(BaseModel):
    """Minimal source connection for list views."""

    id: UUID
    name: str
    short_name: str
    readable_collection_id: str
    status: SourceConnectionStatus
    auth_method: AuthenticationMethod
    created_at: datetime
    modified_at: datetime

    # Summary fields
    last_sync: Optional[SyncSummary] = None
    entity_count: int = 0


class AuthenticationDetails(BaseModel):
    """Authentication information."""

    method: AuthenticationMethod
    authenticated: bool
    authenticated_at: Optional[datetime] = None
    expires_at: Optional[datetime] = None

    # OAuth-specific
    auth_url: Optional[str] = Field(None, description="For pending OAuth flows")
    auth_url_expires: Optional[datetime] = None
    redirect_url: Optional[str] = None

    # Provider-specific
    provider_name: Optional[str] = None
    provider_id: Optional[str] = None


class ScheduleDetails(BaseModel):
    """Schedule information."""

    cron: Optional[str] = None
    next_run: Optional[datetime] = None
    continuous: bool = False
    cursor_field: Optional[str] = None
    cursor_value: Optional[Any] = None


class SyncJobDetails(BaseModel):
    """Sync job details."""

    id: UUID
    status: SyncJobStatus
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    duration_seconds: Optional[float] = None
    entities_processed: int = 0
    entities_inserted: int = 0
    entities_updated: int = 0
    entities_deleted: int = 0
    entities_failed: int = 0
    error: Optional[str] = None


class SyncDetails(BaseModel):
    """Sync execution details."""

    total_runs: int = 0
    successful_runs: int = 0
    failed_runs: int = 0
    last_job: Optional[SyncJobDetails] = None


class EntityTypeStats(BaseModel):
    """Statistics for a specific entity type."""

    count: int
    last_updated: Optional[datetime] = None


class EntitySummary(BaseModel):
    """Entity state summary."""

    total_entities: int = 0
    by_type: Dict[str, EntityTypeStats] = Field(default_factory=dict)
    last_updated: Optional[datetime] = None


class SourceConnection(BaseModel):
    """Complete source connection details."""

    id: UUID
    name: str
    description: Optional[str]
    short_name: str
    readable_collection_id: str
    status: SourceConnectionStatus
    created_at: datetime
    modified_at: datetime

    # Authentication
    auth: AuthenticationDetails

    # Configuration
    config: Optional[Dict[str, Any]] = None
    schedule: Optional[ScheduleDetails] = None

    # Sync information
    sync: Optional[SyncDetails] = None

    # Entity information
    entities: Optional[EntitySummary] = None


class SourceConnectionJob(BaseModel):
    """Individual sync job for a source connection."""

    id: UUID
    source_connection_id: UUID
    status: SyncJobStatus
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    duration_seconds: Optional[float] = None

    # Metrics
    entities_processed: int = 0
    entities_inserted: int = 0
    entities_updated: int = 0
    entities_deleted: int = 0
    entities_failed: int = 0

    # Error info
    error: Optional[str] = None
    error_details: Optional[Dict[str, Any]] = None
