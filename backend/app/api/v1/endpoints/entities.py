"""API endpoints for entity definitions and relations."""

from typing import List

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db
from app.crud.crud_entity import entity_definition, entity_relation
from app.models.user import User
from app.schemas.entity import (
    Entity,
    EntityCreate,
    EntityRelation,
    EntityRelationCreate,
    EntityRelationUpdate,
    EntityUpdate,
)

router = APIRouter()


@router.get("/definitions/", response_model=List[Entity])
async def list_entity_definitions(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List all entity definitions for the current user's organization."""
    return await entity_definition.get_multi_by_organization(
        db, organization_id=current_user.organization_id
    )


@router.post("/definitions/", response_model=Entity)
async def create_entity_definition(
    definition: EntityCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Create a new entity definition."""
    return await entity_definition.create(db, obj_in=definition, user=current_user)


@router.put("/definitions/{definition_id}", response_model=Entity)
async def update_entity_definition(
    definition_id: str,
    definition: EntityUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Update an entity definition."""
    db_obj = await entity_definition.get(db, id=definition_id)
    return await entity_definition.update(db, db_obj=db_obj, obj_in=definition, user=current_user)


@router.get("/relations/", response_model=List[EntityRelation])
async def list_entity_relations(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List all entity relations for the current user's organization."""
    return await entity_relation.get_multi_by_organization(
        db, organization_id=current_user.organization_id
    )


@router.post("/relations/", response_model=EntityRelation)
async def create_entity_relation(
    relation: EntityRelationCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Create a new entity relation."""
    return await entity_relation.create(db, obj_in=relation, user=current_user)


@router.put("/relations/{relation_id}", response_model=EntityRelation)
async def update_entity_relation(
    relation_id: str,
    relation: EntityRelationUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Update an entity relation."""
    db_obj = await entity_relation.get(db, id=relation_id)
    return await entity_relation.update(db, db_obj=db_obj, obj_in=relation, user=current_user)
