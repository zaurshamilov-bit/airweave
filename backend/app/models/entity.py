"""Models for entities."""

from enum import Enum

from sqlalchemy import JSON, Column, ForeignKey, String, UniqueConstraint
from sqlalchemy import Enum as SQLEnum
from sqlalchemy.orm import relationship

from app.models._base import OrganizationBase, UserMixin


class EntityType(str, Enum):
    """Type of entity."""

    FILE = "file"
    JSON = "json"


class Entity(OrganizationBase, UserMixin):
    """An entity type that can be produced or consumed."""

    __tablename__ = "entity"

    name = Column(String, nullable=False)
    description = Column(String)
    type = Column(SQLEnum(EntityType), nullable=False)
    # For files: list of extensions, for JSON: JSON schema
    schema = Column(JSON, nullable=False)
    parent_id = Column(ForeignKey("entity.id"), nullable=True)

    # Relationships
    parent = relationship("Entity", remote_side=[id])
    children = relationship("Entity")

    __table_args__ = (UniqueConstraint("name", "organization_id", name="uq_entity_name_org"),)


class EntityRelation(OrganizationBase, UserMixin):
    """Relation between two entity types."""

    __tablename__ = "entity_relation"

    name = Column(String, nullable=False)
    description = Column(String)
    from_entity_id = Column(ForeignKey("entity.id"), nullable=False)
    to_entity_id = Column(ForeignKey("entity.id"), nullable=False)

    # Relationships
    from_entity = relationship("Entity", foreign_keys=[from_entity_id])
    to_entity = relationship("Entity", foreign_keys=[to_entity_id])
