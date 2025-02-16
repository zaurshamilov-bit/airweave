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
    sync_id = Column(UUID, ForeignKey("sync.id"), nullable=False)

    # Relationships
    sync = relationship("Sync", back_populates="dag_definition")
    nodes = relationship("DagNode", back_populates="dag", cascade="all, delete-orphan")
    edges = relationship("DagEdge", back_populates="dag", cascade="all, delete-orphan")

    __table_args__ = (UniqueConstraint("sync_id", name="uq_sync_dag_def_sync_id"),)


class DagNode(OrganizationBase, UserMixin):
    """Node in a DAG."""

    __tablename__ = "dag_node"

    dag_id = Column(UUID, ForeignKey("sync_dag_definition.id"), nullable=False)
    type = Column(String, nullable=False)  # source, destination, transformer, entity
    name = Column(String, nullable=False)
    config = Column(JSON)  # Configuration for sources, destinations, transformers

    # Reference to the definition (one of these will be set based on type)
    source_id = Column(UUID, ForeignKey("source.id"), nullable=True)
    destination_id = Column(UUID, ForeignKey("destination.id"), nullable=True)
    transformer_id = Column(UUID, ForeignKey("transformer.id"), nullable=True)
    entity_id = Column(UUID, ForeignKey("entity.id"), nullable=True)

    # Position in the UI
    position_x = Column(String)
    position_y = Column(String)

    # Relationships
    dag = relationship("SyncDagDefinition", back_populates="nodes")
    source = relationship("Source")
    destination = relationship("Destination")
    transformer = relationship("Transformer")
    entity = relationship("Entity")
    outgoing_edges = relationship(
        "DagEdge",
        foreign_keys="[DagEdge.from_node_id]",
        back_populates="from_node",
        cascade="all, delete-orphan",
    )
    incoming_edges = relationship(
        "DagEdge",
        foreign_keys="[DagEdge.to_node_id]",
        back_populates="to_node",
        cascade="all, delete-orphan",
    )


class DagEdge(OrganizationBase, UserMixin):
    """Edge in a DAG."""

    __tablename__ = "dag_edge"

    dag_id = Column(UUID, ForeignKey("sync_dag_definition.id"), nullable=False)
    from_node_id = Column(UUID, ForeignKey("dag_node.id"), nullable=False)
    to_node_id = Column(UUID, ForeignKey("dag_node.id"), nullable=False)

    # Relationships
    dag = relationship("SyncDagDefinition", back_populates="edges")
    from_node = relationship(
        "DagNode", foreign_keys=[from_node_id], back_populates="outgoing_edges"
    )
    to_node = relationship("DagNode", foreign_keys=[to_node_id], back_populates="incoming_edges")

    __table_args__ = (
        UniqueConstraint("dag_id", "from_node_id", "to_node_id", name="uq_dag_edge_from_to"),
    )
