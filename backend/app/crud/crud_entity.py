"""CRUD operations for entity definitions and relations."""

from app.models.entity import EntityDefinition, EntityRelation
from app.schemas.entity import (
    EntityDefinitionCreate,
    EntityDefinitionUpdate,
    EntityRelationCreate,
    EntityRelationUpdate,
)

from ._base_organization import CRUDBaseOrganization
from ._base_system import CRUDBaseSystem


class CRUDEntityDefinition(
    CRUDBaseSystem[EntityDefinition, EntityDefinitionCreate, EntityDefinitionUpdate]
):
    """CRUD operations for Entity."""

    pass


class CRUDEntityRelation(
    CRUDBaseOrganization[EntityRelation, EntityRelationCreate, EntityRelationUpdate]
):
    """CRUD operations for EntityRelation."""

    pass


entity_definition = CRUDEntityDefinition(EntityDefinition)
entity_relation = CRUDEntityRelation(EntityRelation)
