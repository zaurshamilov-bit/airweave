"""The API module that contains the endpoints for destinations."""


from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app import crud, schemas
from app.api import deps
from app.core import credentials
from app.models.integration_credential import IntegrationType
from app.platform.configs._base import Fields
from app.platform.locator import resources

router = APIRouter()


@router.get("/{short_name}", response_model=schemas.DestinationWithConfigFields)
async def read_destination(
    *,
    db: AsyncSession = Depends(deps.get_db),
    short_name: str,
    user: schemas.User = Depends(deps.get_user),
) -> schemas.Destination:
    """Get destination by id.

    Args:
    ----
        db (AsyncSession): The database session.
        short_name (str): The short name of the destination.
        user (schemas.User): The current user.

    Returns:
    -------
        schemas.Destination: The destination object.
    """
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


@router.get("/", response_model=list[schemas.Destination])
async def read_destinations(
    *,
    db: AsyncSession = Depends(deps.get_db),
    user: schemas.User = Depends(deps.get_user),
) -> list[schemas.Destination]:
    """Get all destinations."""
    destinations = await crud.destination.get_multi(db)
    return destinations


@router.post("/connect/{short_name}", response_model=schemas.IntegrationCredential)
async def connect_to_destination(
    *,
    db: AsyncSession = Depends(deps.get_db),
    short_name: str,
    config_fields: dict,
    user: schemas.User = Depends(deps.get_user),
) -> schemas.IntegrationCredential:
    """Connect to a destination.

    Args:
    ----
        db (AsyncSession): The database session.
        short_name (str): The short name of the destination.
        config_fields (dict): The configuration fields.
        user (schemas.User): The current user.

    Returns:
    -------
        schemas.IntegrationCredential: The destination credential object.
    """
    destination = await crud.destination.get_by_short_name(db, short_name)
    if not destination:
        raise HTTPException(status_code=400, detail="Destination does not exist")

    auth_config_class = resources.get_auth_config(destination.auth_config_class)
    auth_config = auth_config_class(**config_fields)

    encrypted_credentials = credentials.encrypt(auth_config.model_dump())

    integration_credentials = schemas.IntegrationCredentialCreateEncrypted(
        name=f"{destination.name} - {user.email}",
        description=f"Credentials for {destination.name} - {user.email}",
        integration_short_name=destination.short_name,
        integration_type=IntegrationType.DESTINATION,
        auth_credential_type=destination.auth_config_class,
        encrypted_credentials=encrypted_credentials,
        auth_config_class=destination.auth_config_class,
    )

    integration_credentials = await crud.integration_credential.create(
        db, obj_in=integration_credentials, current_user=user
    )

    integration_credentials.decrypted_credentials = credentials.decrypt(
        integration_credentials.encrypted_credentials
    )

    return integration_credentials
