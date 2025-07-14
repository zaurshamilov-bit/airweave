"""Auth Provider endpoints for managing auth provider connections."""

from typing import Any, Dict, List, Optional

from fastapi import Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from airweave import crud, schemas
from airweave.api import deps
from airweave.api.router import TrailingSlashRouter
from airweave.core import credentials
from airweave.core.logging import logger
from airweave.core.shared_models import ConnectionStatus, IntegrationType
from airweave.db.unit_of_work import UnitOfWork
from airweave.platform.locator import resource_locator
from airweave.schemas.auth import AuthContext

router = TrailingSlashRouter()


async def _validate_auth_fields(
    db: AsyncSession, auth_provider_short_name: str, auth_fields: Optional[Dict[str, Any]]
) -> dict:
    """Validate auth fields based on auth type.

    Args:
        db: The database session
        auth_provider_short_name: The short name of the auth provider
        auth_fields: The auth fields to validate

    Returns:
        The validated auth fields as a dict

    Raises:
        HTTPException: If auth fields are invalid or not supported
    """
    # Get the auth provider info
    auth_provider = await crud.auth_provider.get_by_short_name(
        db, short_name=auth_provider_short_name
    )
    if not auth_provider:
        raise HTTPException(
            status_code=404, detail=f"Auth provider '{auth_provider_short_name}' not found"
        )

    # Check if auth_config_class is defined for the auth provider
    if not auth_provider.auth_config_class:
        raise HTTPException(
            status_code=422,
            detail=f"Auth provider {auth_provider.name} does not have an auth config defined.",
        )

    if auth_fields is None:
        raise HTTPException(
            status_code=422, detail=f"Auth provider {auth_provider.name} requires auth fields."
        )

    # Convert ConfigValues to dict if needed
    if hasattr(auth_fields, "model_dump"):
        auth_fields_dict = auth_fields.model_dump()
    else:
        auth_fields_dict = auth_fields

    # Create and validate auth config
    try:
        auth_config_class = resource_locator.get_auth_config(auth_provider.auth_config_class)
        auth_config = auth_config_class(**auth_fields_dict)
        return auth_config.model_dump()
    except Exception as e:
        logger.error(f"Failed to validate auth fields: {e}")

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
                f"Invalid configuration for {auth_provider.auth_config_class}:\n"
                + "\n".join(error_messages)
            )
            raise HTTPException(
                status_code=422, detail=f"Invalid auth fields: {error_detail}"
            ) from e
        else:
            # For other types of errors
            raise HTTPException(status_code=422, detail=f"Invalid auth fields: {str(e)}") from e


@router.get("/list", response_model=List[schemas.AuthProvider])
async def list_auth_providers(
    *,
    db: AsyncSession = Depends(deps.get_db),
    auth_context: AuthContext = Depends(deps.get_auth_context),
    skip: int = 0,
    limit: int = 100,
) -> List[schemas.AuthProvider]:
    """Get all available auth providers.

    Args:
    -----
        db: The database session
        auth_context: The current authentication context
        skip: Number of auth providers to skip
        limit: Maximum number of auth providers to return

    Returns:
    --------
        List[schemas.AuthProvider]: List of available auth providers
    """
    auth_providers = await crud.auth_provider.get_multi(db, skip=skip, limit=limit)
    return auth_providers


@router.get("/detail/{short_name}", response_model=schemas.AuthProvider)
async def get_auth_provider(
    *,
    db: AsyncSession = Depends(deps.get_db),
    short_name: str,
    auth_context: AuthContext = Depends(deps.get_auth_context),
) -> schemas.AuthProvider:
    """Get details of a specific auth provider.

    Args:
    -----
        db: The database session
        short_name: The short name of the auth provider
        auth_context: The current authentication context

    Returns:
    --------
        schemas.AuthProvider: The auth provider details
    """
    auth_provider = await crud.auth_provider.get_by_short_name(db, short_name=short_name)
    if not auth_provider:
        raise HTTPException(
            status_code=404,
            detail=f"Auth provider not found: {short_name}",
        )
    return auth_provider


@router.post("/", response_model=schemas.AuthProviderConnection)
async def connect_auth_provider(
    *,
    db: AsyncSession = Depends(deps.get_db),
    auth_provider_connection_in: schemas.AuthProviderConnectionCreate,
    auth_context: AuthContext = Depends(deps.get_auth_context),
) -> schemas.AuthProviderConnection:
    """Create a new auth provider connection with credentials.

    Args:
    -----
        db: The database session
        auth_context: The current authentication context
        auth_provider_connection_in: The auth provider connection data

    Returns:
    --------
        schemas.AuthProviderConnection: The created connection
    """
    async with UnitOfWork(db) as uow:
        try:
            # 1. Validate auth provider exists
            auth_provider = await crud.auth_provider.get_by_short_name(
                uow.session, auth_provider_connection_in.short_name
            )
            if not auth_provider:
                raise HTTPException(
                    status_code=400,
                    detail=f"Auth provider not found: {auth_provider_connection_in.short_name}",
                )

            # 2. Validate auth fields
            validated_auth_fields = await _validate_auth_fields(
                uow.session,
                auth_provider_connection_in.short_name,
                auth_provider_connection_in.auth_fields,
            )

            # 3. Create integration credential with encrypted auth credentials
            integration_credential_data = schemas.IntegrationCredentialCreateEncrypted(
                name=f"{auth_provider_connection_in.name} Credentials",
                integration_short_name=auth_provider_connection_in.short_name,
                description=f"Credentials for {auth_provider_connection_in.name}",
                integration_type=IntegrationType.AUTH_PROVIDER,
                auth_type=auth_provider.auth_type,
                encrypted_credentials=credentials.encrypt(validated_auth_fields),
                auth_config_class=auth_provider.auth_config_class,
            )

            integration_credential = await crud.integration_credential.create(
                uow.session,
                obj_in=integration_credential_data,
                auth_context=auth_context,
                uow=uow,
            )
            await uow.session.flush()

            # 4. Create connection without config fields
            connection_data = schemas.ConnectionCreate(
                name=auth_provider_connection_in.name,
                readable_id=auth_provider_connection_in.readable_id,
                description=f"Auth provider connection for {auth_provider_connection_in.name}",
                integration_type=IntegrationType.AUTH_PROVIDER,
                status=ConnectionStatus.ACTIVE,
                integration_credential_id=integration_credential.id,
                short_name=auth_provider_connection_in.short_name,
            )

            connection = await crud.connection.create(
                uow.session,
                obj_in=connection_data,
                auth_context=auth_context,
                uow=uow,
            )
            await uow.session.flush()

            # 6. Return response
            return schemas.AuthProviderConnection(
                id=connection.id,
                name=connection.name,
                readable_id=connection.readable_id,
                short_name=connection.short_name,
                description=connection.description,
                status=connection.status.value,
                created_at=connection.created_at,
                modified_at=connection.modified_at,
            )

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Failed to create auth provider connection: {str(e)}")
            raise HTTPException(
                status_code=500, detail=f"Failed to create auth provider connection: {str(e)}"
            ) from e
