"""API endpoints for the DAG system."""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app import schemas
from app.api import deps
from app.core.dag_service import dag_service
from app.crud.crud_dag import (
    sync_dag_definition,
)
from app.models.user import User

router = APIRouter()


@router.get("/sync/{sync_id}/dag/", response_model=schemas.SyncDagDefinition)
async def get_sync_dag(
    sync_id: UUID,
    db: AsyncSession = Depends(deps.get_db),
    current_user: User = Depends(deps.get_user),
):
    """Get the DAG definition for a sync."""
    dag = await sync_dag_definition.get_by_sync_id(db, sync_id=sync_id, user=current_user)
    if not dag:
        raise HTTPException(status_code=404, detail="DAG not found")
    return dag


@router.post("/sync/{sync_id}/dag/", response_model=schemas.SyncDagDefinition)
async def create_sync_dag(
    sync_id: UUID,
    dag: schemas.SyncDagDefinitionCreate,
    db: AsyncSession = Depends(deps.get_db),
    current_user: User = Depends(deps.get_user),
):
    """Create a new DAG definition for a sync."""
    return await sync_dag_definition.create_with_nodes_and_edges(db, obj_in=dag, user=current_user)


@router.put("/sync/{sync_id}/dag/", response_model=schemas.SyncDagDefinition)
async def update_sync_dag(
    sync_id: UUID,
    dag: schemas.SyncDagDefinitionUpdate,
    db: AsyncSession = Depends(deps.get_db),
    current_user: User = Depends(deps.get_user),
):
    """Update a DAG definition for a sync."""
    db_dag = await sync_dag_definition.get_by_sync_id(db, sync_id=sync_id, user=current_user)
    if not db_dag:
        raise HTTPException(status_code=404, detail="DAG not found")

    return await sync_dag_definition.update_with_nodes_and_edges(
        db, db_obj=db_dag, obj_in=dag, user=current_user
    )


@router.get("/init", response_model=schemas.SyncDagDefinition)
async def initialize_dag(
    sync_id: UUID,
    db: AsyncSession = Depends(deps.get_db),
    current_user: User = Depends(deps.get_user),
) -> schemas.SyncDagDefinition:
    """Initialize a new DAG with source, entities, and destination."""
    dag = await dag_service.create_initial_dag(db, sync_id=sync_id, current_user=current_user)
    return dag
