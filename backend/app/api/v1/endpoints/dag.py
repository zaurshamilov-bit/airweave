"""API endpoints for the DAG system."""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db
from app.crud.crud_dag import (
    sync_dag_definition,
)
from app.models.user import User
from app.schemas.dag import (
    SyncDagDefinition,
    SyncDagDefinitionCreate,
    SyncDagDefinitionUpdate,
)

router = APIRouter()


@router.get("/sync/{sync_id}/dag/", response_model=SyncDagDefinition)
async def get_sync_dag(
    sync_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get the DAG definition for a sync."""
    dag = await sync_dag_definition.get_by_sync_id(db, sync_id=sync_id, user=current_user)
    if not dag:
        raise HTTPException(status_code=404, detail="DAG not found")
    return dag


@router.post("/sync/{sync_id}/dag/", response_model=SyncDagDefinition)
async def create_sync_dag(
    sync_id: UUID,
    dag: SyncDagDefinitionCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Create a new DAG definition for a sync."""
    return await sync_dag_definition.create_with_nodes_and_edges(db, obj_in=dag, user=current_user)


@router.put("/sync/{sync_id}/dag/", response_model=SyncDagDefinition)
async def update_sync_dag(
    sync_id: UUID,
    dag: SyncDagDefinitionUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Update a DAG definition for a sync."""
    db_dag = await sync_dag_definition.get_by_sync_id(db, sync_id=sync_id, user=current_user)
    if not db_dag:
        raise HTTPException(status_code=404, detail="DAG not found")

    return await sync_dag_definition.update_with_nodes_and_edges(
        db, db_obj=db_dag, obj_in=dag, user=current_user
    )
