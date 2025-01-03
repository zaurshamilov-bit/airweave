"""The API module that contains the endpoints for sources."""


from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app import crud, schemas
from app.api import deps

router = APIRouter()


@router.get("/{short_name}", response_model=schemas.Source)
async def read_source(
    *,
    db: AsyncSession = Depends(deps.get_db),
    short_name: str,
    user: schemas.User = Depends(deps.get_user),
) -> schemas.Source:
    """Get source by id.

    Args:
    ----
        db (AsyncSession): The database session.
        short_name (str): The short name of the source.
        user (schemas.User): The current user.

    Returns:
    -------
        schemas.Source: The source object.

    """
    source = await crud.source.get_by_short_name(db, short_name)
    if not source:
        raise HTTPException(status_code=404, detail="Source not found")
    return source


@router.get("/", response_model=list[schemas.Source])
async def read_sources(
    *,
    db: AsyncSession = Depends(deps.get_db),
    user: schemas.User = Depends(deps.get_user),
) -> list[schemas.Source]:
    """Get all sources for the current user.

    Returns:
    -------
        list[schemas.Source]: The list of sources.

    """
    sources = await crud.source.get_all(db)
    return sources
