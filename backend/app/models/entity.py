"""Models for entities."""

from enum import Enum

from sqlalchemy import JSON, Column, ForeignKey, String, UniqueConstraint
from sqlalchemy import Enum as SQLEnum
from sqlalchemy.orm import backref, relationship

from app.models._base import Base


class EntityType(str, Enum):
    """Type of entity."""

    FILE = "file"
    JSON = "json"


class EntityDefinition(Base):
    """An entity type that can be produced or consumed."""

    __tablename__ = "entity_definition"

    name = Column(String, nullable=False)
    description = Column(String)
    type = Column(SQLEnum(EntityType), nullable=False)
    # For files: list of extensions, for JSON: JSON schema
    schema = Column(JSON, nullable=False)
    parent_id = Column(ForeignKey("entity_definition.id"), nullable=True)

    organization_id = Column(ForeignKey("organization.id"), nullable=True)

    # Relationships
    parent = relationship(
        "EntityDefinition", backref=backref("children"), remote_side="[EntityDefinition.id]"
    )

    __table_args__ = (
        UniqueConstraint("name", "organization_id", name="uq_entity_definition_name_org"),
    )


class EntityRelation(Base):
    """Relation between two entity types."""

    __tablename__ = "entity_relation"

    name = Column(String, nullable=False)
    description = Column(String)
    from_entity_id = Column(ForeignKey("entity_definition.id"), nullable=False)
    to_entity_id = Column(ForeignKey("entity_definition.id"), nullable=False)
    organization_id = Column(ForeignKey("organization.id"), nullable=True)

    # Relationships
    from_entity = relationship("EntityDefinition", foreign_keys=[from_entity_id])
    to_entity = relationship("EntityDefinition", foreign_keys=[to_entity_id])
