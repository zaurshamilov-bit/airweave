"""API endpoints for managing syncs."""

from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Body, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app import crud, schemas
from app.api import deps
from app.platform.sync.service import sync_service

router = APIRouter()

@router.get("/", response_model=list[schemas.Sync])
async def list_syncs(
    *,
    db: AsyncSession = Depends(deps.get_db),
    skip: int = 0,
    limit: int = 100,
    user: schemas.User = Depends(deps.get_user),
) -> list[schemas.Sync]:
    """List all syncs for the current user."""
    syncs = await crud.sync.get_all_for_user(
        db=db, current_user=user, skip=skip, limit=limit
    )
    return syncs

@router.get("/{sync_id}", response_model=schemas.Sync)
async def get_sync(
    *,
    db: AsyncSession = Depends(deps.get_db),
    sync_id: UUID,
    user: schemas.User = Depends(deps.get_user),
) -> schemas.Sync:
    """Get a specific sync by ID."""
    sync = await crud.sync.get(db=db, id=sync_id, current_user=user)
    if not sync:
        raise HTTPException(status_code=404, detail="Sync not found")
    return sync

@router.post("/", response_model=schemas.Sync)
async def create_sync(
    *,
    db: AsyncSession = Depends(deps.get_db),
    sync_in: schemas.SyncCreate = Body(...),
    user: schemas.User = Depends(deps.get_user),
    background_tasks: BackgroundTasks,
) -> schemas.Sync:
    """Create a new sync configuration."""
    sync = await sync_service.create(db=db, sync=sync_in.to_base(), current_user=user)

    if sync_in.run_immediately:
        sync_job = await crud.sync_job.create(db=db, sync=sync, current_user=user)
        # Add background task to run the sync
        sync_job_schema = schemas.SyncJob.model_validate(sync_job)
        sync_schema = schemas.Sync.model_validate(sync)
        background_tasks.add_task(sync_service.run, sync_schema, sync_job_schema, user)

    return sync

@router.delete("/{sync_id}", response_model=schemas.Sync)
async def delete_sync(
    *,
    db: AsyncSession = Depends(deps.get_db),
    sync_id: UUID,
    delete_data: bool = False,
    user: schemas.User = Depends(deps.get_user),
) -> schemas.Sync:
    """Delete a sync configuration and optionally its associated data."""
    sync = await crud.sync.get(db=db, id=sync_id, current_user=user)
    if not sync:
        raise HTTPException(status_code=404, detail="Sync not found")

    if delete_data:
        # TODO: Implement data deletion logic
        pass

    return await crud.sync.remove(db=db, id=sync_id, current_user=user)

@router.post("/{sync_id}/run", response_model=schemas.SyncJob)
async def run_sync(
    *,
    db: AsyncSession = Depends(deps.get_db),
    sync_id: UUID,
    user: schemas.User = Depends(deps.get_user),
    background_tasks: BackgroundTasks,
) -> schemas.SyncJob:
    """Trigger a sync run."""
    sync = await crud.sync.get(db=db, id=sync_id, current_user=user)
    sync_schema = schemas.Sync.model_validate(sync)

    if not sync:
        raise HTTPException(status_code=404, detail="Sync not found")

    sync_job_in = schemas.SyncJobCreate(sync_id=sync_id)
    sync_job = await crud.sync_job.create(db=db, obj_in=sync_job_in, current_user=user)
    sync_job_schema = schemas.SyncJob.model_validate(sync_job)

    await sync_service.run(sync_schema, sync_job_schema, user)

    # background_tasks.add_task(sync_service.run, sync_schema, sync_job_schema, user) # swap for redis queue

    return sync_job

@router.get("/{sync_id}/jobs", response_model=list[schemas.SyncJob])
async def list_sync_jobs(
    *,
    db: AsyncSession = Depends(deps.get_db),
    sync_id: UUID,
    skip: int = 0,
    limit: int = 100,
    user: schemas.User = Depends(deps.get_user),
) -> list[schemas.SyncJob]:
    """List all jobs for a specific sync."""
    sync = await crud.sync.get(db=db, id=sync_id, current_user=user)
    if not sync:
        raise HTTPException(status_code=404, detail="Sync not found")

    return await crud.sync_job.get_multi_by_sync(
        db=db, sync_id=sync_id, skip=skip, limit=limit
    )

@router.get("/{sync_id}/jobs/{job_id}", response_model=schemas.SyncJob)
async def get_sync_job(
    *,
    db: AsyncSession = Depends(deps.get_db),
    sync_id: UUID,
    job_id: UUID,
    user: schemas.User = Depends(deps.get_user),
) -> schemas.SyncJob:
    """Get details of a specific sync job."""
    sync_job = await crud.sync_job.get(db=db, id=job_id, current_user=user)
    if not sync_job or sync_job.sync_id != sync_id:
        raise HTTPException(status_code=404, detail="Sync job not found")
    return sync_job
