"""CRUD operations for entity relations."""

from app.models.entity_relation import EntityRelation
from app.schemas.entity_relation import EntityRelationCreate, EntityRelationUpdate

from ._base_organization import CRUDBaseOrganization


class CRUDEntityRelation(
    CRUDBaseOrganization[EntityRelation, EntityRelationCreate, EntityRelationUpdate]
):
    """CRUD operations for Entity Relation."""

    pass


entity_relation = CRUDEntityRelation(EntityRelation)
