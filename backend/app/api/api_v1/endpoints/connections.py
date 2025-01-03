"""The API module that contains the endpoints for connections."""


from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app import crud, schemas
from app.api import deps
from app.core import credentials
from app.core.logging import logger
from app.db.unit_of_work import UnitOfWork
from app.models.integration_credential import IntegrationType
from app.platform.auth.schemas import AuthType
from app.platform.auth.services import oauth2_service
from app.platform.auth.settings import integration_settings
from app.platform.locator import resource_locator
from app.schemas.connection import ConnectionCreate, ConnectionStatus

router = APIRouter()


@router.get(
    "/list/all",
    response_model=list[schemas.Connection],
)
async def list_all_connected_integrations(
    db: AsyncSession = Depends(deps.get_db),
    user: schemas.User = Depends(deps.get_user),
) -> list[schemas.Connection]:
    """Get all active connections for the current user across all integration types."""
    connections = await crud.connection.get_all_for_user(db, current_user=user)
    return connections


@router.get(
    "/list/{integration_type}",
    response_model=list[schemas.Connection],
)
async def list_connected_integrations(
    integration_type: IntegrationType,
    db: AsyncSession = Depends(deps.get_db),
    user: schemas.User = Depends(deps.get_user),
) -> list[schemas.Connection]:
    """Get all integrations of specified type connected to the current user."""
    connections = await crud.connection.get_active_by_integration_type(
        db, integration_type=integration_type, organization_id=user.organization_id
    )
    return connections


@router.post(
    "/connect/{integration_type}/{short_name}",
    response_model=schemas.Connection,
)
async def connect_integration(
    *,
    db: AsyncSession = Depends(deps.get_db),
    integration_type: IntegrationType,
    short_name: str,
    config_fields: dict,
    user: schemas.User = Depends(deps.get_user),
) -> schemas.Connection:
    """Connect to a source, destination, or embedding model.

    Use the `/sources/{short_name}, /destinations/{short_name}, /embedding_models/{short_name}`
        endpoints to get the auth config fields.
    """
    async with UnitOfWork(db) as uow:
        # Get the integration based on type
        integration = None
        if integration_type == IntegrationType.SOURCE:
            integration = await crud.source.get_by_short_name(uow.session, short_name)
        elif integration_type == IntegrationType.DESTINATION:
            integration = await crud.destination.get_by_short_name(uow.session, short_name)
        elif integration_type == IntegrationType.EMBEDDING_MODEL:
            integration = await crud.embedding_model.get_by_short_name(uow.session, short_name)

        if not integration:
            raise HTTPException(
                status_code=400,
                detail=f"{integration_type} with short_name '{short_name}' does not exist",
            )

        if integration.auth_type != AuthType.config_class:
            raise HTTPException(
                status_code=400,
                detail=(
                    f"Integration {integration.name} does not support config fields, "
                    "use the UI to connect"
                ),
            )

        # Create and validate auth config if exists
        if integration.auth_config_class:
            auth_config_class = resource_locator.get_auth_config(integration.auth_config_class)
            auth_config = auth_config_class(**config_fields)
            encrypted_creds = credentials.encrypt(auth_config.model_dump())
        else:
            encrypted_creds = credentials.encrypt({})

        # Create integration credential
        integration_cred_in = schemas.IntegrationCredentialCreateEncrypted(
            name=f"{integration.name} - {user.email}",
            description=f"Credentials for {integration.name} - {user.email}",
            integration_short_name=integration.short_name,
            integration_type=integration_type,
            auth_type=integration.integration.auth_type,
            encrypted_credentials=encrypted_creds,
            auth_config_class=integration.auth_config_class,
        )

        integration_cred = await crud.integration_credential.create(
            uow.session, obj_in=integration_cred_in, current_user=user, uow=uow
        )
        await uow.session.flush()

        # Create connection with appropriate ID field
        connection_data = {
            "name": f"Connection to {integration.name}",
            "integration_type": integration_type,
            "status": ConnectionStatus.ACTIVE,
            "integration_credential_id": integration_cred.id,
        }

        # Set the appropriate ID based on integration type
        if integration_type == IntegrationType.SOURCE:
            connection_data["source_id"] = integration.id
        elif integration_type == IntegrationType.DESTINATION:
            connection_data["destination_id"] = integration.id
        elif integration_type == IntegrationType.EMBEDDING_MODEL:
            connection_data["embedding_model_id"] = integration.id

        connection_in = ConnectionCreate(**connection_data)
        connection = await crud.connection.create(
            uow.session, obj_in=connection_in, current_user=user, uow=uow
        )

        await uow.commit()
        await uow.session.refresh(connection)

        return connection


@router.delete("/disconnect/{integration_type}/{short_name}", response_model=schemas.Connection)
async def disconnect_integration(
    *,
    db: AsyncSession = Depends(deps.get_db),
    integration_type: IntegrationType,
    short_name: str,
    user: schemas.User = Depends(deps.get_user),
) -> schemas.Connection:
    """Disconnect from a source, destination, or embedding model.

    This will:
    1. Find the active connection for the given integration
    2. Set its status to INACTIVE
    3. Return the updated connection
    """
    async with UnitOfWork(db) as uow:
        # Get active connection for this integration
        connections = await crud.connection.get_active_by_integration_type(
            uow.session, integration_type=integration_type, organization_id=user.organization_id
        )

        # Find the specific connection for this short_name
        connection = next(
            (
                conn
                for conn in connections
                if conn.integration_credential.integration_short_name == short_name
            ),
            None,
        )

        if not connection:
            raise HTTPException(
                status_code=404,
                detail=f"No active connection found for {integration_type} '{short_name}'",
            )

        # Update connection status to inactive
        connection_update = schemas.ConnectionUpdate(status=ConnectionStatus.INACTIVE)

        updated_connection = await crud.connection.update(
            uow.session, db_obj=connection, obj_in=connection_update, current_user=user, uow=uow
        )

        await uow.commit()
        await uow.session.refresh(updated_connection)

        return updated_connection


@router.get("/oauth2/source/auth_url")
async def get_oauth2_auth_url(
    *,
    db: AsyncSession = Depends(deps.get_db),
    short_name: str,
    user: schemas.User = Depends(deps.get_user),
) -> str:
    """Get the OAuth2 authorization URL for a source."""
    settings = integration_settings.get_by_short_name(short_name)

    if not settings:
        raise HTTPException(status_code=404, detail="Integration not found")

    if short_name == "trello":
        return oauth2_service.generate_auth_url_for_trello()

    if settings.auth_type not in [
        AuthType.oauth2,
        AuthType.oauth2_with_refresh,
        AuthType.oauth2_with_refresh_rotating,
    ]:
        raise HTTPException(status_code=400, detail="Integration does not support OAuth2")
    return oauth2_service.generate_auth_url(settings)


@router.post("/oauth2/source/code")
async def send_oauth2_code(
    *,
    db: AsyncSession = Depends(deps.get_db),
    short_name: str,
    code: str,
    user: schemas.User = Depends(deps.get_user),
) -> schemas.SourceConnection:
    """Send the OAuth2 authorization code for a source.

    This will:
    1. Get the OAuth2 settings for the source
    2. Exchange the authorization code for a token
    3. Create an integration credential with the token
    """
    settings = integration_settings.get_by_short_name(short_name)

    if not settings:
        raise HTTPException(status_code=404, detail="Integration not found")

    source = await crud.source.get_by_short_name(db, short_name)

    if not source:
        raise HTTPException(status_code=404, detail="Source not found")

    if source.auth_type not in (
        AuthType.oauth2,
        AuthType.oauth2_with_refresh,
        AuthType.oauth2_with_refresh_rotating,
    ):
        raise HTTPException(status_code=400, detail="Source does not support OAuth2")
    try:
        oauth2_response = await oauth2_service.exchange_autorization_code_for_token(
            short_name, code
        )

        decrypted_credentials = (
            {"access_token": oauth2_response.access_token}
            if settings.auth_type == "oauth2"
            else {"refresh_token": oauth2_response.refresh_token}
        )

        encrypted_credentials = credentials.encrypt(decrypted_credentials)

        async with UnitOfWork(db) as uow:
            integration_credential_in = schemas.IntegrationCredentialCreate(
                name=f"{source.name} - {user.email}",
                description=f"OAuth2 credentials for {source.name} - {user.email}",
                integration_short_name=source.short_name,
                integration_type=IntegrationType.SOURCE,
                auth_type=source.auth_type,
                encrypted_credentials=encrypted_credentials,
            )

            integration_credential = await crud.integration_credential.create(
                uow.session, obj_in=integration_credential_in, current_user=user, uow=uow
            )

            await uow.session.flush()

            connection_in = ConnectionCreate(
                name=f"Connection to {source.name}",
                integration_type=IntegrationType.SOURCE,
                status=ConnectionStatus.ACTIVE,
                integration_credential_id=integration_credential.id,
                source_id=source.id,
            )

            connection = await crud.connection.create(
                uow.session, obj_in=connection_in, current_user=user, uow=uow
            )

            await uow.commit()
            await uow.session.refresh(connection)

        return connection
    except Exception as e:
        logger.error(f"Failed to exchange OAuth2 code: {e}")
        raise HTTPException(status_code=400, detail="Failed to exchange OAuth2 code") from e
