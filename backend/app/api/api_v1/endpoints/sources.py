"""The API module that contains the endpoints for sources."""

from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app import crud, schemas
from app.api import deps

router = APIRouter()


@router.get("/{id}", response_model=schemas.Source)
async def read_source(
    *,
    db: AsyncSession = Depends(deps.get_db),
    id: UUID,
    user: schemas.User = Depends(deps.get_user),
) -> schemas.Source:
    """Get source by id.

    Args:
    ----
        db (AsyncSession): The database session.
        id (UUID): The ID of the source.
        user (schemas.User): The current user.

    Returns:
    -------
        schemas.Source: The source object.

    """
    return await crud.source.get(db, id)


@router.get("/", response_model=schemas.Source)
async def read_sources(
    *,
    db: AsyncSession = Depends(deps.get_db),
    user: schemas.User = Depends(deps.get_user),
) -> schemas.Source:
    """Get all sources for the current user."""
    return await crud.source.get_multi(db, user=user)
