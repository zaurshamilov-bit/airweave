"""White label endpoints."""

from typing import Optional
from uuid import UUID

from fastapi import (
    BackgroundTasks,
    Body,
    Depends,
    HTTPException,
    Path,
    Request,
    Response,
)
from sqlalchemy.ext.asyncio import AsyncSession

from airweave import crud, schemas
from airweave.api import deps
from airweave.api.examples import (
    create_source_connection_list_response,
    create_white_label_list_response,
)
from airweave.api.router import TrailingSlashRouter
from airweave.core.logging import ContextualLogger, logger
from airweave.core.source_connection_service import source_connection_service
from airweave.core.sync_service import sync_service
from airweave.db.session import get_db_context
from airweave.platform.auth.services import oauth2_service
from airweave.schemas.auth import AuthContext

router = TrailingSlashRouter()


async def _handle_white_label_cors(
    request: Request,
    response: Response,
    white_label_id: UUID,
    db: AsyncSession,
    auth_context: AuthContext,
) -> None:
    """Validate white label origin - CORS headers are now handled by middleware.

    Args:
        request: The request object
        response: The response object
        white_label_id: The white label ID
        db: The database session
        auth_context: The current authentication context
    """
    # Get origin from request headers
    origin = request.headers.get("origin")
    if not origin:
        return

    try:
        # Validate against the white label's allowed origins
        white_label = await crud.white_label.get(
            db=db, id=white_label_id, auth_context=auth_context
        )
        if not white_label or not white_label.allowed_origins:
            logger.debug(f"White label {white_label_id} not found or has no allowed origins")
            return

        # Get allowed origins from white label
        allowed_origins = [origin.strip() for origin in white_label.allowed_origins.split(",")]

        # Check if the request origin is allowed
        if origin in allowed_origins:
            # Add CORS headers to the response
            response.headers["Access-Control-Allow-Origin"] = origin
            response.headers["Access-Control-Allow-Credentials"] = "true"
            logger.debug(f"Added CORS headers for white label {white_label_id} and origin {origin}")
    except Exception as e:
        raise HTTPException(status_code=400, detail="Failed to validate white label origin.") from e


@router.get(
    "/list",
    response_model=list[schemas.WhiteLabel],
    responses=create_white_label_list_response(
        ["github_integration"],
        "GitHub integration",
    ),
)
async def list_white_labels(
    db: AsyncSession = Depends(deps.get_db),
    auth_context: AuthContext = Depends(deps.get_auth_context),
) -> list[schemas.WhiteLabel]:
    """List all white label integrations for your organization.

    <br/><br/>
    Returns all custom OAuth integrations configured with your own branding and
    credentials. These integrations allow you to present OAuth consent screens with
    your company name instead of Airweave.<br/><br/>**White label integrations only
    work with OAuth2.0 sources** like Slack, Google Drive, or HubSpot that require
    OAuth consent flows.
    """
    white_labels = await crud.white_label.get_multi(db, auth_context=auth_context)
    return white_labels


@router.post("/", response_model=schemas.WhiteLabel)
async def create_white_label(
    *,
    db: AsyncSession = Depends(deps.get_db),
    auth_context: AuthContext = Depends(deps.get_auth_context),
    white_label_in: schemas.WhiteLabelCreate = Body(...),
    logger: ContextualLogger = Depends(deps.get_logger),
) -> schemas.WhiteLabel:
    """Create a new white label integration.

    <br/><br/>
    **This only works for sources that use OAuth2.0 authentication** like Slack,
    Google Drive, GitHub, or HubSpot.<br/><br/>Sets up a custom OAuth integration
    using your own OAuth application credentials and branding. Once created,
    customers will see your company name during OAuth consent flows instead of
    Airweave. This requires you to have already configured your own OAuth
    application with the target service provider.
    """
    logger.info(f"Creating white label {white_label_in.name}.")
    white_label = await crud.white_label.create(
        db,
        obj_in=white_label_in,
        auth_context=auth_context,
    )
    return white_label


@router.get("/{white_label_id}", response_model=schemas.WhiteLabel)
async def get_white_label(
    white_label_id: UUID = Path(
        ..., description="The unique identifier of the white label integration"
    ),
    db: AsyncSession = Depends(deps.get_db),
    auth_context: AuthContext = Depends(deps.get_auth_context),
    logger: ContextualLogger = Depends(deps.get_logger),
) -> schemas.WhiteLabel:
    """Retrieve a specific white label integration by its ID."""
    logger.info(
        f"Getting white label {white_label_id} for organization {auth_context.organization_id}"
    )
    white_label = await crud.white_label.get(db, id=white_label_id, auth_context=auth_context)
    if white_label.organization_id != auth_context.organization_id:  # type: ignore
        raise HTTPException(status_code=403, detail="Not enough permissions")
    return white_label


@router.put("/{white_label_id}", response_model=schemas.WhiteLabel)
async def update_white_label(
    *,
    db: AsyncSession = Depends(deps.get_db),
    auth_context: AuthContext = Depends(deps.get_auth_context),
    white_label_id: UUID = Path(
        ..., description="The unique identifier of the white label integration to update"
    ),
    white_label_in: schemas.WhiteLabelUpdate = Body(...),
) -> schemas.WhiteLabel:
    """Update a white label integration's configuration."""
    # TODO: Check if update is valid (i.e. scopes, source id etc)
    white_label = await crud.white_label.get(db, id=white_label_id, auth_context=auth_context)
    if white_label.organization_id != auth_context.organization_id:  # type: ignore
        raise HTTPException(status_code=403, detail="Not enough permissions")

    white_label = await crud.white_label.update(
        db,
        db_obj=white_label,
        obj_in=white_label_in,
        auth_context=auth_context,
    )
    return white_label


@router.delete("/{white_label_id}")
async def delete_white_label(
    white_label_id: UUID = Path(
        ..., description="The unique identifier of the white label integration to delete"
    ),
    db: AsyncSession = Depends(deps.get_db),
    auth_context: AuthContext = Depends(deps.get_auth_context),
) -> schemas.WhiteLabel:
    """Delete a white label integration.

    <br/><br/>
    Permanently removes the white label configuration and OAuth credentials.
    Existing source connections created through this integration will continue to work,
    but no new OAuth flows can be initiated until a new white label integration is created.
    """
    white_label = await crud.white_label.get(db, id=white_label_id, auth_context=auth_context)
    if white_label.organization_id != auth_context.organization_id:
        raise HTTPException(status_code=403, detail="Not enough permissions")

    return await crud.white_label.remove(db, id=white_label_id, auth_context=auth_context)


@router.api_route(
    "/{white_label_id}/oauth2/auth_url",
    response_model=str,
    methods=["GET", "OPTIONS"],
    responses={
        200: {
            "description": "OAuth2 authorization URL with your branding",
            "content": {
                "application/json": {
                    "examples": {
                        "slack_auth_url": {
                            "summary": "Slack OAuth URL",
                            "value": "https://slack.com/oauth/v2/authorize?response_type=code&client_id=1234567890.1234567890123&redirect_uri=https%3A//yourapp.com/auth/slack/callback&scope=channels%3Aread+chat%3Awrite+users%3Aread",
                        },
                    }
                }
            },
        }
    },
)
async def get_white_label_oauth2_auth_url(
    *,
    request: Request,
    response: Response,
    db: AsyncSession = Depends(deps.get_db),
    white_label_id: UUID = Path(
        ..., description="The unique identifier of the white label integration"
    ),
    auth_context: AuthContext = Depends(deps.get_auth_context),
) -> str:
    """Generate a branded OAuth2 authorization URL for customer authentication.

    <br/><br/>
    Creates the OAuth consent URL that customers should be redirected to for
    authentication. The OAuth consent screen will display your company name and
    branding instead of Airweave.
    """
    # Handle CORS for white label
    await _handle_white_label_cors(request, response, white_label_id, db, auth_context)

    # Handle OPTIONS request for preflight
    if request.method == "OPTIONS":
        return ""

    white_label = await crud.white_label.get(db, id=white_label_id, auth_context=auth_context)
    if white_label.organization_id != auth_context.organization_id:  # type: ignore
        raise HTTPException(status_code=403, detail="Not enough permissions")

    return await oauth2_service.generate_auth_url_for_whitelabel(db=db, white_label=white_label)


@router.get(
    "/{white_label_id}/source-connections",
    response_model=list[schemas.SourceConnectionListItem],
    responses=create_source_connection_list_response(
        ["white_label_slack"],
        "Source connections created through white label OAuth flows",
    ),
)
async def list_white_label_source_connections(
    white_label_id: UUID = Path(
        ..., description="The unique identifier of the white label integration"
    ),
    db: AsyncSession = Depends(deps.get_db),
    auth_context: AuthContext = Depends(deps.get_auth_context),
) -> list[schemas.SourceConnectionListItem]:
    """List all source connections created through a specific white label integration.

    <br/><br/>
    Returns source connections that were established using this white label's OAuth flow.
    """
    white_label = await crud.white_label.get(db, id=white_label_id, auth_context=auth_context)
    if white_label.organization_id != auth_context.organization_id:
        raise HTTPException(status_code=403, detail="Not enough permissions")

    source_connections = await crud.source_connection.get_for_white_label(
        db, white_label_id=white_label_id, auth_context=auth_context
    )

    return [
        schemas.SourceConnectionListItem.model_validate(sc, from_attributes=True)
        for sc in source_connections
    ]


@router.api_route(
    "/{white_label_id}/oauth2/code",
    response_model=schemas.SourceConnection,
    methods=["POST", "OPTIONS"],
)
async def exchange_white_label_oauth2_code(
    *,
    request: Request,
    response: Response,
    white_label_id: UUID = Path(
        ..., description="The unique identifier of the white label integration"
    ),
    code: str = Body(
        ...,
        description=(
            "The OAuth2 authorization code received from the OAuth callback "
            "after customer authentication"
        ),
        examples=[
            "4/P7q7W91a-oMsCeLvIaQm6bTrgtp7",
        ],
    ),
    source_connection_in: Optional[schemas.SourceConnectionCreateWithWhiteLabel] = Body(
        None,
        description=(
            "Optional configuration for the source connection. If not provided, "
            "a source connection will be created automatically with default settings. "
            "The white label integration is automatically linked to the source connection."
        ),
    ),
    db: AsyncSession = Depends(deps.get_db),
    auth_context: AuthContext = Depends(deps.get_auth_context),
    logger: ContextualLogger = Depends(deps.get_logger),
    background_tasks: BackgroundTasks,
) -> schemas.SourceConnection:
    """Complete the OAuth flow and create a source connection.

    <br/><br/>
    **This is the core endpoint that converts OAuth authorization codes into working
    source connections.**<br/><br/>The OAuth credentials are obtained automatically
    from the authorization code - you do not need to provide auth_fields. The white
    label integration is automatically linked to the created source connection for
    tracking and branding purposes.
    """
    # Handle CORS for white label
    await _handle_white_label_cors(request, response, white_label_id, db, auth_context)

    # Handle OPTIONS request for preflight
    if request.method == "OPTIONS":
        return ""

    white_label = await crud.white_label.get(db, id=white_label_id, auth_context=auth_context)

    if white_label.organization_id != auth_context.organization_id:
        raise HTTPException(status_code=403, detail="Not enough permissions")

    white_label = schemas.WhiteLabel.model_validate(white_label, from_attributes=True)
    logger.info(f"Exchanging OAuth2 code for WhiteLabel {white_label.id}.")
    try:
        # Exchange code for connection
        connection = await oauth2_service.create_oauth2_connection_for_whitelabel(
            db=db, white_label=white_label, code=code, auth_context=auth_context
        )
        logger.info(f"Created connection {connection.id} for WhiteLabel {white_label.id}.")

        # Create or use the provided source connection config
        if source_connection_in is None:
            # If no source connection provided, create one with defaults
            source_connection_in = schemas.SourceConnectionCreateWithWhiteLabel(
                name=f"{connection.name} from {white_label.name}",
                description=f"Created from white label {white_label.name}",
                short_name=white_label.source_short_name,
                sync_immediately=True,
                white_label_id=white_label_id,
                credential_id=connection.integration_credential_id,
            )
        else:
            # Ensure white_label_id and short_name are set correctly
            source_connection_in.white_label_id = white_label_id
            source_connection_in.credential_id = connection.integration_credential_id
            if not source_connection_in.short_name:
                source_connection_in.short_name = white_label.source_short_name

        # Create the source connection with the connection ID
        source_connection, sync_job = await source_connection_service.create_source_connection(
            db=db,
            source_connection_in=source_connection_in,
            auth_context=auth_context,
        )

        # If job was created and sync_immediately is True, start it in background
        if sync_job:
            async with get_db_context() as sync_db:
                sync_dag = await sync_service.get_sync_dag(
                    db=sync_db, sync_id=source_connection.sync_id, auth_context=auth_context
                )

                # Get the sync object
                sync = await crud.sync.get(
                    db=sync_db, id=source_connection.sync_id, auth_context=auth_context
                )
                sync = schemas.Sync.model_validate(sync, from_attributes=True)
                sync_job = schemas.SyncJob.model_validate(sync_job, from_attributes=True)
                sync_dag = schemas.SyncDag.model_validate(sync_dag, from_attributes=True)
                collection = await crud.collection.get_by_readable_id(
                    db=sync_db, readable_id=source_connection.collection, auth_context=auth_context
                )
                collection = schemas.Collection.model_validate(collection, from_attributes=True)

            background_tasks.add_task(
                sync_service.run,
                sync,
                sync_job,
                sync_dag,
                collection,
                source_connection,
                auth_context,
            )

        # Make sure we are returning the source_connection, not anything else
        logger.debug(f"Returning source_connection: {source_connection}")
        return source_connection

    except Exception as e:
        logger.error(f"Failed to exchange OAuth2 code for WhiteLabel {white_label.id}: {e}")
        # Pass through the detailed error message if it's an HTTPException
        if isinstance(e, HTTPException):
            raise
        raise HTTPException(status_code=400, detail=str(e)) from e
