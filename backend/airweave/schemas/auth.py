"""Authentication context schemas."""

from typing import Any, Dict, Optional
from uuid import UUID

from pydantic import BaseModel

from .user import User


class AuthContext(BaseModel):
    """Unified authentication context for all auth methods."""

    organization_id: UUID
    user: Optional[User] = None
    auth_method: str  # "auth0", "api_key", "system"

    # Auth method specific metadata
    auth_metadata: Optional[Dict[str, Any]] = None

    @property
    def has_user_context(self) -> bool:
        """Whether this context has user info for tracking."""
        return self.user is not None

    @property
    def tracking_email(self) -> Optional[str]:
        """Email to use for UserMixin tracking."""
        return self.user.email if self.user else None

    @property
    def user_id(self) -> Optional[UUID]:
        """User ID if available."""
        return self.user.id if self.user else None

    @property
    def is_api_key_auth(self) -> bool:
        """Whether this is API key authentication."""
        return self.auth_method == "api_key"

    @property
    def is_user_auth(self) -> bool:
        """Whether this is user authentication (Auth0)."""
        return self.auth_method == "auth0"

    def __str__(self) -> str:
        """String representation for logging."""
        if self.user:
            return f"AuthContext(method={self.auth_method}, user={self.user.email}, org={self.organization_id})"
        else:
            return f"AuthContext(method={self.auth_method}, org={self.organization_id})"
