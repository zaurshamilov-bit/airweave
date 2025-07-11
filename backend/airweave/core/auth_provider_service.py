"""Service for managing auth provider operations."""

from typing import Any, Dict, Optional, Union

from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from airweave import crud, schemas
from airweave.core import credentials
from airweave.core.logging import logger
from airweave.core.shared_models import IntegrationType
from airweave.platform.locator import resource_locator
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

    async def _validate_auth_provider_config(
        self,
        db: AsyncSession,
        auth_provider_short_name: str,
        auth_provider_config: Optional[Dict[str, Any]],
    ) -> dict:
        """Validate auth provider config fields based on auth provider config class.

        Args:
            db: The database session
            auth_provider_short_name: The short name of the auth provider
            auth_provider_config: The auth provider config fields to validate

        Returns:
            The validated auth provider config fields as a dict

        Raises:
            HTTPException: If config fields are invalid or required but not provided
        """
        # Get the auth provider info
        auth_provider = await crud.auth_provider.get_by_short_name(
            db, short_name=auth_provider_short_name
        )
        if not auth_provider:
            raise HTTPException(
                status_code=404, detail=f"Auth provider '{auth_provider_short_name}' not found"
            )

        BASE_ERROR_MESSAGE = (
            "For more information about auth provider configuration, "
            "check [this page](https://docs.airweave.ai/docs/auth-providers)."
        )

        # Check if auth provider has a config class defined - it MUST be defined
        if not hasattr(auth_provider, "config_class") or auth_provider.config_class is None:
            raise HTTPException(
                status_code=422,
                detail=f"Auth provider {auth_provider.name} does not have a "
                "configuration class defined. " + BASE_ERROR_MESSAGE,
            )

        # Config class exists but no config fields provided - check if that's allowed
        if auth_provider_config is None:
            try:
                # Get config class to check if it has required fields
                config_class = resource_locator.get_config(auth_provider.config_class)
                # Create an empty instance to see if it accepts no fields
                config = config_class()
                return config.model_dump()
            except Exception:
                # If it fails with no fields, config is required
                raise HTTPException(
                    status_code=422,
                    detail=f"Auth provider {auth_provider.name} requires config fields "
                    "but none were provided. " + BASE_ERROR_MESSAGE,
                ) from None

        # Both config class and config fields exist, validate them
        try:
            config_class = resource_locator.get_config(auth_provider.config_class)
            config = config_class(**auth_provider_config)
            return config.model_dump()
        except Exception as e:
            auth_provider_logger.error(f"Failed to validate auth provider config fields: {e}")

            # Check if it's a Pydantic validation error and format it nicely
            from pydantic import ValidationError

            if isinstance(e, ValidationError):
                # Extract the field names and error messages
                error_messages = []
                for error in e.errors():
                    field = ".".join(str(loc) for loc in error.get("loc", []))
                    msg = error.get("msg", "")
                    error_messages.append(f"Field '{field}': {msg}")

                error_detail = (
                    f"Invalid configuration for {auth_provider.config_class}:\n"
                    + "\n".join(error_messages)
                )
                raise HTTPException(
                    status_code=422,
                    detail=f"Invalid auth provider config fields: {error_detail}. "
                    + BASE_ERROR_MESSAGE,
                ) from e
            else:
                # For other types of errors
                raise HTTPException(
                    status_code=422,
                    detail=f"Invalid auth provider config fields: {str(e)}. " + BASE_ERROR_MESSAGE,
                ) from e

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

        Creates an auth provider instance with credentials and uses it to get source credentials.

        Args:
            db: The database session
            source_connection_in: The source connection being created
            auth_context: The current authentication context

        Returns:
            Integration credential for the source

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

        # Validate auth provider config fields
        auth_provider_config_dict = None
        if (
            hasattr(source_connection_in, "auth_provider_config")
            and source_connection_in.auth_provider_config
        ):
            # Convert ConfigValues to dict if needed
            if hasattr(source_connection_in.auth_provider_config, "model_dump"):
                auth_provider_config_dict = source_connection_in.auth_provider_config.model_dump()
            else:
                auth_provider_config_dict = source_connection_in.auth_provider_config

        validated_auth_provider_config = await self._validate_auth_provider_config(
            db, auth_provider_short_name, auth_provider_config_dict
        )

        auth_provider_logger.info(
            f"\nValidated auth provider config: {validated_auth_provider_config}\n"
        )

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

        # If there are multiple connections, use the most recent one (by modified_at)
        # TODO: have the option to select a specific connection
        most_recent_connection = max(connections, key=lambda conn: conn.modified_at)

        auth_provider_logger.info(
            f"\nMost recent connection (modified_at: {most_recent_connection.modified_at}): "
            f"{most_recent_connection.name}\n"
        )

        # Get the integration credential for this connection
        if not most_recent_connection.integration_credential_id:
            raise HTTPException(
                status_code=404,
                detail=f"Connection '{most_recent_connection.name}' has no integration credential",
            )

        # Get the integration credential
        integration_credential = await crud.integration_credential.get(
            db, id=most_recent_connection.integration_credential_id, auth_context=auth_context
        )

        if not integration_credential:
            raise HTTPException(
                status_code=404,
                detail=f"Integration credential not found for connection "
                f"'{most_recent_connection.name}'",
            )

        auth_provider_logger.info(
            f"\nRetrieved integration credential: {integration_credential.name}\n"
        )

        # Decrypt the credentials
        decrypted_credentials = credentials.decrypt(integration_credential.encrypted_credentials)

        # Create auth provider instance with credentials and validated config
        auth_provider_class = resource_locator.get_auth_provider(auth_provider)
        auth_provider_instance = await auth_provider_class.create(
            credentials=decrypted_credentials,
            config=validated_auth_provider_config,
        )

        auth_provider_logger.info(
            f"\nCreated auth provider instance: {auth_provider_instance.__class__.__name__}\n"
        )

        source_short_name = source_connection_in.short_name
        auth_provider_logger.info(
            f"\nGetting source credentials from auth provider for source: {source_short_name}\n"
        )

        # Get the required auth fields from the source using the auth config class
        source = await crud.source.get_by_short_name(db, short_name=source_short_name)
        source_auth_config_class = resource_locator.get_auth_config(source.auth_config_class)
        source_auth_config_fields = list(source_auth_config_class.model_fields.keys())
        auth_provider_logger.info(f"\nSource auth config fields: {source_auth_config_fields}\n")

        source_credentials = await auth_provider_instance.get_creds_for_source(
            source_short_name=source_short_name, source_auth_config_fields=source_auth_config_fields
        )
        auth_provider_logger.info(f"\nSource credentials: {source_credentials}\n")

        integration_cred_in = schemas.IntegrationCredentialCreateEncrypted(
            name=f"{source.name} - {auth_context.organization_id}",
            description=f"Credentials for {source.name} - {auth_context.organization_id}",
            integration_short_name=source_short_name,
            integration_type=IntegrationType.SOURCE,
            auth_type=source.auth_type,
            encrypted_credentials=credentials.encrypt(source_credentials),
            auth_config_class=source.auth_config_class,
        )
        integration_credential = await crud.integration_credential.create(
            db, obj_in=integration_cred_in, auth_context=auth_context
        )

        return integration_credential


# Singleton instance
auth_provider_service = AuthProviderService()
