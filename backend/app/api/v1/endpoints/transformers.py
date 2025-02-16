"""API endpoints for transformers."""

from typing import List

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db
from app.crud.crud_transformer import transformer
from app.models.user import User
from app.schemas.transformer import Transformer, TransformerCreate, TransformerUpdate

router = APIRouter()


@router.get("/", response_model=List[Transformer])
async def list_transformers(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List all transformers for the current user's organization."""
    return await transformer.get_multi_by_organization(
        db, organization_id=current_user.organization_id
    )


@router.post("/", response_model=Transformer)
async def create_transformer(
    transformer_in: TransformerCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Create a new transformer."""
    return await transformer.create(db, obj_in=transformer_in, user=current_user)


@router.put("/{transformer_id}", response_model=Transformer)
async def update_transformer(
    transformer_id: str,
    transformer_in: TransformerUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Update a transformer."""
    db_obj = await transformer.get(db, id=transformer_id)
    return await transformer.update(db, db_obj=db_obj, obj_in=transformer_in, user=current_user)
