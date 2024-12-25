"""The API module that contains the endpoints for destinations."""

from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app import crud, schemas
from app.api import deps

router = APIRouter()


@router.get("/{id}", response_model=schemas.Destination)
async def read_destination(
    *,
    db: AsyncSession = Depends(deps.get_db),
    id: UUID,
    user: schemas.User = Depends(deps.get_user),
) -> schemas.Destination:
    """Get destination by id."""
    return await crud.destination.get(db, id)


@router.get("/", response_model=list[schemas.Destination])
async def read_destinations(
    *,
    db: AsyncSession = Depends(deps.get_db),
    user: schemas.User = Depends(deps.get_user),
) -> list[schemas.Destination]:
    """Get all destinations."""
    return await crud.destination.get_multi(db)
