"""The API module that contains the endpoints for destinations."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app import crud, schemas
from app.api import deps
from app.platform.configs._base import Fields
from app.platform.locator import resources

router = APIRouter()


@router.get("/list", response_model=list[schemas.Destination])
async def list_destinations(
    db: AsyncSession = Depends(deps.get_db),
    user: schemas.User = Depends(deps.get_user),
) -> list[schemas.Destination]:
    """Get all available destinations."""
    destinations = await crud.destination.get_all(db)
    return destinations


@router.get("/{short_name}", response_model=schemas.DestinationWithConfigFields)
async def read_destination(
    *,
    db: AsyncSession = Depends(deps.get_db),
    short_name: str,
    user: schemas.User = Depends(deps.get_user),
) -> schemas.Destination:
    """Get destination by short name."""
    destination = await crud.destination.get_by_short_name(db, short_name)
    if not destination:
        raise HTTPException(status_code=404, detail="Destination not found")
    if destination.auth_config_class:
        auth_config_class = resources.get_auth_config(destination.auth_config_class)
        fields = Fields.from_config_class(auth_config_class)
        destination_with_config_fields = schemas.DestinationWithConfigFields.model_validate(
            destination, from_attributes=True
        )
        destination_with_config_fields.config_fields = fields
        return destination_with_config_fields
    return destination
