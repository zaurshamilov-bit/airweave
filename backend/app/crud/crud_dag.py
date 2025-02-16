"""CRUD operations for DAG models."""

from typing import Optional
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.dag import (
    DagEdge,
    DagNode,
    SyncDagDefinition,
)
from app.models.user import User
from app.schemas.dag import (
    SyncDagDefinitionCreate,
    SyncDagDefinitionUpdate,
)

from ._base_organization import CRUDBaseOrganization


class CRUDSyncDagDefinition(
    CRUDBaseOrganization[SyncDagDefinition, SyncDagDefinitionCreate, SyncDagDefinitionUpdate]
):
    """CRUD operations for SyncDagDefinition."""

    async def create_with_nodes_and_edges(
        self,
        db: AsyncSession,
        *,
        obj_in: SyncDagDefinitionCreate,
        user: User,
    ) -> SyncDagDefinition:
        """Create a DAG with its nodes and edges."""
        # Create the DAG
        db_obj = await self.create(db, obj_in=obj_in, user=user)

        # Create nodes
        for node in obj_in.nodes:
            db_node = DagNode(
                **node.dict(),
                dag_id=db_obj.id,
                organization_id=user.organization_id,
                created_by_email=user.email,
                modified_by_email=user.email,
            )
            db.add(db_node)
        await db.flush()

        # Create edges
        for edge in obj_in.edges:
            db_edge = DagEdge(
                **edge.dict(),
                dag_id=db_obj.id,
                organization_id=user.organization_id,
                created_by_email=user.email,
                modified_by_email=user.email,
            )
            db.add(db_edge)

        await db.commit()
        await db.refresh(db_obj)

        # Reload with relationships
        result = await db.execute(
            select(SyncDagDefinition)
            .where(SyncDagDefinition.id == db_obj.id)
            .options(
                selectinload(SyncDagDefinition.nodes),
                selectinload(SyncDagDefinition.edges),
            )
        )
        return result.scalar_one()

    async def update_with_nodes_and_edges(
        self,
        db: AsyncSession,
        *,
        db_obj: SyncDagDefinition,
        obj_in: SyncDagDefinitionUpdate,
        user: User,
    ) -> SyncDagDefinition:
        """Update a DAG with its nodes and edges."""
        # Update DAG fields
        db_obj = await self.update(db, db_obj=db_obj, obj_in=obj_in, user=user)

        # If nodes provided, replace all nodes
        if obj_in.nodes is not None:
            # Delete existing nodes (cascade will handle edges)
            await db.execute(select(DagNode).where(DagNode.dag_id == db_obj.id).delete())
            # Create new nodes
            for node in obj_in.nodes:
                db_node = DagNode(
                    **node.model_dump(),
                    dag_id=db_obj.id,
                    organization_id=user.organization_id,
                    created_by_email=user.email,
                    modified_by_email=user.email,
                )
                db.add(db_node)
            await db.flush()

        # If edges provided, replace all edges
        if obj_in.edges is not None:
            # Delete existing edges
            await db.execute(select(DagEdge).where(DagEdge.dag_id == db_obj.id).delete())
            # Create new edges
            for edge in obj_in.edges:
                db_edge = DagEdge(
                    **edge.model_dump(),
                    dag_id=db_obj.id,
                    organization_id=user.organization_id,
                    created_by_email=user.email,
                    modified_by_email=user.email,
                )
                db.add(db_edge)

        await db.commit()
        await db.refresh(db_obj)

        # Reload with relationships
        result = await db.execute(
            select(SyncDagDefinition)
            .where(SyncDagDefinition.id == db_obj.id)
            .options(
                selectinload(SyncDagDefinition.nodes),
                selectinload(SyncDagDefinition.edges),
            )
        )
        return result.scalar_one()

    async def get_by_sync_id(
        self,
        db: AsyncSession,
        *,
        sync_id: UUID,
        user: User,
    ) -> Optional[SyncDagDefinition]:
        """Get a DAG by sync ID."""
        result = await db.execute(
            select(SyncDagDefinition)
            .where(
                SyncDagDefinition.sync_id == sync_id,
                SyncDagDefinition.organization_id == user.organization_id,
            )
            .options(
                selectinload(SyncDagDefinition.nodes),
                selectinload(SyncDagDefinition.edges),
            )
        )
        return result.scalar_one_or_none()


sync_dag_definition = CRUDSyncDagDefinition(SyncDagDefinition)
