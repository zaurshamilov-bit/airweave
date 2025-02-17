"""CRUD operations for entity definitions and relations."""

from typing import List
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

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

    async def get_multi_by_ids(
        self, db: AsyncSession, *, ids: List[UUID]
    ) -> List[EntityDefinition]:
        """Get multiple entity definitions by their IDs.

        Args:
            db (AsyncSession): The database session
            ids (List[UUID]): List of entity definition IDs to fetch

        Returns:
            List[EntityDefinition]: List of found entity definitions
        """
        result = await db.execute(select(self.model).where(self.model.id.in_(ids)))
        return list(result.unique().scalars().all())


class CRUDEntityRelation(
    CRUDBaseOrganization[EntityRelation, EntityRelationCreate, EntityRelationUpdate]
):
    """CRUD operations for EntityRelation."""

    pass


entity_definition = CRUDEntityDefinition(EntityDefinition)
entity_relation = CRUDEntityRelation(EntityRelation)
