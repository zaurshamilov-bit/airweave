"""API endpoints for managing source connections."""

import urllib.parse
from datetime import datetime, timezone
from typing import List, Optional
from uuid import UUID

from fastapi import BackgroundTasks, Body, Depends, HTTPException, Path, Query
from fastapi.responses import RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession

from airweave import crud, schemas
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
from airweave.core.temporal_service import temporal_service
from airweave.crud import redirect_session
from airweave.db.session import get_db_context
from airweave.schemas.source_connection import (
    SourceConnectionInitiate,
    SourceConnectionInitiateResponse,
)

router = TrailingSlashRouter()


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

        if await temporal_service.is_temporal_enabled():
            await temporal_service.run_source_connection_workflow(
                sync=sync,
                sync_job=sync_job,
                sync_dag=sync_dag,
                collection=collection,
                source_connection=source_connection_with_auth,
                ctx=ctx,
                access_token=getattr(sync_job, "access_token", None),
            )
        else:
            background_tasks.add_task(
                sync_service.run,
                sync,
                sync_job,
                sync_dag,
                collection,
                source_connection_with_auth,
                ctx,
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
async def list_source_connections(
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
async def get_source_connection(
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
    return await source_connection_service.get_source_connection(
        db=db,
        source_connection_id=source_connection_id,
        show_auth_fields=show_auth_fields,
        ctx=ctx,
    )


@router.post("/", response_model=schemas.SourceConnection)
async def create_source_connection(
    *,
    db: AsyncSession = Depends(deps.get_db),
    source_connection_in: schemas.SourceConnectionCreate = Body(...),
    ctx: ApiContext = Depends(deps.get_context),
    guard_rail: GuardRailService = Depends(deps.get_guard_rail_service),
    background_tasks: BackgroundTasks,
) -> schemas.SourceConnection:
    """Create a new source connection to sync data into your collection."""
    await guard_rail.is_allowed(ActionType.SOURCE_CONNECTIONS)

    if source_connection_in.collection is None:
        await guard_rail.is_allowed(ActionType.COLLECTIONS)

    if source_connection_in.sync_immediately:
        await guard_rail.is_allowed(ActionType.SYNCS)
        await guard_rail.is_allowed(ActionType.ENTITIES)

    SOURCES_BLOCKED_FROM_AUTH_PROVIDERS = [
        "confluence",
        "jira",
        "bitbucket",
        "github",
        "ctti",
        "monday",
        "postgresql",
    ]

    if (
        source_connection_in.auth_provider
        and source_connection_in.short_name in SOURCES_BLOCKED_FROM_AUTH_PROVIDERS
    ):
        raise HTTPException(
            status_code=422,
            detail=(
                f"The {source_connection_in.short_name.title()} source cannot currently be created "
                f"using auth providers. Please provide credentials directly using the 'auth_fields'"
                f" parameter instead. Support for {source_connection_in.short_name.title()} through"
                f" auth providers is coming soon."
            ),
        )

    creating_new_collection = source_connection_in.collection is None

    source_connection, sync_job = await source_connection_service.create_source_connection(
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

            if await temporal_service.is_temporal_enabled():
                await temporal_service.run_source_connection_workflow(
                    sync=sync,
                    sync_job=sync_job,
                    sync_dag=sync_dag,
                    collection=collection,
                    source_connection=source_connection_with_auth,
                    ctx=ctx,
                )
            else:
                background_tasks.add_task(
                    sync_service.run,
                    sync,
                    sync_job,
                    sync_dag,
                    collection,
                    source_connection_with_auth,
                    ctx,
                )

            await guard_rail.increment(ActionType.SYNCS)

    return source_connection


@router.post("/internal/", response_model=schemas.SourceConnection)
async def create_source_connection_with_credential(
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

    source_connection, sync_job = await source_connection_service.create_source_connection(
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

            if await temporal_service.is_temporal_enabled():
                await temporal_service.run_source_connection_workflow(
                    sync=sync,
                    sync_job=sync_job,
                    sync_dag=sync_dag,
                    collection=collection,
                    source_connection=source_connection_with_auth,
                    ctx=ctx,
                )
            else:
                background_tasks.add_task(
                    sync_service.run,
                    sync,
                    sync_job,
                    sync_dag,
                    collection,
                    source_connection_with_auth,
                    ctx,
                )

            await guard_rail.increment(ActionType.SYNCS)

    return source_connection


async def _validate_continuous_source(
    source_connection_in: schemas.SourceConnectionCreateContinuous,
) -> None:
    """Validate that the source supports continuous sync."""
    SUPPORTED_CONTINUOUS_SOURCES = ["github", "postgresql"]

    if source_connection_in.short_name not in SUPPORTED_CONTINUOUS_SOURCES:
        raise HTTPException(
            status_code=422,
            detail=(
                f"The '{source_connection_in.short_name}' source is not yet supported "
                f"for continuous sync. Currently supported sources are: "
                f"{', '.join(SUPPORTED_CONTINUOUS_SOURCES)}. More sources will be added soon."
            ),
        )

    SOURCES_BLOCKED_FROM_AUTH_PROVIDERS = [
        "confluence",
        "jira",
        "bitbucket",
        "github",
        "ctti",
        "monday",
        "postgresql",
    ]

    if (
        source_connection_in.auth_provider
        and source_connection_in.short_name in SOURCES_BLOCKED_FROM_AUTH_PROVIDERS
    ):
        raise HTTPException(
            status_code=422,
            detail=(
                f"The {source_connection_in.short_name.title()} source cannot currently "
                f"be created using auth providers. Please provide credentials directly "
                f"using the 'auth_fields' parameter instead."
            ),
        )


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


@router.post("/continuous", response_model=schemas.SourceConnectionContinuousResponse)
async def create_continuous_source_connection_BETA(
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

    regular_create_data = {
        "name": source_connection_in.name,
        "description": source_connection_in.description,
        "short_name": source_connection_in.short_name,
        "config_fields": source_connection_in.config_fields,
        "collection": source_connection_in.collection,
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

    if cursor_field:
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
            if await temporal_service.is_temporal_enabled():
                await temporal_service.run_source_connection_workflow(
                    sync=sync,
                    sync_job=sync_job_initial,
                    sync_dag=sync_dag,
                    collection=collection,
                    source_connection=source_connection_with_auth,
                    ctx=ctx,
                )
            else:
                background_tasks.add_task(
                    sync_service.run,
                    sync,
                    sync_job_initial,
                    sync_dag,
                    collection,
                    source_connection_with_auth,
                    ctx,
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
        response.minute_level_schedule = {
            "schedule_id": schedule_response.schedule_id,
            "cron_expression": minute_level_cron,
            "status": "active",
            "message": (
                f"Initial sync started and schedule created successfully. "
                f"Incremental syncs will run every {minute_level_cron.split()[0]} minute(s). "
                f"Daily cleanup runs at 2 AM to remove orphaned entities."
            ),
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
async def update_source_connection(
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
async def delete_source_connection(
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
async def run_source_connection(
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

    if await temporal_service.is_temporal_enabled():
        await temporal_service.run_source_connection_workflow(
            sync=sync,
            sync_job=sync_job,
            sync_dag=sync_dag,
            collection=collection,
            source_connection=source_connection_with_auth,
            ctx=ctx,
            access_token=sync_job.access_token if hasattr(sync_job, "access_token") else None,
        )
    else:
        background_tasks.add_task(
            sync_service.run,
            sync,
            sync_job,
            sync_dag,
            collection,
            source_connection_with_auth,
            ctx,
            access_token=sync_job.access_token if hasattr(sync_job, "access_token") else None,
        )

    await guard_rail.increment(ActionType.SYNCS)

    return sync_job.to_source_connection_job(source_connection_id)


@router.get(
    "/{source_connection_id}/jobs",
    response_model=List[schemas.SourceConnectionJob],
    responses=create_job_list_response(["completed"], "Complete sync job history"),
)
async def list_source_connection_jobs(
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
async def get_source_connection_job(
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
async def cancel_source_connection_job(
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


@router.post("/initiate", response_model=SourceConnectionInitiateResponse)
async def initiate_source_connection(
    *,
    db: AsyncSession = Depends(deps.get_db),
    source_connection_in: SourceConnectionInitiate = Body(...),
    ctx: ApiContext = Depends(deps.get_context),
    guard_rail: GuardRailService = Depends(deps.get_guard_rail_service),
    background_tasks: BackgroundTasks,
) -> SourceConnectionInitiateResponse:
    """Unified initiation.

    - If non-OAuth or token injection ⇒ create now and return the SourceConnection
    - If OAuth ⇒ return BACKEND proxy auth URL (authorize/{code})
    """
    # ---- Parity with create_source_connection: preflight checks
    await guard_rail.is_allowed(ActionType.SOURCE_CONNECTIONS)
    creating_new_collection = source_connection_in.collection is None
    if creating_new_collection:
        await guard_rail.is_allowed(ActionType.COLLECTIONS)

    if source_connection_in.sync_immediately:
        await guard_rail.is_allowed(ActionType.SYNCS)
        await guard_rail.is_allowed(ActionType.ENTITIES)

    # ---- Same provider blocklist behavior as create_source_connection
    SOURCES_BLOCKED_FROM_AUTH_PROVIDERS = [
        "confluence",
        "jira",
        "bitbucket",
        "github",
        "ctti",
        "monday",
        "postgresql",
    ]
    if (
        source_connection_in.auth_provider
        and source_connection_in.short_name in SOURCES_BLOCKED_FROM_AUTH_PROVIDERS
    ):
        raise HTTPException(
            status_code=422,
            detail=(
                f"The {source_connection_in.short_name.title()} source cannot currently be created"
                f" using auth providers. Please provide credentials directly using the "
                f" 'auth_fields' parameter instead."
            ),
        )

    # ---- Service performs either immediate create or returns an auth URL + initiation id
    (
        init_id,
        auth_url,
        source_connection,
        sync_job,
    ) = await source_connection_service.initiate_connection(
        db=db, source_connection_in=source_connection_in, ctx=ctx
    )

    # ---- OAuth browser flow path: an auth_url was generated and a shell was created.
    # Guard rail increments for this flow will happen in the /callback endpoint.
    if auth_url:
        return SourceConnectionInitiateResponse(
            connection_init_id=init_id,
            authentication_url=auth_url,
            status="pending",
            source_connection=source_connection,  # Return the newly created shell
        )

    # ---- Immediate creation path: no auth_url, but a final connection object was created.
    elif source_connection:
        await guard_rail.increment(ActionType.SOURCE_CONNECTIONS)
        if creating_new_collection:
            await guard_rail.increment(ActionType.COLLECTIONS)

        # Kick off initial sync now if requested (same as create_source_connection)
        if sync_job and source_connection_in.sync_immediately:
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

                if await temporal_service.is_temporal_enabled():
                    await temporal_service.run_source_connection_workflow(
                        sync=sync,
                        sync_dag=sync_dag,
                        collection=collection,
                        source_connection=source_connection_with_auth,
                    )
                else:
                    background_tasks.add_task(
                        sync_service.run,
                        sync,
                        sync_job,
                        sync_dag,
                        collection,
                        source_connection_with_auth,
                        ctx,
                    )

                await guard_rail.increment(ActionType.SYNCS)

        return SourceConnectionInitiateResponse(
            connection_init_id=init_id,
            authentication_url=auth_url,
            status="created",
            source_connection=source_connection,
        )

    # Fallback in case something unexpected happens where no auth_url and no source_connection exist
    raise HTTPException(status_code=500, detail="Could not initiate source connection.")


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
