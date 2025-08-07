"""The API module that contains the endpoints for embedding models."""

from fastapi import Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from airweave import crud, schemas
from airweave.api import deps
from airweave.api.context import ApiContext
from airweave.api.router import TrailingSlashRouter
from airweave.platform.configs._base import Fields
from airweave.platform.locator import resource_locator

router = TrailingSlashRouter()


@router.get("/detail/{short_name}", response_model=schemas.EmbeddingModelWithAuthenticationFields)
async def read_embedding_model(
    *,
    db: AsyncSession = Depends(deps.get_db),
    short_name: str,
    ctx: ApiContext = Depends(deps.get_context),
) -> schemas.EmbeddingModel:
    """Get embedding model by id.

    Args:
    ----
        db (AsyncSession): The database session.
        short_name (str): The short name of the embedding model.
        ctx (ApiContext): The current authentication context.

    Returns:
    -------
        schemas.EmbeddingModel: The embedding model object.

    """
    embedding_model = await crud.embedding_model.get_by_short_name(db, short_name)
    if not embedding_model:
        raise HTTPException(status_code=404, detail="Embedding model not found")
    if embedding_model.auth_config_class:
        auth_config_class = resource_locator.get_auth_config(embedding_model.auth_config_class)
        embedding_model.auth_fields = Fields.from_config_class(auth_config_class)
    return embedding_model


@router.get("/list", response_model=list[schemas.EmbeddingModel])
async def read_embedding_models(
    *,
    db: AsyncSession = Depends(deps.get_db),
    ctx: ApiContext = Depends(deps.get_context),
) -> list[schemas.EmbeddingModel]:
    """Get all embedding models.

    Args:
    ----
        db (AsyncSession): The database session.
        ctx (ApiContext): The current authentication context.

    Returns:
    -------
        list[schemas.EmbeddingModel]: The list of embedding models.

    """
    return await crud.embedding_model.get_all(db)
