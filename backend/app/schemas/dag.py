"""Schemas for DAG system."""

from enum import Enum
from typing import Dict, List, Optional
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


class NodeType(str, Enum):
    """Type of node."""

    source = "source"
    destination = "destination"
    transformer = "transformer"
    entity = "entity"


class DagNodeBase(BaseModel):
    """Base schema for DAG node.

    Sources, transformers, and destinations are also nodes, but they do not have an
    entity_definition_id.

    Entities are nodes that have an entity_definition_id but do not have a connection_id,
    or a config.
    """

    type: NodeType
    name: str
    config: Optional[Dict] = None

    # One of these will be set based on type
    connection_id: Optional[UUID] = None
    entity_definition_id: Optional[UUID] = None
    transformer_id: Optional[UUID] = None


class DagNodeCreate(DagNodeBase):
    """Schema for creating a DAG node."""

    id: Optional[UUID] = Field(
        default_factory=uuid4, description="Optional pre-set ID for the node"
    )


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


class SyncDagBase(BaseModel):
    """Base schema for sync DAG definition."""

    name: str
    description: Optional[str] = None
    sync_id: UUID


class SyncDagCreate(SyncDagBase):
    """Schema for creating a sync DAG definition."""

    nodes: List[DagNodeCreate]
    edges: List[DagEdgeCreate]


class SyncDagUpdate(SyncDagBase):
    """Schema for updating a sync DAG definition."""

    nodes: Optional[List[DagNodeCreate]] = None
    edges: Optional[List[DagEdgeCreate]] = None


class SyncDag(SyncDagBase):
    """Schema for a sync DAG definition.

    The DAG structure as the UI displays it.

    This means that for each entity, there is a node that is the producer and a node that is the
    consumer. These are connected by an edge: producer -edge-> entity -edge-> consumer

    Sources, transformers, and destinations are also nodes, but they do not have an
    entity_definition_id.

    Sources are producers by default, and destinations are consumers by default.
    Transformers are both producers and consumers.
    """

    id: UUID
    organization_id: UUID
    created_by_email: str
    modified_by_email: str
    nodes: list[DagNode]
    edges: list[DagEdge]

    def get_node(self, node_id: UUID) -> DagNode:
        """Get a node by ID."""
        for node in self.nodes:
            if node.id == node_id:
                return node
        raise ValueError(f"Node with ID {node_id} not found")

    def get_edges_from_node(self, node_id: UUID) -> list[DagEdge]:
        """Get an edge that points from a node."""
        edges = []
        for edge in self.edges:
            if edge.from_node_id == node_id:
                edges.append(edge)
        return edges

    def get_edges_to_node(self, node_id: UUID) -> list[DagEdge]:
        """Get an edge that points to a node."""
        edges = []
        for edge in self.edges:
            if edge.to_node_id == node_id:
                edges.append(edge)
        return edges

    def get_source_node(self) -> DagNode:
        """Get the source node."""
        for node in self.nodes:
            if node.type == NodeType.source:
                return node
        raise ValueError("No source node found")

    def get_destination_nodes(self) -> list[DagNode]:
        """Get all destination nodes."""
        return [node for node in self.nodes if node.type == NodeType.destination]

    class Config:
        """Pydantic config."""

        from_attributes = True
