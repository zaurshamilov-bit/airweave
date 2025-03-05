"""API endpoints for Cursor development tooling.

These endpoints are only enabled when LOCAL_CURSOR_DEVELOPMENT is True.
"""

from typing import List

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app import crud, schemas
from app.api import deps
from app.core.config import settings
from app.core.shared_models import IntegrationType
from app.db.unit_of_work import UnitOfWork
from app.platform.sync.service import sync_service

router = APIRouter()


@router.get("/connections/status/{short_name}", response_model=List[schemas.Connection])
async def check_connection_status(
    *,
    db: AsyncSession = Depends(deps.get_db),
    short_name: str,
    user: schemas.User = Depends(deps.get_admin_user),
) -> List[schemas.Connection]:
    """Check if a source connection exists for the given short_name.

    Args:
    -----
        db: The database session
        short_name: The short name of the source to check
        user: The admin user

    Returns:
    --------
        List[schemas.Connection]: List of source connections for the given short_name

    Raises:
    -------
        HTTPException: If the endpoint is not enabled or no connections are found
    """
    if not settings.LOCAL_CURSOR_DEVELOPMENT:
        raise HTTPException(
            status_code=404,
            detail="This endpoint is only available when LOCAL_CURSOR_DEVELOPMENT is enabled",
        )

    # Find source connections for the given short_name
    connections = await crud.connection.get_all_by_short_name(
        db=db, short_name=short_name, current_user=user
    )

    # Filter for SOURCE connections only
    source_connections = [
        conn for conn in connections if conn.integration_type == IntegrationType.SOURCE
    ]

    if not source_connections:
        raise HTTPException(
            status_code=404,
            detail=f"No source connections found for source with short_name: {short_name}",
        )

    return source_connections


@router.post("/test-sync/{short_name}", response_model=schemas.SyncJob)
async def test_sync(
    *,
    db: AsyncSession = Depends(deps.get_db),
    short_name: str,
    background_tasks: BackgroundTasks,
    user: schemas.User = Depends(deps.get_admin_user),
) -> schemas.SyncJob:
    """Run a sync for a specific source by short_name.

    This endpoint is used for testing source integrations during development.
    It finds the first available source connection for the given short_name and
    runs a sync on it.

    Args:
    -----
        db: The database session
        short_name: The short name of the source to sync
        background_tasks: The background tasks
        user: The admin user

    Returns:
    --------
        schemas.SyncJob: The created sync job

    Raises:
    -------
        HTTPException: If no source connection is found for the short_name
    """
    if not settings.LOCAL_CURSOR_DEVELOPMENT:
        raise HTTPException(
            status_code=404,
            detail="This endpoint is only available when LOCAL_CURSOR_DEVELOPMENT is enabled",
        )

    # Find a source connection for the given short_name
    connections = await crud.connection.get_all_by_short_name(
        db=db, short_name=short_name, current_user=user
    )

    # Filter for SOURCE connections only
    source_connections = [
        conn for conn in connections if conn.integration_type == IntegrationType.SOURCE
    ]

    if not source_connections:
        raise HTTPException(
            status_code=404,
            detail=f"No source connections found for source with short_name: {short_name}",
        )

    # Use the first available connection
    source_connection = source_connections[0]

    # Find a sync for this source connection or create one if not found
    syncs = await crud.sync.get_all_for_source_connection(
        db=db, source_connection_id=source_connection.id, current_user=user
    )

    if syncs:
        sync = syncs[0]
    else:
        # Create a new sync
        async with UnitOfWork(db) as uow:
            # Find the default destination for testing
            destination_connections = await crud.connection.get_active_by_integration_type(
                db=db,
                integration_type=IntegrationType.DESTINATION,
                organization_id=user.organization_id,
            )

            if not destination_connections:
                raise HTTPException(status_code=404, detail="No destination connections found")

            # Create a sync using the first destination found
            sync_in = schemas.SyncCreate(
                name=f"Test Sync for {short_name}",
                source_connection_id=source_connection.id,
                destination_connection_id=destination_connections[0].id,
                enabled=True,
                schedule="manual",
            )

            sync = await sync_service.create(
                db=db, sync=sync_in.to_base(), current_user=user, uow=uow
            )
            await uow.session.flush()

    # Run the sync
    async with UnitOfWork(db) as uow:
        # Create a sync job
        sync_job_in = schemas.SyncJobCreate(sync_id=sync.id)
        sync_job = await crud.sync_job.create(db=db, obj_in=sync_job_in, current_user=user, uow=uow)

        # Get the DAG
        sync_dag = await crud.sync_dag.get_by_sync_id(db=db, sync_id=sync.id, current_user=user)

        # Convert models to schemas
        sync_schema = schemas.Sync.model_validate(sync)
        sync_job_schema = schemas.SyncJob.model_validate(sync_job)
        sync_dag_schema = schemas.SyncDag.model_validate(sync_dag)
        user_schema = schemas.User.model_validate(user)

        # Run the sync in background
        background_tasks.add_task(
            sync_service.run, sync_schema, sync_job_schema, sync_dag_schema, user_schema
        )

        await uow.session.flush()

    return schemas.SyncJob.model_validate(sync_job)
