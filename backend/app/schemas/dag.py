"""Schemas for DAG system."""

from typing import Dict, List, Optional
from uuid import UUID

from pydantic import BaseModel, Field


class DagNodePosition(BaseModel):
    """Schema for node position in the UI."""

    x: float = Field(..., description="X coordinate")
    y: float = Field(..., description="Y coordinate")


class DagNodeBase(BaseModel):
    """Base schema for DAG node."""

    type: str  # source, destination, transformer, entity
    name: str
    config: Optional[Dict] = None
    position: Optional[DagNodePosition] = None

    # One of these will be set based on type
    source_id: Optional[UUID] = None
    destination_id: Optional[UUID] = None
    transformer_id: Optional[UUID] = None
    entity_definition_id: Optional[UUID] = None


class DagNodeCreate(DagNodeBase):
    """Schema for creating a DAG node."""

    pass


class DagNodeUpdate(DagNodeBase):
    """Schema for updating a DAG node."""

    pass


class DagNode(DagNodeBase):
    """Schema for a DAG node."""

    id: UUID
    dag_id: UUID
    organization_id: UUID
    created_by_email: str
    modified_by_email: str

    class Config:
        """Pydantic config."""

        from_attributes = True


class DagEdgeBase(BaseModel):
    """Base schema for DAG edge."""

    from_node_id: UUID
    to_node_id: UUID


class DagEdgeCreate(DagEdgeBase):
    """Schema for creating a DAG edge."""

    pass


class DagEdgeUpdate(DagEdgeBase):
    """Schema for updating a DAG edge."""

    pass


class DagEdge(DagEdgeBase):
    """Schema for a DAG edge."""

    id: UUID
    dag_id: UUID
    organization_id: UUID
    created_by_email: str
    modified_by_email: str

    class Config:
        """Pydantic config."""

        from_attributes = True


class SyncDagDefinitionBase(BaseModel):
    """Base schema for sync DAG definition."""

    name: str
    description: Optional[str] = None
    sync_id: UUID


class SyncDagDefinitionCreate(SyncDagDefinitionBase):
    """Schema for creating a sync DAG definition."""

    nodes: List[DagNodeCreate]
    edges: List[DagEdgeCreate]


class SyncDagDefinitionUpdate(SyncDagDefinitionBase):
    """Schema for updating a sync DAG definition."""

    nodes: Optional[List[DagNodeCreate]] = None
    edges: Optional[List[DagEdgeCreate]] = None


class SyncDagDefinition(SyncDagDefinitionBase):
    """Schema for a sync DAG definition."""

    id: UUID
    organization_id: UUID
    created_by_email: str
    modified_by_email: str
    nodes: List[DagNode]
    edges: List[DagEdge]

    class Config:
        """Pydantic config."""

        from_attributes = True
