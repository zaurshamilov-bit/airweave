"""The API module that contains the endpoints for embedding models."""

from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app import crud, schemas
from app.api import deps

router = APIRouter()


@router.get("/{id}", response_model=schemas.EmbeddingModel)
async def read_embedding_model(
    *,
    db: AsyncSession = Depends(deps.get_db),
    id: UUID,
    user: schemas.User = Depends(deps.get_user),
) -> schemas.EmbeddingModel:
    """Get embedding model by id.

    Args:
    ----
        db (AsyncSession): The database session.
        id (UUID): The ID of the embedding model.
        user (schemas.User): The current user.

    Returns:
    -------
        schemas.EmbeddingModel: The embedding model object.

    """
    return await crud.embedding_model.get(db, id)


@router.get("/", response_model=list[schemas.EmbeddingModel])
async def read_embedding_models(
    *,
    db: AsyncSession = Depends(deps.get_db),
    user: schemas.User = Depends(deps.get_user),
) -> list[schemas.EmbeddingModel]:
    """Get all embedding models.

    Args:
    ----
        db (AsyncSession): The database session.
        user (schemas.User): The current user.

    Returns:
    -------
        list[schemas.EmbeddingModel]: The list of embedding models.

    """
    return await crud.embedding_model.get_multi(db)
