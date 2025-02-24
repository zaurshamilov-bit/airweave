"""Models for the DAG system."""

from enum import Enum

from sqlalchemy import (
    JSON,
    UUID,
    Column,
    ForeignKey,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship

from ._base import OrganizationBase, UserMixin


class NodeType(str, Enum):
    """Type of node in a DAG."""

    SOURCE = "source"
    DESTINATION = "destination"
    TRANSFORMER = "transformer"
    ENTITY = "entity"


class SyncDagDefinition(OrganizationBase, UserMixin):
    """Definition of a sync DAG."""

    __tablename__ = "sync_dag_definition"

    name = Column(String, nullable=False)
    description = Column(String)
    sync_id = Column(UUID, ForeignKey("sync.id", ondelete="CASCADE"), nullable=False)

    __table_args__ = (UniqueConstraint("sync_id", name="uq_sync_dag_def_sync_id"),)

    nodes = relationship(
        "DagNode", back_populates="dag", lazy="selectin", cascade="all, delete-orphan"
    )
    edges = relationship(
        "DagEdge", back_populates="dag", lazy="selectin", cascade="all, delete-orphan"
    )


class DagNode(OrganizationBase, UserMixin):
    """Node in a DAG."""

    __tablename__ = "dag_node"

    dag_id = Column(UUID, ForeignKey("sync_dag_definition.id", ondelete="CASCADE"), nullable=False)
    type = Column(String, nullable=False)  # source, destination, transformer, entity
    name = Column(String, nullable=False)
    config = Column(JSON)  # Configuration for sources, destinations, transformers

    # Reference to the definition (one of these will be set based on type)
    connection_id = Column(UUID, ForeignKey("connection.id"), nullable=True)
    entity_definition_id = Column(UUID, ForeignKey("entity_definition.id"), nullable=True)

    # Relationships
    dag = relationship("SyncDagDefinition", back_populates="nodes", lazy="noload")
    outgoing_edges = relationship(
        "DagEdge",
        foreign_keys="[DagEdge.from_node_id]",
        back_populates="from_node",
        cascade="all, delete-orphan",
        lazy="noload",
    )
    incoming_edges = relationship(
        "DagEdge",
        foreign_keys="[DagEdge.to_node_id]",
        back_populates="to_node",
        cascade="all, delete-orphan",
        lazy="noload",
    )


class DagEdge(OrganizationBase, UserMixin):
    """Edge in a DAG."""

    __tablename__ = "dag_edge"

    dag_id = Column(UUID, ForeignKey("sync_dag_definition.id", ondelete="CASCADE"), nullable=False)
    from_node_id = Column(UUID, ForeignKey("dag_node.id", ondelete="CASCADE"), nullable=False)
    to_node_id = Column(UUID, ForeignKey("dag_node.id", ondelete="CASCADE"), nullable=False)

    # Relationships
    dag = relationship("SyncDagDefinition", back_populates="edges", lazy="noload")
    from_node = relationship(
        "DagNode",
        primaryjoin="DagEdge.from_node_id==DagNode.id",
        back_populates="outgoing_edges",
        lazy="noload",
    )
    to_node = relationship(
        "DagNode",
        primaryjoin="DagEdge.to_node_id==DagNode.id",
        back_populates="incoming_edges",
        lazy="noload",
    )

    __table_args__ = (
        UniqueConstraint("dag_id", "from_node_id", "to_node_id", name="uq_dag_edge_from_to"),
    )
