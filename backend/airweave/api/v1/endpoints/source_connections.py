"""API endpoints for managing source connections."""

import urllib.parse
from datetime import datetime, timezone
from typing import List, Optional
from uuid import UUID

from fastapi import BackgroundTasks, Body, Depends, HTTPException, Path, Query
from fastapi.responses import RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession

from airweave import crud, schemas
from airweave.analytics import track_api_endpoint
from airweave.api import deps
from airweave.api.context import ApiContext
from airweave.api.examples import (
    create_job_list_response,
    create_single_job_response,
    create_source_connection_list_response,
)
from airweave.api.router import TrailingSlashRouter
from airweave.core.datetime_utils import utc_now_naive
from airweave.core.guard_rail_service import GuardRailService
from airweave.core.logging import logger
from airweave.core.shared_models import ActionType, SyncJobStatus
from airweave.core.source_connection_service import source_connection_service
from airweave.core.sync_job_service import sync_job_service
from airweave.core.sync_service import sync_service
from airweave.crud import redirect_session
from airweave.db.session import get_db_context

router = TrailingSlashRouter()


# Single source of truth for continuous sync support across creation and conversion paths
SUPPORTED_CONTINUOUS_SOURCES = [
    "github",
    "google_drive",
    "outlook_mail",
    "postgresql",
]


@router.get("/callback")
async def complete_source_connection_callback(
    *,
    db: AsyncSession = Depends(deps.get_db),
    code: str = Query(..., description="Authorization code returned by provider"),
    state: str = Query(..., description="State value returned by provider"),
    ctx: ApiContext = Depends(deps.get_context),
    guard_rail: GuardRailService = Depends(deps.get_guard_rail_service),
    background_tasks: BackgroundTasks,
):
    """OAuth2 callback endpoint (no short_name).

    Completes the connection, kicks off the initial sync if requested,
    and redirects to the final app URL.
    """
    (
        source_connection,
        final_redirect_url,
        sync_job,
        meta,
    ) = await source_connection_service.complete_connection_from_oauth_callback(
        db=db, state=state, code=code, ctx=ctx
    )
    meta = meta or {}

    # Guard-rail increments for the newly created connection (parity with non-OAuth path)
    await guard_rail.increment(ActionType.SOURCE_CONNECTIONS)
    if meta.get("creating_new_collection"):
        await guard_rail.increment(ActionType.COLLECTIONS)

    # If a job was created and sync_immediately is on, dispatch it now (Temporal or background)
    sync_job_id = None
    if sync_job and meta.get("sync_immediately", True):
        sync_dag = await sync_service.get_sync_dag(db=db, sync_id=sync_job.sync_id, ctx=ctx)
        sync = await crud.sync.get(db=db, id=sync_job.sync_id, ctx=ctx)
        sync = schemas.Sync.model_validate(sync, from_attributes=True)
        sync_dag = schemas.SyncDag.model_validate(sync_dag, from_attributes=True)

        collection = await crud.collection.get_by_readable_id(
            db=db, readable_id=source_connection.collection, ctx=ctx
        )
        collection = schemas.Collection.model_validate(collection, from_attributes=True)

        source_connection_with_auth = await source_connection_service.get_source_connection(
            db=db,
            source_connection_id=source_connection.id,
            show_auth_fields=True,
            ctx=ctx,
        )

        await source_connection_service.run_sync_job_workflow(
            sync=sync,
            sync_job=sync_job,
            sync_dag=sync_dag,
            collection=collection,
            source_connection=source_connection_with_auth,
            ctx=ctx,
            background_tasks=background_tasks,
            access_token=getattr(sync_job, "access_token", None),
        )

        await guard_rail.increment(ActionType.SYNCS)
        sync_job_id = str(sync_job.id)

    # Redirect with useful context for the app
    params = {
        "status": "sync_started" if sync_job_id else "success",
        "source_connection_id": str(source_connection.id),
        "collection": source_connection.collection,
    }
    if sync_job_id:
        params["sync_job_id"] = sync_job_id

    qs = urllib.parse.urlencode(params)
    target = (
        f"{final_redirect_url}?{qs}"
        if "?" not in final_redirect_url
        else f"{final_redirect_url}&{qs}"
    )
    return RedirectResponse(url=target, status_code=302)


@router.get(
    "/",
    response_model=List[schemas.SourceConnectionListItem],
    responses=create_source_connection_list_response(
        ["engineering_docs"], "Multiple source connections across collections"
    ),
)
async def list(
    *,
    db: AsyncSession = Depends(deps.get_db),
    collection: Optional[str] = Query(
        None, description="Filter source connections by collection readable ID"
    ),
    skip: int = Query(0, description="Number of source connections to skip for pagination"),
    limit: int = Query(
        100, description="Maximum number of source connections to return (1-1000)", le=1000, ge=1
    ),
    ctx: ApiContext = Depends(deps.get_context),
) -> List[schemas.SourceConnectionListItem]:
    """List source connections across your organization."""
    if collection:
        return await source_connection_service.get_source_connections_by_collection(
            db=db,
            collection=collection,
            ctx=ctx,
            skip=skip,
            limit=limit,
        )

    return await source_connection_service.get_all_source_connections(
        db=db, ctx=ctx, skip=skip, limit=limit
    )


@router.get("/{source_connection_id}", response_model=schemas.SourceConnection)
async def get(
    *,
    db: AsyncSession = Depends(deps.get_db),
    source_connection_id: UUID = Path(
        ..., description="The unique identifier of the source connection"
    ),
    show_auth_fields: bool = Query(
        False,
        description="Whether to reveal authentication credentials.",
    ),
    ctx: ApiContext = Depends(deps.get_context),
) -> schemas.SourceConnection:
    """Retrieve a specific source connection by its ID."""
    result = await source_connection_service.get_source_connection(
        db=db,
        source_connection_id=source_connection_id,
        show_auth_fields=show_auth_fields,
        ctx=ctx,
    )
    return result


@router.post("/", response_model=schemas.SourceConnection)
@track_api_endpoint("create_source_connection")
async def create(
    *,
    db: AsyncSession = Depends(deps.get_db),
    source_connection_in: schemas.SourceConnectionCreate = Body(...),
    ctx: ApiContext = Depends(deps.get_context),
    guard_rail: GuardRailService = Depends(deps.get_guard_rail_service),
    background_tasks: BackgroundTasks,
) -> schemas.SourceConnection:
    """Create a new source connection to sync data into your collection.

    The auth_mode determines how authentication is handled:
    - oauth2: Returns an authentication URL for browser-based OAuth flow (unless tokens provided)
    - direct_auth: Creates connection immediately with provided credentials
    - external_provider: Creates connection using auth provider credentials

    For OAuth flows, check the authentication_url field in the response.
    """
    await guard_rail.is_allowed(ActionType.SOURCE_CONNECTIONS)

    if source_connection_in.collection is None:
        await guard_rail.is_allowed(ActionType.COLLECTIONS)

    if source_connection_in.sync_immediately:
        await guard_rail.is_allowed(ActionType.SYNCS)
        await guard_rail.is_allowed(ActionType.ENTITIES)

    # Validate source can use auth providers
    if hasattr(source_connection_in, "auth_mode"):
        source_connection_service.validate_source_for_auth_provider(
            source_connection_in.short_name, source_connection_in.auth_mode
        )

    creating_new_collection = source_connection_in.collection is None

    # Create the source connection (may return auth URL for OAuth flows)
    (
        init_id,
        auth_url,
        source_connection,
        sync_job,
    ) = await source_connection_service.create_source_connection(
        db=db, source_connection_in=source_connection_in, ctx=ctx
    )

    # If OAuth flow is needed, return immediately with auth URL
    if auth_url:
        # Guard rail increments will happen in the callback endpoint
        source_connection.authentication_url = auth_url
        return source_connection

    # For immediate creation, increment guard rails
    await guard_rail.increment(ActionType.SOURCE_CONNECTIONS)

    if creating_new_collection:
        await guard_rail.increment(ActionType.COLLECTIONS)

    # Run sync if requested
    if sync_job and source_connection_in.sync_immediately:
        async with get_db_context() as db:
            sync_dag = await sync_service.get_sync_dag(
                db=db, sync_id=source_connection.sync_id, ctx=ctx
            )

            sync = await crud.sync.get(db=db, id=source_connection.sync_id, ctx=ctx)
            sync = schemas.Sync.model_validate(sync, from_attributes=True)
            sync_dag = schemas.SyncDag.model_validate(sync_dag, from_attributes=True)
            collection = await crud.collection.get_by_readable_id(
                db=db, readable_id=source_connection.collection, ctx=ctx
            )
            collection = schemas.Collection.model_validate(collection, from_attributes=True)

            source_connection_with_auth = await source_connection_service.get_source_connection(
                db=db,
                source_connection_id=source_connection.id,
                show_auth_fields=True,
                ctx=ctx,
            )

            await source_connection_service.run_sync_job_workflow(
                sync=sync,
                sync_job=sync_job,
                sync_dag=sync_dag,
                collection=collection,
                source_connection=source_connection_with_auth,
                ctx=ctx,
                background_tasks=background_tasks,
            )

            await guard_rail.increment(ActionType.SYNCS)

    # Return successful creation response (authentication_url is None for authenticated connections)
    return source_connection


@router.post("/internal/", response_model=schemas.SourceConnection)
async def create_with_credential(
    *,
    db: AsyncSession = Depends(deps.get_db),
    source_connection_in: schemas.SourceConnectionCreateWithCredential = Body(...),
    guard_rail: GuardRailService = Depends(deps.get_guard_rail_service),
    ctx: ApiContext = Depends(deps.get_context),
    background_tasks: BackgroundTasks,
) -> schemas.SourceConnection:
    """Create a new source connection using an existing credential (internal use only)."""
    await guard_rail.is_allowed(ActionType.SOURCE_CONNECTIONS)

    if source_connection_in.collection is None:
        await guard_rail.is_allowed(ActionType.COLLECTIONS)

    if source_connection_in.sync_immediately:
        await guard_rail.is_allowed(ActionType.SYNCS)
        await guard_rail.is_allowed(ActionType.ENTITIES)

    creating_new_collection = source_connection_in.collection is None

    _, _, source_connection, sync_job = await source_connection_service.create_source_connection(
        db=db, source_connection_in=source_connection_in, ctx=ctx
    )

    await guard_rail.increment(ActionType.SOURCE_CONNECTIONS)

    if creating_new_collection:
        await guard_rail.increment(ActionType.COLLECTIONS)

    if sync_job and source_connection_in.sync_immediately:
        async with get_db_context() as db:
            sync_dag = await sync_service.get_sync_dag(
                db=db, sync_id=source_connection.sync_id, ctx=ctx
            )

            sync = await crud.sync.get(db=db, id=source_connection.sync_id, ctx=ctx)
            sync = schemas.Sync.model_validate(sync, from_attributes=True)
            sync_dag = schemas.SyncDag.model_validate(sync_dag, from_attributes=True)
            collection = await crud.collection.get_by_readable_id(
                db=db, readable_id=source_connection.collection, ctx=ctx
            )
            collection = schemas.Collection.model_validate(collection, from_attributes=True)

            source_connection_with_auth = await source_connection_service.get_source_connection(
                db=db,
                source_connection_id=source_connection.id,
                show_auth_fields=True,
                ctx=ctx,
            )

            await source_connection_service.run_sync_job_workflow(
                sync=sync,
                sync_job=sync_job,
                sync_dag=sync_dag,
                collection=collection,
                source_connection=source_connection_with_auth,
                ctx=ctx,
                background_tasks=background_tasks,
            )

            await guard_rail.increment(ActionType.SYNCS)

    return source_connection


async def _validate_continuous_source(
    source_connection_in: schemas.SourceConnectionCreateContinuous,
) -> None:
    """Validate that the source supports continuous sync."""
    if source_connection_in.short_name not in SUPPORTED_CONTINUOUS_SOURCES:
        raise HTTPException(
            status_code=422,
            detail=(
                f"The '{source_connection_in.short_name}' source is not yet supported "
                f"for continuous sync. Currently supported sources are: "
                f"{', '.join(SUPPORTED_CONTINUOUS_SOURCES)}. More sources will be added soon."
            ),
        )

    # Auth provider validation is handled later when auth_mode is determined


async def _determine_cursor_field(
    source_connection_in: schemas.SourceConnectionCreateContinuous,
) -> str:
    """Determine the cursor field for incremental sync."""
    core_attrs, auxiliary_attrs = source_connection_in.map_to_core_and_auxiliary_attributes()
    user_cursor_field = auxiliary_attrs.get("cursor_field", None)

    async with get_db_context() as fresh_db:
        from airweave import crud

        source_model = await crud.source.get_by_short_name(
            fresh_db, source_connection_in.short_name
        )
        if not source_model:
            raise HTTPException(
                status_code=404, detail=f"Source '{source_connection_in.short_name}' not found"
            )

    from airweave.platform.locator import resource_locator

    source_class = resource_locator.get_source(source_model)
    temp_source = source_class()
    default_cursor_field = temp_source.get_default_cursor_field()

    cursor_field = user_cursor_field or default_cursor_field

    if not cursor_field:
        raise HTTPException(
            status_code=422,
            detail=(
                f"The '{source_connection_in.short_name}' source requires a 'cursor_field' "
                f"to be specified for incremental syncs."
            ),
        )

    if user_cursor_field and default_cursor_field and cursor_field != default_cursor_field:
        try:
            temp_source.validate_cursor_field(cursor_field)
        except ValueError as e:
            raise HTTPException(status_code=422, detail=str(e)) from e

    return cursor_field


async def _validate_continuous_source_by_short_name(short_name: str) -> None:
    """Validate that the source supports continuous sync (by short_name)."""
    if short_name not in SUPPORTED_CONTINUOUS_SOURCES:
        raise HTTPException(
            status_code=422,
            detail=(
                f"The '{short_name}' source is not yet supported for continuous sync. "
                f"Currently supported sources are: {', '.join(SUPPORTED_CONTINUOUS_SOURCES)}."
            ),
        )


async def _determine_cursor_field_for_source(
    short_name: str, user_cursor_field: Optional[str]
) -> str:
    """Determine and validate cursor field for an existing source connection."""
    # Get the source model to check its default cursor field
    async with get_db_context() as fresh_db:
        source_model = await crud.source.get_by_short_name(fresh_db, short_name)
        if not source_model:
            raise HTTPException(status_code=404, detail=f"Source '{short_name}' not found")

    # Get the source class and default cursor field
    from airweave.platform.locator import resource_locator

    source_class = resource_locator.get_source(source_model)
    temp_source = source_class()
    default_cursor_field = temp_source.get_default_cursor_field()

    cursor_field = user_cursor_field or default_cursor_field

    if not cursor_field:
        raise HTTPException(
            status_code=422,
            detail=(
                f"The '{short_name}' source requires a 'cursor_field' to be specified for "
                f"incremental syncs."
            ),
        )

    # Validate when user overrides default
    if user_cursor_field and default_cursor_field and cursor_field != default_cursor_field:
        try:
            temp_source.validate_cursor_field(cursor_field)
        except ValueError as e:
            raise HTTPException(status_code=422, detail=str(e)) from e

    return cursor_field


async def _run_initial_sync_job(
    source_connection: schemas.SourceConnection,
    sync_job_initial: schemas.SyncJob,
    ctx: ApiContext,
    background_tasks: BackgroundTasks,
) -> None:
    """Run the initial sync job for a continuous source connection."""
    async with get_db_context() as db:
        sync_dag = await sync_service.get_sync_dag(
            db=db, sync_id=source_connection.sync_id, ctx=ctx
        )

        # Get the sync object
        sync = await crud.sync.get(db=db, id=source_connection.sync_id, ctx=ctx)
        sync = schemas.Sync.model_validate(sync, from_attributes=True)
        sync_dag = schemas.SyncDag.model_validate(sync_dag, from_attributes=True)
        collection = await crud.collection.get_by_readable_id(
            db=db, readable_id=source_connection.collection, ctx=ctx
        )
        collection = schemas.Collection.model_validate(collection, from_attributes=True)

        # Get source connection with auth_fields for temporal processing
        source_connection_with_auth = await source_connection_service.get_source_connection(
            db=db,
            source_connection_id=source_connection.id,
            show_auth_fields=True,  # Important: Need actual auth_fields for temporal
            ctx=ctx,
        )

        # Use centralized sync job runner
        await source_connection_service.run_sync_job_workflow(
            sync=sync,
            sync_job=sync_job_initial,
            sync_dag=sync_dag,
            collection=collection,
            source_connection=source_connection_with_auth,
            ctx=ctx,
            background_tasks=background_tasks,
        )


async def _create_minute_level_schedule(
    source_connection: schemas.SourceConnection,
    minute_level_cron: str,
    ctx: ApiContext,
) -> schemas.ScheduleResponse:
    """Create and start the minute-level schedule for continuous sync."""
    try:
        # Create the minute-level schedule using fresh connection
        async with get_db_context() as fresh_db:
            schedule_response = await sync_service.create_minute_level_schedule(
                db=fresh_db,
                sync_id=source_connection.sync_id,
                cron_expression=minute_level_cron,
                ctx=ctx,
            )

            # Always auto-start the schedule
            await sync_service.resume_minute_level_schedule(
                db=fresh_db,
                sync_id=source_connection.sync_id,
                ctx=ctx,
            )

        schedule_response.status = "active"

        logger.info(
            f"Created minute-level schedule for sync {source_connection.sync_id} "
            f"with cron {minute_level_cron}"
        )
        return schedule_response

    except Exception as e:
        logger.error(
            f"Failed to create minute-level schedule for sync {source_connection.sync_id}: {e}"
        )
        # We don't fail the entire operation if schedule creation fails
        return schemas.ScheduleResponse(
            schedule_id=None,
            status="failed",
            message=f"Source connection created but schedule setup failed: {str(e)}",
        )


async def _persist_cursor_field_for_sync(sync_id: UUID, cursor_field: str, ctx: ApiContext) -> None:
    """Persist cursor field for a sync with empty cursor data.

    Subsequent runs populate cursor data as sources yield changes.
    """
    async with get_db_context() as fresh_db:
        from airweave.core.sync_cursor_service import sync_cursor_service

        await sync_cursor_service.create_or_update_cursor(
            db=fresh_db,
            sync_id=sync_id,
            cursor_data={},
            cursor_field=cursor_field,
            ctx=ctx,
        )


async def _create_daily_cleanup_schedule_if_enabled(
    source_connection: schemas.SourceConnection,
    enable_daily_cleanup: bool,
    ctx: ApiContext,
) -> None:
    """Create and start a daily forced-full cleanup schedule if enabled."""
    if not enable_daily_cleanup:
        return

    daily_cleanup_cron = "0 2 * * *"  # 2 AM daily
    try:
        async with get_db_context() as fresh_db:
            sync_model = await crud.sync.get(db=fresh_db, id=source_connection.sync_id, ctx=ctx)
            sync_dag_model = await crud.sync_dag.get_by_sync_id(
                db=fresh_db, sync_id=source_connection.sync_id, ctx=ctx
            )

            collection = await crud.collection.get_by_readable_id(
                db=fresh_db, readable_id=source_connection.collection, ctx=ctx
            )
            collection = schemas.Collection.model_validate(collection, from_attributes=True)

            source_connection_with_auth = await source_connection_service.get_source_connection(
                db=fresh_db,
                source_connection_id=source_connection.id,
                show_auth_fields=True,
                ctx=ctx,
            )

            sync_schema = schemas.Sync.model_validate(sync_model, from_attributes=True)
            sync_dag_schema = schemas.SyncDag.model_validate(sync_dag_model, from_attributes=True)

            from airweave.core.temporal_service import temporal_service

            if await temporal_service.is_temporal_enabled():
                from airweave.platform.temporal.schedule_service import (
                    temporal_schedule_service,
                )

                daily_schedule_id = await temporal_schedule_service.create_daily_cleanup_schedule(
                    sync_id=source_connection.sync_id,
                    cron_expression=daily_cleanup_cron,
                    sync_dict=sync_schema.model_dump(mode="json"),
                    sync_dag_dict=sync_dag_schema.model_dump(mode="json"),
                    collection_dict=collection.model_dump(mode="json"),
                    source_connection_dict=source_connection_with_auth.model_dump(mode="json"),
                    user_dict={
                        "email": ctx.user.email if ctx.user else "api-key-user",
                        "organization": ctx.organization.model_dump(mode="json"),
                        "user": (ctx.user.model_dump(mode="json") if ctx.user else None),
                        "auth_method": ctx.auth_method,
                        "auth_metadata": ctx.auth_metadata,
                        "request_id": ctx.request_id,
                    },
                    db=fresh_db,
                    ctx=ctx,
                )

                await temporal_schedule_service.resume_schedule(
                    schedule_id=daily_schedule_id,
                    sync_id=source_connection.sync_id,
                    user_dict={
                        "email": ctx.user.email if ctx.user else "api-key-user",
                        "organization": ctx.organization.model_dump(mode="json"),
                        "user": (ctx.user.model_dump(mode="json") if ctx.user else None),
                        "auth_method": ctx.auth_method,
                        "auth_metadata": ctx.auth_metadata,
                        "request_id": ctx.request_id,
                    },
                    db=fresh_db,
                    ctx=ctx,
                )

                logger.info(
                    "Created daily cleanup schedule for sync %s with cron %s",
                    source_connection.sync_id,
                    daily_cleanup_cron,
                )
    except Exception as e:
        logger.error(
            "Failed to create daily cleanup schedule for sync %s: %s",
            source_connection.sync_id,
            e,
        )


async def _run_new_sync_job_for_connection(
    source_connection_id: UUID,
    ctx: ApiContext,
    background_tasks: BackgroundTasks,
) -> None:
    """Trigger a new sync job for a source connection and start execution."""
    # Create job
    async with get_db_context() as db:
        sync_job = await source_connection_service.run_source_connection(
            db=db, source_connection_id=source_connection_id, ctx=ctx
        )

    # Start job
    async with get_db_context() as run_db:
        sync = await crud.sync.get(db=run_db, id=sync_job.sync_id, ctx=ctx, with_connections=True)
        sync_dag = await sync_service.get_sync_dag(db=run_db, sync_id=sync_job.sync_id, ctx=ctx)
        source_connection_with_auth = await source_connection_service.get_source_connection(
            db=run_db,
            source_connection_id=source_connection_id,
            show_auth_fields=True,
            ctx=ctx,
        )
        collection = await crud.collection.get_by_readable_id(
            db=run_db, readable_id=source_connection_with_auth.collection, ctx=ctx
        )

        sync = schemas.Sync.model_validate(sync, from_attributes=True)
        sync_dag = schemas.SyncDag.model_validate(sync_dag, from_attributes=True)
        collection = schemas.Collection.model_validate(collection, from_attributes=True)

        await source_connection_service.run_sync_job_workflow(
            sync=sync,
            sync_job=sync_job,
            sync_dag=sync_dag,
            collection=collection,
            source_connection=source_connection_with_auth,
            ctx=ctx,
            background_tasks=background_tasks,
        )


@router.post("/continuous", response_model=schemas.SourceConnectionContinuousResponse)
async def create_continuous_BETA(
    *,
    db: AsyncSession = Depends(deps.get_db),
    source_connection_in: schemas.SourceConnectionCreateContinuous = Body(...),
    ctx: ApiContext = Depends(deps.get_context),
    guard_rail: GuardRailService = Depends(deps.get_guard_rail_service),
    background_tasks: BackgroundTasks,
) -> schemas.SourceConnectionContinuousResponse:
    """Create a continuously syncing source connection (BETA)."""
    await _validate_continuous_source(source_connection_in)

    await guard_rail.is_allowed(ActionType.SOURCE_CONNECTIONS)

    if source_connection_in.collection is None:
        await guard_rail.is_allowed(ActionType.COLLECTIONS)

    await guard_rail.is_allowed(ActionType.SYNCS)
    await guard_rail.is_allowed(ActionType.ENTITIES)

    creating_new_collection = source_connection_in.collection is None

    cursor_field = await _determine_cursor_field(source_connection_in)
    minute_level_cron = "*/1 * * * *"

    # Determine auth_mode based on what's provided
    if source_connection_in.auth_fields:
        auth_mode = "direct_auth"
    elif source_connection_in.auth_provider:
        auth_mode = "external_provider"
    else:
        raise HTTPException(
            status_code=422, detail="Either auth_fields or auth_provider must be provided"
        )

    # Validate source can use auth providers
    source_connection_service.validate_source_for_auth_provider(
        source_connection_in.short_name, auth_mode
    )

    regular_create_data = {
        "name": source_connection_in.name,
        "description": source_connection_in.description,
        "short_name": source_connection_in.short_name,
        "config_fields": source_connection_in.config_fields,
        "collection": source_connection_in.collection,
        "auth_mode": auth_mode,
        "auth_fields": source_connection_in.auth_fields,
        "auth_provider": source_connection_in.auth_provider,
        "auth_provider_config": source_connection_in.auth_provider_config,
        "sync_immediately": True,
        "cron_schedule": None,
    }

    regular_create_data = {k: v for k, v in regular_create_data.items() if v is not None}
    regular_source_connection_in = schemas.SourceConnectionCreate(**regular_create_data)

    async with get_db_context() as fresh_db:
        (
            _,
            _,
            source_connection,
            sync_job_initial,
        ) = await source_connection_service.create_source_connection(
            db=fresh_db, source_connection_in=regular_source_connection_in, ctx=ctx
        )

    guard_rail_fresh = GuardRailService(ctx.organization.id, logger=ctx.logger)
    await guard_rail_fresh.increment(ActionType.SOURCE_CONNECTIONS)
    if creating_new_collection:
        await guard_rail_fresh.increment(ActionType.COLLECTIONS)
    await guard_rail_fresh.increment(ActionType.SYNCS)

    logger.info(
        f"Sync {source_connection.sync_id} created. Initial sync running to establish baseline."
    )

    # Store the cursor field in the database for the sync (empty data initially)
    if cursor_field:
        await _persist_cursor_field_for_sync(
            sync_id=source_connection.sync_id, cursor_field=cursor_field, ctx=ctx
        )
        logger.info(
            f"Cursor field '{cursor_field}' stored for sync {source_connection.sync_id}. "
            f"Initial cursor data will be created after initial sync completes."
        )
        async with get_db_context() as fresh_db:
            from airweave.core.sync_cursor_service import sync_cursor_service

            await sync_cursor_service.create_or_update_cursor(
                db=fresh_db,
                sync_id=source_connection.sync_id,
                cursor_data={},
                cursor_field=cursor_field,
                ctx=ctx,
            )
        logger.info(f"Cursor field '{cursor_field}' stored for sync {source_connection.sync_id}.")

    if sync_job_initial:
        await _run_initial_sync_job(source_connection, sync_job_initial, ctx, background_tasks)

    # Create the minute-level schedule
    schedule_response = await _create_minute_level_schedule(
        source_connection, minute_level_cron, ctx
    )

    # Optionally create the daily cleanup schedule
    await _create_daily_cleanup_schedule_if_enabled(
        source_connection=source_connection,
        enable_daily_cleanup=getattr(source_connection_in, "enable_daily_cleanup", True),
        ctx=ctx,
    )

    # Create the response with schedule information
    async with get_db_context() as db2:
        sync_dag = await sync_service.get_sync_dag(
            db=db2, sync_id=source_connection.sync_id, ctx=ctx
        )
        sync = await crud.sync.get(db=db2, id=source_connection.sync_id, ctx=ctx)
        sync = schemas.Sync.model_validate(sync, from_attributes=True)
        sync_dag = schemas.SyncDag.model_validate(sync_dag, from_attributes=True)
        collection = await crud.collection.get_by_readable_id(
            db=db2, readable_id=source_connection.collection, ctx=ctx
        )
        collection = schemas.Collection.model_validate(collection, from_attributes=True)
        source_connection_with_auth = await source_connection_service.get_source_connection(
            db=db2,
            source_connection_id=source_connection.id,
            show_auth_fields=True,
            ctx=ctx,
        )
        await source_connection_service.run_sync_job_workflow(
            sync=sync,
            sync_job=sync_job_initial,
            sync_dag=sync_dag,
            collection=collection,
            source_connection=source_connection_with_auth,
            ctx=ctx,
            background_tasks=background_tasks,
        )

    schedule_response = await sync_service.create_minute_level_schedule(
        db=db, sync_id=source_connection.sync_id, cron_expression=minute_level_cron, ctx=ctx
    )
    await sync_service.resume_minute_level_schedule(
        db=db, sync_id=source_connection.sync_id, ctx=ctx
    )

    response = schemas.SourceConnectionContinuousResponse.from_orm_with_collection_mapping(
        source_connection
    )
    if schedule_response and schedule_response.schedule_id:
        base_msg = (
            f"Initial sync started and schedule created successfully. "
            f"Incremental syncs will run every {minute_level_cron.split()[0]} minute(s)."
        )
        if getattr(source_connection_in, "enable_daily_cleanup", True):
            base_msg += " Daily cleanup runs at 2 AM to remove orphaned entities."
        response.minute_level_schedule = {
            "schedule_id": schedule_response.schedule_id,
            "cron_expression": minute_level_cron,
            "status": "active",
            "message": base_msg,
        }
    else:
        response.minute_level_schedule = {
            "schedule_id": None,
            "cron_expression": minute_level_cron,
            "status": "failed",
            "message": "Source connection created but schedule setup failed.",
        }

    return response


@router.put("/{source_connection_id}", response_model=schemas.SourceConnection)
async def update(
    *,
    db: AsyncSession = Depends(deps.get_db),
    source_connection_id: UUID = Path(
        ..., description="The unique identifier of the source connection to update"
    ),
    source_connection_in: schemas.SourceConnectionUpdate = Body(...),
    ctx: ApiContext = Depends(deps.get_context),
) -> schemas.SourceConnection:
    """Update a source connection's properties."""
    return await source_connection_service.update_source_connection(
        db=db,
        source_connection_id=source_connection_id,
        source_connection_in=source_connection_in,
        ctx=ctx,
    )


@router.delete("/{source_connection_id}", response_model=schemas.SourceConnection)
async def delete(
    *,
    db: AsyncSession = Depends(deps.get_db),
    source_connection_id: UUID = Path(
        ..., description="The unique identifier of the source connection to delete"
    ),
    ctx: ApiContext = Depends(deps.get_context),
    guard_rail: GuardRailService = Depends(deps.get_guard_rail_service),
) -> schemas.SourceConnection:
    """Delete a source connection and all associated data."""
    await guard_rail.decrement(ActionType.SOURCE_CONNECTIONS)
    return await source_connection_service.delete_source_connection(
        db=db,
        source_connection_id=source_connection_id,
        ctx=ctx,
    )


@router.post(
    "/{source_connection_id}/run",
    response_model=schemas.SourceConnectionJob,
    responses=create_single_job_response("completed", "Sync job successfully triggered"),
)
async def run(
    *,
    db: AsyncSession = Depends(deps.get_db),
    source_connection_id: UUID = Path(
        ..., description="The unique identifier of the source connection to sync"
    ),
    access_token: Optional[str] = Body(
        None,
        embed=True,
        description=(
            "Start a sync job with a direct OAuth access token instead of stored credentials."
        ),
    ),
    ctx: ApiContext = Depends(deps.get_context),
    guard_rail: GuardRailService = Depends(deps.get_guard_rail_service),
    background_tasks: BackgroundTasks,
) -> schemas.SourceConnectionJob:
    """Manually trigger a data sync for this source connection."""
    await guard_rail.is_allowed(ActionType.SYNCS)
    await guard_rail.is_allowed(ActionType.ENTITIES)

    sync_job = await source_connection_service.run_source_connection(
        db=db,
        source_connection_id=source_connection_id,
        ctx=ctx,
        access_token=access_token,
    )

    sync = await crud.sync.get(db=db, id=sync_job.sync_id, ctx=ctx, with_connections=True)
    sync_dag = await sync_service.get_sync_dag(db=db, sync_id=sync_job.sync_id, ctx=ctx)

    source_connection_with_auth = await source_connection_service.get_source_connection(
        db=db,
        source_connection_id=source_connection_id,
        show_auth_fields=True,
        ctx=ctx,
    )

    collection = await crud.collection.get_by_readable_id(
        db=db, readable_id=source_connection_with_auth.collection, ctx=ctx
    )

    sync = schemas.Sync.model_validate(sync, from_attributes=True)
    sync_dag = schemas.SyncDag.model_validate(sync_dag, from_attributes=True)
    collection = schemas.Collection.model_validate(collection, from_attributes=True)

    await source_connection_service.run_sync_job_workflow(
        sync=sync,
        sync_job=sync_job,
        sync_dag=sync_dag,
        collection=collection,
        source_connection=source_connection_with_auth,
        ctx=ctx,
        background_tasks=background_tasks,
        access_token=sync_job.access_token if hasattr(sync_job, "access_token") else None,
    )

    await guard_rail.increment(ActionType.SYNCS)

    return sync_job.to_source_connection_job(source_connection_id)


@router.get(
    "/{source_connection_id}/jobs",
    response_model=List[schemas.SourceConnectionJob],
    responses=create_job_list_response(["completed"], "Complete sync job history"),
)
async def list_jobs(
    *,
    db: AsyncSession = Depends(deps.get_db),
    source_connection_id: UUID = Path(
        ..., description="The unique identifier of the source connection"
    ),
    ctx: ApiContext = Depends(deps.get_context),
) -> List[schemas.SourceConnectionJob]:
    """List all sync jobs for a source connection."""
    return await source_connection_service.get_source_connection_jobs(
        db=db, source_connection_id=source_connection_id, ctx=ctx
    )


@router.get(
    "/{source_connection_id}/jobs/{job_id}",
    response_model=schemas.SourceConnectionJob,
    responses=create_single_job_response("completed", "Detailed sync job information"),
)
async def get_job(
    *,
    db: AsyncSession = Depends(deps.get_db),
    source_connection_id: UUID = Path(
        ..., description="The unique identifier of the source connection"
    ),
    job_id: UUID = Path(..., description="The unique identifier of the sync job"),
    ctx: ApiContext = Depends(deps.get_context),
) -> schemas.SourceConnectionJob:
    """Get detailed information about a specific sync job."""
    tmp = await source_connection_service.get_source_connection_job(
        db=db, source_connection_id=source_connection_id, job_id=job_id, ctx=ctx
    )
    return tmp


@router.post(
    "/{source_connection_id}/jobs/{job_id}/cancel",
    response_model=schemas.SourceConnectionJob,
    responses=create_single_job_response("cancelled", "Successfully cancelled sync job"),
)
async def cancel_job(
    *,
    db: AsyncSession = Depends(deps.get_db),
    source_connection_id: UUID = Path(
        ..., description="The unique identifier of the source connection"
    ),
    job_id: UUID = Path(..., description="The unique identifier of the sync job to cancel"),
    ctx: ApiContext = Depends(deps.get_context),
) -> schemas.SourceConnectionJob:
    """Cancel a running sync job."""
    sync_job = await source_connection_service.get_source_connection_job(
        db=db, source_connection_id=source_connection_id, job_id=job_id, ctx=ctx
    )

    if sync_job.status not in [
        SyncJobStatus.CREATED,
        SyncJobStatus.PENDING,
        SyncJobStatus.IN_PROGRESS,
    ]:
        raise HTTPException(
            status_code=400, detail=f"Cannot cancel job in {sync_job.status} status"
        )

    from airweave.core.temporal_service import temporal_service

    if await temporal_service.is_temporal_enabled():
        try:
            cancelled = await temporal_service.cancel_sync_job_workflow(str(job_id))
            if cancelled:
                logger.info(f"Successfully sent cancellation signal for job {job_id}")
            else:
                logger.warning(f"No running Temporal workflow found for job {job_id}")
                from airweave.core.sync_job_service import sync_job_service as sjs

                if sync_job.status in [SyncJobStatus.IN_PROGRESS, SyncJobStatus.PENDING]:
                    await sjs.update_status(
                        sync_job_id=job_id,
                        status=SyncJobStatus.CANCELLED,
                        ctx=ctx,
                        error="Job cancelled by user",
                        failed_at=utc_now_naive(),
                    )
        except Exception as e:
            logger.error(f"Error cancelling Temporal workflow: {e}")
            raise HTTPException(status_code=500, detail="Failed to cancel workflow") from None
    else:
        await sync_job_service.update_status(
            sync_job_id=job_id,
            status=SyncJobStatus.CANCELLED,
            ctx=ctx,
            error="Job cancelled by user",
            failed_at=utc_now_naive(),
        )

    return await source_connection_service.get_source_connection_job(
        db=db, source_connection_id=source_connection_id, job_id=job_id, ctx=ctx
    )


@router.get("/{source_short_name}/oauth2_url", response_model=schemas.OAuth2AuthUrl)
async def get_oauth2_authorization_url(
    *,
    source_short_name: str = Path(
        ..., description="The source type identifier (e.g., 'google_drive', 'slack')"
    ),
    client_id: Optional[str] = Query(
        None, description="Optional custom OAuth client ID (for bring-your-own-credentials)"
    ),
) -> schemas.OAuth2AuthUrl:
    """Get the OAuth2 authorization URL for a source."""
    return await source_connection_service.get_oauth2_authorization_url(
        source_short_name=source_short_name, client_id=client_id
    )


@router.post(
    "/{source_short_name}/code_to_token_credentials",
    response_model=schemas.IntegrationCredentialInDB,
)
async def create_credentials_from_authorization_code(
    *,
    db: AsyncSession = Depends(deps.get_db),
    source_short_name: str = Path(
        ..., description="The source type identifier (e.g., 'google_drive', 'slack')"
    ),
    code: str = Query(..., description="The authorization code received from the OAuth callback"),
    credential_name: Optional[str] = Body(
        None, description="Custom name for the stored credential"
    ),
    credential_description: Optional[str] = Body(
        None, description="Description to help identify this credential"
    ),
    client_id: Optional[str] = Body(
        None, description="OAuth client ID (required for bring-your-own-credentials)"
    ),
    client_secret: Optional[str] = Body(
        None, description="OAuth client secret (required for bring-your-own-credentials)"
    ),
    ctx: ApiContext = Depends(deps.get_context),
) -> schemas.IntegrationCredentialInDB:
    """Exchange an OAuth2 authorization code for access credentials."""
    return await source_connection_service.create_credential_from_oauth2_code(
        db=db,
        source_short_name=source_short_name,
        code=code,
        credential_name=credential_name,
        credential_description=credential_description,
        client_id=client_id,
        client_secret=client_secret,
        ctx=ctx,
    )


@router.post(
    "/{source_connection_id}/make_continuous",
    response_model=schemas.SourceConnectionContinuousResponse,
)
async def make_source_connection_continuous_BETA(
    *,
    db: AsyncSession = Depends(deps.get_db),
    source_connection_id: UUID = Path(
        ..., description="The unique identifier of the source connection to convert"
    ),
    payload: schemas.SourceConnectionMakeContinuous = Body(...),
    ctx: ApiContext = Depends(deps.get_context),
    guard_rail: GuardRailService = Depends(deps.get_guard_rail_service),
    background_tasks: BackgroundTasks,
) -> schemas.SourceConnectionContinuousResponse:
    """Convert an existing source connection to continuous sync (BETA).

    Adds a minute-level schedule for incremental syncs and an optional daily cleanup schedule
    that performs a forced full sync for orphaned entity deletion.
    """
    # Permissions for scheduling and processing entities
    await guard_rail.is_allowed(ActionType.SYNCS)
    await guard_rail.is_allowed(ActionType.ENTITIES)

    # Load the existing source connection
    source_connection = await source_connection_service.get_source_connection(
        db=db, source_connection_id=source_connection_id, ctx=ctx
    )

    # Validate source supports continuous
    await _validate_continuous_source_by_short_name(source_connection.short_name)

    # Determine/validate cursor field
    cursor_field = await _determine_cursor_field_for_source(
        source_connection.short_name, payload.cursor_field
    )

    # Store cursor field (cursor_data left empty; first incremental run will populate it)
    async with get_db_context() as fresh_db:
        from airweave.core.sync_cursor_service import sync_cursor_service

        await sync_cursor_service.create_or_update_cursor(
            db=fresh_db,
            sync_id=source_connection.sync_id,
            cursor_data={},
            cursor_field=cursor_field,
            ctx=ctx,
        )

    # Create minute-level schedule and start it
    minute_level_cron = "*/1 * * * *"
    schedule_response = await _create_minute_level_schedule(
        source_connection, minute_level_cron, ctx
    )

    # Optionally create daily cleanup schedule
    if payload.enable_daily_cleanup:
        daily_cleanup_cron = "0 2 * * *"  # 2 AM daily
        try:
            async with get_db_context() as fresh_db:
                sync_model = await crud.sync.get(db=fresh_db, id=source_connection.sync_id, ctx=ctx)
                sync_dag_model = await crud.sync_dag.get_by_sync_id(
                    db=fresh_db, sync_id=source_connection.sync_id, ctx=ctx
                )

                collection = await crud.collection.get_by_readable_id(
                    db=fresh_db, readable_id=source_connection.collection, ctx=ctx
                )
                collection = schemas.Collection.model_validate(collection, from_attributes=True)

                source_connection_with_auth = await source_connection_service.get_source_connection(
                    db=fresh_db,
                    source_connection_id=source_connection.id,
                    show_auth_fields=True,
                    ctx=ctx,
                )

                sync_schema = schemas.Sync.model_validate(sync_model, from_attributes=True)
                sync_dag_schema = schemas.SyncDag.model_validate(
                    sync_dag_model, from_attributes=True
                )

                from airweave.core.temporal_service import temporal_service

                if await temporal_service.is_temporal_enabled():
                    from airweave.platform.temporal.schedule_service import (
                        temporal_schedule_service,
                    )

                    daily_schedule_id = (
                        await temporal_schedule_service.create_daily_cleanup_schedule(
                            sync_id=source_connection.sync_id,
                            cron_expression=daily_cleanup_cron,
                            sync_dict=sync_schema.model_dump(mode="json"),
                            sync_dag_dict=sync_dag_schema.model_dump(mode="json"),
                            collection_dict=collection.model_dump(mode="json"),
                            source_connection_dict=source_connection_with_auth.model_dump(
                                mode="json"
                            ),
                            user_dict={
                                "email": ctx.user.email if ctx.user else "api-key-user",
                                "organization": ctx.organization.model_dump(mode="json"),
                                "user": ctx.user.model_dump(mode="json") if ctx.user else None,
                                "auth_method": ctx.auth_method,
                                "auth_metadata": ctx.auth_metadata,
                                "request_id": ctx.request_id,
                            },
                            db=fresh_db,
                            ctx=ctx,
                        )
                    )

                    await temporal_schedule_service.resume_schedule(
                        schedule_id=daily_schedule_id,
                        sync_id=source_connection.sync_id,
                        user_dict={
                            "email": ctx.user.email if ctx.user else "api-key-user",
                            "organization": ctx.organization.model_dump(mode="json"),
                            "user": ctx.user.model_dump(mode="json") if ctx.user else None,
                            "auth_method": ctx.auth_method,
                            "auth_metadata": ctx.auth_metadata,
                            "request_id": ctx.request_id,
                        },
                        db=fresh_db,
                        ctx=ctx,
                    )
        except Exception as e:
            logger.error(
                f"Failed to create daily cleanup schedule for sync {source_connection.sync_id}: {e}"
            )

    # Optionally trigger an initial sync right away
    if payload.run_initial_sync:
        await _run_new_sync_job_for_connection(
            source_connection_id=source_connection_id,
            ctx=ctx,
            background_tasks=background_tasks,
        )
        await guard_rail.increment(ActionType.SYNCS)

    # Build response (include minute-level schedule details)
    response = schemas.SourceConnectionContinuousResponse.model_validate(source_connection)
    if schedule_response and schedule_response.schedule_id:
        response.minute_level_schedule = {
            "schedule_id": schedule_response.schedule_id,
            "cron_expression": minute_level_cron,
            "status": schedule_response.status,
            "message": (
                f"Continuous mode enabled. Incremental syncs run every "
                f"{minute_level_cron.split()[0]} minute(s)."
            ),
        }
    elif schedule_response:
        response.minute_level_schedule = {
            "schedule_id": None,
            "cron_expression": minute_level_cron,
            "status": "failed",
            "message": schedule_response.message,
        }

    return response


@router.get("/authorize/{code}")
async def resolve_authorize_code(
    *,
    db: AsyncSession = Depends(deps.get_db),
    code: str = Path(..., description="8-character pre-consent authorize code"),
):
    """Resolve the pre-consent authorize code into the PROVIDER OAuth URL.

    We keep it reusable until TTL expiry to allow user retries.
    """
    rs = await redirect_session.get_by_code(db, code)
    if not rs:
        raise HTTPException(status_code=404, detail="authorize code not found")

    if rs.expires_at <= datetime.now(timezone.utc):
        raise HTTPException(status_code=410, detail="authorize code expired")

    # Redirect to the provider's OAuth URL that was stored
    return RedirectResponse(url=rs.final_url, status_code=302)
