"""API endpoints for managing source connections."""

from typing import List
from uuid import UUID

from fastapi import BackgroundTasks, Body, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from airweave import crud, schemas
from airweave.api import deps
from airweave.api.router import TrailingSlashRouter
from airweave.core.source_connection_service import source_connection_service
from airweave.core.sync_service import sync_service

router = TrailingSlashRouter()


@router.get("/", response_model=List[schemas.SourceConnection])
async def list_source_connections(
    *,
    db: AsyncSession = Depends(deps.get_db),
    skip: int = 0,
    limit: int = 100,
    user: schemas.User = Depends(deps.get_user),
) -> List[schemas.SourceConnection]:
    """List all source connections for the current user.

    Args:
        db: The database session
        skip: The number of connections to skip
        limit: The number of connections to return
        user: The current user

    Returns:
        A list of source connections
    """
    return await crud.source_connection.get_all_for_user(
        db=db, current_user=user, skip=skip, limit=limit
    )


@router.get("/{source_connection_id}", response_model=schemas.SourceConnection)
async def get_source_connection(
    *,
    db: AsyncSession = Depends(deps.get_db),
    source_connection_id: UUID,
    user: schemas.User = Depends(deps.get_user),
) -> schemas.SourceConnection:
    """Get a specific source connection by ID.

    Args:
        db: The database session
        source_connection_id: The ID of the source connection
        user: The current user

    Returns:
        The source connection
    """
    source_connection = await crud.source_connection.get(
        db=db, id=source_connection_id, current_user=user
    )
    if not source_connection:
        raise HTTPException(status_code=404, detail="Source connection not found")
    return source_connection


@router.post("/", response_model=schemas.SourceConnection)
async def create_source_connection(
    *,
    db: AsyncSession = Depends(deps.get_db),
    source_connection_in: schemas.SourceConnectionCreate = Body(...),
    user: schemas.User = Depends(deps.get_user),
    background_tasks: BackgroundTasks,
) -> schemas.SourceConnection:
    """Create a new source connection.

    This endpoint creates:
    1. An integration credential with the provided auth fields
    2. A collection if not provided
    3. The source connection
    4. A sync configuration and DAG
    5. A sync job if immediate execution is requested

    Args:
        db: The database session
        source_connection_in: The source connection to create
        user: The current user
        background_tasks: Background tasks for async operations

    Returns:
        The created source connection
    """
    source_connection, sync_job = await source_connection_service.create_source_connection(
        db=db, source_connection_in=source_connection_in, current_user=user
    )

    # If job was created and sync_immediately is True, start it in background
    if sync_job and source_connection_in.sync_immediately:
        sync_dag = await sync_service.get_sync_dag(
            db=db, sync_id=source_connection.sync_id, current_user=user
        )

        # Get the sync object
        sync = await crud.sync.get(db=db, id=source_connection.sync_id, current_user=user)

        background_tasks.add_task(sync_service.run, sync, sync_job, sync_dag, user)

    return source_connection


@router.put("/{source_connection_id}", response_model=schemas.SourceConnection)
async def update_source_connection(
    *,
    db: AsyncSession = Depends(deps.get_db),
    source_connection_id: UUID,
    source_connection_in: schemas.SourceConnectionUpdate = Body(...),
    user: schemas.User = Depends(deps.get_user),
) -> schemas.SourceConnection:
    """Update a source connection.

    Args:
        db: The database session
        source_connection_id: The ID of the source connection to update
        source_connection_in: The updated source connection data
        user: The current user

    Returns:
        The updated source connection
    """
    return await source_connection_service.update_source_connection(
        db=db,
        source_connection_id=source_connection_id,
        source_connection_in=source_connection_in,
        current_user=user,
    )


@router.delete("/{source_connection_id}", response_model=schemas.SourceConnection)
async def delete_source_connection(
    *,
    db: AsyncSession = Depends(deps.get_db),
    source_connection_id: UUID,
    delete_data: bool = False,
    user: schemas.User = Depends(deps.get_user),
) -> schemas.SourceConnection:
    """Delete a source connection and all related components.

    Args:
        db: The database session
        source_connection_id: The ID of the source connection to delete
        delete_data: Whether to delete the associated data in destinations
        user: The current user

    Returns:
        The deleted source connection
    """
    return await source_connection_service.delete_source_connection(
        db=db, source_connection_id=source_connection_id, current_user=user, delete_data=delete_data
    )


@router.post("/{source_connection_id}/run", response_model=schemas.SyncJob)
async def run_source_connection(
    *,
    db: AsyncSession = Depends(deps.get_db),
    source_connection_id: UUID,
    user: schemas.User = Depends(deps.get_user),
    background_tasks: BackgroundTasks,
) -> schemas.SyncJob:
    """Trigger a sync run for a source connection.

    Args:
        db: The database session
        source_connection_id: The ID of the source connection to run
        user: The current user
        background_tasks: Background tasks for async operations

    Returns:
        The created sync job
    """
    sync_job = await source_connection_service.run_source_connection(
        db=db, source_connection_id=source_connection_id, current_user=user
    )

    # Start the sync job in the background
    sync = await crud.sync.get(db=db, id=sync_job.sync_id, current_user=user, with_connections=True)
    sync_dag = await sync_service.get_sync_dag(db=db, sync_id=sync_job.sync_id, current_user=user)
    background_tasks.add_task(sync_service.run, sync, sync_job, sync_dag, user)

    return sync_job


@router.get("/{source_connection_id}/jobs", response_model=List[schemas.SyncJob])
async def list_source_connection_jobs(
    *,
    db: AsyncSession = Depends(deps.get_db),
    source_connection_id: UUID,
    user: schemas.User = Depends(deps.get_user),
) -> List[schemas.SyncJob]:
    """List all sync jobs for a source connection.

    Args:
        db: The database session
        source_connection_id: The ID of the source connection
        user: The current user

    Returns:
        A list of sync jobs
    """
    return await source_connection_service.get_source_connection_jobs(
        db=db, source_connection_id=source_connection_id, current_user=user
    )
