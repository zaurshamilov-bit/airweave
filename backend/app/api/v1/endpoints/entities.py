"""API endpoints for entity definitions and relations."""

from typing import List
from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api import deps
from app.crud.crud_entity import entity_definition, entity_relation
from app.models.user import User
from app.schemas.entity import (
    EntityDefinition,
    EntityDefinitionCreate,
    EntityDefinitionUpdate,
    EntityRelation,
    EntityRelationCreate,
    EntityRelationUpdate,
)

router = APIRouter()


@router.get("/definitions/", response_model=List[EntityDefinition])
async def list_entity_definitions(
    db: AsyncSession = Depends(deps.get_db),
    current_user: User = Depends(deps.get_user),
) -> List[EntityDefinition]:
    """List all entity definitions for the current user's organization."""
    return await entity_definition.get_multi_by_organization(
        db, organization_id=current_user.organization_id
    )


@router.post("/definitions/", response_model=EntityDefinition)
async def create_entity_definition(
    definition: EntityDefinitionCreate,
    db: AsyncSession = Depends(deps.get_db),
    current_user: User = Depends(deps.get_user),
) -> EntityDefinition:
    """Create a new entity definition."""
    return await entity_definition.create(db, obj_in=definition, user=current_user)


@router.put("/definitions/{definition_id}", response_model=EntityDefinition)
async def update_entity_definition(
    definition_id: UUID,
    definition: EntityDefinitionUpdate,
    db: AsyncSession = Depends(deps.get_db),
    current_user: User = Depends(deps.get_user),
) -> EntityDefinition:
    """Update an entity definition."""
    db_obj = await entity_definition.get(db, id=definition_id)
    return await entity_definition.update(db, db_obj=db_obj, obj_in=definition, user=current_user)


@router.get("/relations/", response_model=List[EntityRelation])
async def list_entity_relations(
    db: AsyncSession = Depends(deps.get_db),
    current_user: User = Depends(deps.get_user),
) -> List[EntityRelation]:
    """List all entity relations for the current user's organization."""
    return await entity_relation.get_multi_by_organization(
        db, organization_id=current_user.organization_id
    )


@router.post("/relations/", response_model=EntityRelation)
async def create_entity_relation(
    relation: EntityRelationCreate,
    db: AsyncSession = Depends(deps.get_db),
    current_user: User = Depends(deps.get_user),
) -> EntityRelation:
    """Create a new entity relation."""
    return await entity_relation.create(db, obj_in=relation, user=current_user)


@router.put("/relations/{relation_id}", response_model=EntityRelation)
async def update_entity_relation(
    relation_id: UUID,
    relation: EntityRelationUpdate,
    db: AsyncSession = Depends(deps.get_db),
    current_user: User = Depends(deps.get_user),
) -> EntityRelation:
    """Update an entity relation."""
    db_obj = await entity_relation.get(db, id=relation_id)
    return await entity_relation.update(db, db_obj=db_obj, obj_in=relation, user=current_user)


@router.post("/definitions/by-ids/", response_model=List[EntityDefinition])
async def get_entity_definitions_by_ids(
    ids: List[UUID],
    db: AsyncSession = Depends(deps.get_db),
    current_user: User = Depends(deps.get_user),
) -> List[EntityDefinition]:
    """Get multiple entity definitions by their IDs.

    Args:
        ids: List of entity definition IDs to fetch
        db: Database session
        current_user: Current authenticated user

    Returns:
        List of entity definitions matching the provided IDs
    """
    return await entity_definition.get_multi_by_ids(db, ids=ids)
