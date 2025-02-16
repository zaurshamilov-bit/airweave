"""CRUD operations for entity definitions and relations."""

from app.models.entity import Entity, EntityRelation
from app.schemas.entity import (
    EntityCreate,
    EntityRelationCreate,
    EntityRelationUpdate,
    EntityUpdate,
)

from ._base_organization import CRUDBaseOrganization


class CRUDEntity(CRUDBaseOrganization[Entity, EntityCreate, EntityUpdate]):
    """CRUD operations for Entity."""

    pass


class CRUDEntityRelation(
    CRUDBaseOrganization[EntityRelation, EntityRelationCreate, EntityRelationUpdate]
):
    """CRUD operations for EntityRelation."""

    pass


entity_definition = CRUDEntity(Entity)
entity_relation = CRUDEntityRelation(EntityRelation)
