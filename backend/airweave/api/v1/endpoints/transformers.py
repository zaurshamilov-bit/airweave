"""API endpoints for transformers."""

from typing import List

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from airweave.api import deps
from airweave.api.router import TrailingSlashRouter
from airweave.crud.crud_transformer import transformer
from airweave.schemas.auth import AuthContext
from airweave.schemas.transformer import Transformer, TransformerCreate, TransformerUpdate

router = TrailingSlashRouter()


@router.get("/", response_model=List[Transformer])
async def list_transformers(
    db: AsyncSession = Depends(deps.get_db),
    auth_context: AuthContext = Depends(deps.get_auth_context),
):
    """List all transformers for the current user's organization."""
    return await transformer.get_multi(db, organization_id=auth_context.user.organization_id)


@router.post("/", response_model=Transformer)
async def create_transformer(
    transformer_in: TransformerCreate,
    db: AsyncSession = Depends(deps.get_db),
    auth_context: AuthContext = Depends(deps.get_auth_context),
):
    """Create a new transformer."""
    return await transformer.create(db, obj_in=transformer_in, auth_context=auth_context)


@router.put("/{transformer_id}", response_model=Transformer)
async def update_transformer(
    transformer_id: str,
    transformer_in: TransformerUpdate,
    db: AsyncSession = Depends(deps.get_db),
    auth_context: AuthContext = Depends(deps.get_auth_context),
):
    """Update a transformer."""
    db_obj = await transformer.get(db, id=transformer_id)
    return await transformer.update(
        db, db_obj=db_obj, obj_in=transformer_in, auth_context=auth_context
    )
