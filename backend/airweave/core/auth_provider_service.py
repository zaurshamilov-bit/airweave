"""Service for managing auth provider operations."""

from typing import Union

from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from airweave import crud
from airweave.core.logging import logger
from airweave.schemas import (
    IntegrationCredential,
    SourceConnectionCreate,
    SourceConnectionCreateWithWhiteLabel,
)
from airweave.schemas.auth import AuthContext

auth_provider_logger = logger.with_prefix("Auth Provider Service: ").with_context(
    component="auth_provider_service"
)


class AuthProviderService:
    """Service for managing auth provider operations."""

    async def get_source_credentials(
        self,
        db: AsyncSession,
        source_connection_in: Union[
            SourceConnectionCreate,
            SourceConnectionCreateWithWhiteLabel,
        ],
        auth_context: AuthContext,
    ) -> IntegrationCredential:
        """Get source credentials from auth provider.

        For now, this does the same validation as validate_and_get_auth_provider_connections
        but will eventually handle credential creation/management.

        Args:
            db: The database session
            source_connection_in: The source connection being created
            auth_context: The current authentication context

        Returns:
            Integration credential (for now, just validates and returns None)

        Raises:
            HTTPException: If the auth provider doesn't exist or has no connections
        """
        auth_provider_short_name = getattr(source_connection_in, "auth_provider", None)
        if not auth_provider_short_name:
            raise HTTPException(
                status_code=400, detail="Auth provider short name not found in source connection"
            )

        auth_provider_logger.info(
            f"\nGetting source credentials from auth provider '{auth_provider_short_name}'\n"
        )

        # 1. Check if auth provider exists
        auth_provider = await crud.auth_provider.get_by_short_name(
            db, short_name=auth_provider_short_name
        )
        if not auth_provider:
            raise HTTPException(
                status_code=404,
                detail=f"Auth provider '{auth_provider_short_name}' not found. "
                "To see which auth providers are supported and learn more about how to use them, "
                "check [this page](https://docs.airweave.ai/docs/auth-providers).",
            )

        auth_provider_logger.info(f"\nFound auth provider: {auth_provider.name}\n")

        # 2. Get all connections for the auth provider for this organization
        connections = await crud.connection.get_all_by_short_name(
            db, auth_provider_short_name, auth_context
        )

        auth_provider_logger.info(
            f"\nFound {len(connections)} connection(s) for auth provider {auth_provider_short_name}"
            f"\n{connections}'\n"
        )

        if not connections:
            raise HTTPException(
                status_code=404,
                detail=f"No connections found for auth provider '{auth_provider_short_name}'",
            )

        # For now, return None - this will be implemented later to create/manage credentials
        auth_provider_logger.info("Credential creation not implemented yet - returning None")
        return None


# Singleton instance
auth_provider_service = AuthProviderService()
