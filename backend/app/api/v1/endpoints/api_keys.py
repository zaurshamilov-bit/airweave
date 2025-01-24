"""API endpoints for managing API keys."""

from uuid import UUID

from fastapi import APIRouter, Body, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app import crud, schemas
from app.api import deps

router = APIRouter()


@router.post("/", response_model=schemas.APIKeyWithPlainKey)
async def create_api_key(
    *,
    db: AsyncSession = Depends(deps.get_db),
    api_key_in: schemas.APIKeyCreate = Body(...),
    user: schemas.User = Depends(deps.get_user),
) -> schemas.APIKeyWithPlainKey:
    """Create a new API key for the current user.

    Returns a temporary plain key for the user to store securely.
    This is not stored in the database.

    Args:
    ----
        db (AsyncSession): The database session.
        api_key_in (schemas.APIKeyCreate): The API key creation data.
        user (schemas.User): The current user.

    Returns:
    -------
        schemas.APIKeyWithPlainKey: The created API key object, including the key.

    """
    api_key_obj = await crud.api_key.create_with_user(db=db, obj_in=api_key_in, current_user=user)
    return api_key_obj


@router.get("/{id}", response_model=schemas.APIKey)
async def read_api_key(
    *,
    db: AsyncSession = Depends(deps.get_db),
    id: UUID,
    user: schemas.User = Depends(deps.get_user),
) -> schemas.APIKey:
    """Retrieve an API key by ID.

    Args:
    ----
        db (AsyncSession): The database session.
        id (UUID): The ID of the API key.
        user (schemas.User): The current user.

    Returns:
    -------
        schemas.APIKey: The API key object.

    Raises:
    ------
        HTTPException: If the API key is not found.

    """
    api_key = await crud.api_key.get(db=db, id=id, current_user=user)
    if not api_key:
        raise HTTPException(status_code=404, detail="API key not found")
    return api_key


@router.get("/", response_model=list[schemas.APIKey])
async def read_api_keys(
    *,
    db: AsyncSession = Depends(deps.get_db),
    skip: int = 0,
    limit: int = 100,
    user: schemas.User = Depends(deps.get_user),
) -> list[schemas.APIKey]:
    """Retrieve all API keys for the current user.

    Args:
    ----
        db (AsyncSession): The database session.
        skip (int): Number of records to skip for pagination.
        limit (int): Maximum number of records to return.
        user (schemas.User): The current user.

    Returns:
    -------
        List[schemas.APIKey]: A list of API keys.

    """
    api_keys = await crud.api_key.get_all_for_user(db=db, skip=skip, limit=limit, current_user=user)
    return api_keys


@router.delete("/", response_model=schemas.APIKey)
async def delete_api_key(
    *,
    db: AsyncSession = Depends(deps.get_db),
    id: UUID,
    user: schemas.User = Depends(deps.get_user),
) -> schemas.APIKey:
    """Delete an API key.

    Args:
    ----
        db (AsyncSession): The database session.
        id (UUID): The ID of the API key.
        user (schemas.User): The current user.

    Returns:
    -------
        schemas.APIKey: The revoked API key object.

    Raises:
    ------
        HTTPException: If the API key is not found.

    """
    api_key = await crud.api_key.get(db=db, id=id, current_user=user)
    if not api_key:
        raise HTTPException(status_code=404, detail="API key not found")
    api_key = await crud.api_key.remove(db=db, id=id, current_user=user)
    return api_key
