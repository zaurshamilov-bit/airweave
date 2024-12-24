"""API endpoints for managing API keys."""

from uuid import UUID

from fastapi import APIRouter, Body, Depends, HTTPException
from sqlalchemy.orm import Session

from app import crud, schemas
from app.api import deps
from app.core.contexts import AppContext

router = APIRouter()


@router.post("/", response_model=schemas.APIKeyWithPlainKey)
async def create_api_key(
    *,
    db: Session = Depends(deps.get_db),
    api_key_in: schemas.APIKeyCreate = Body(...),

) -> schemas.APIKeyWithPlainKey:
    """Create a new API key for the current user.

    Returns a temporary plain key for the user to store securely.
    This is not stored in the database.

    Args:
    ----
        db (Session): The database session.
        api_key_in (schemas.APIKeyCreate): The API key creation data.
        app_context (AppContext): The application context.

    Returns:
    -------
        schemas.APIKeyWithPlainKey: The created API key object, including the key.

    """
    api_key_obj = await crud.api_key.create_with_user(
        db=db, obj_in=api_key_in, current_user=app_context.user
    )
    return api_key_obj


@router.get("/", response_model=schemas.APIKey)
async def read_api_key(
    *,
    db: Session = Depends(deps.get_db),
    id: UUID,
    app_context: AppContext = Depends(deps.get_app_context),
) -> schemas.APIKey:
    """Retrieve an API key by ID.

    Args:
    ----
        db (Session): The database session.
        id (UUID): The ID of the API key.
        app_context (AppContext): The application context.

    Returns:
    -------
        schemas.APIKey: The API key object.

    Raises:
    ------
        HTTPException: If the API key is not found.

    """
    api_key = await crud.api_key.get(db=db, id=id, current_user=app_context.user)
    if not api_key:
        raise HTTPException(status_code=404, detail="API key not found")
    return api_key


@router.get("/all", response_model=list[schemas.APIKey])
async def read_api_keys(
    *,
    db: Session = Depends(deps.get_db),
    skip: int = 0,
    limit: int = 100,
    app_context: AppContext = Depends(deps.get_app_context),
) -> list[schemas.APIKey]:
    """Retrieve all API keys for the current user.

    Args:
    ----
        db (Session): The database session.
        skip (int): Number of records to skip for pagination.
        limit (int): Maximum number of records to return.
        app_context (AppContext): The application context.

    Returns:
    -------
        List[schemas.APIKey]: A list of API keys.

    """
    api_keys = await crud.api_key.get_multi(
        db=db, skip=skip, limit=limit, current_user=app_context.user
    )
    return api_keys


@router.delete("/", response_model=schemas.APIKey)
async def delete_api_key(
    *,
    db: Session = Depends(deps.get_db),
    id: UUID,
    app_context: AppContext = Depends(deps.get_app_context),
) -> schemas.APIKey:
    """Delete an API key.

    Args:
    ----
        db (Session): The database session.
        id (UUID): The ID of the API key.
        app_context (AppContext): The application context.

    Returns:
    -------
        schemas.APIKey: The revoked API key object.

    Raises:
    ------
        HTTPException: If the API key is not found.

    """
    api_key = await crud.api_key.get(db=db, id=id, current_user=app_context.user)
    if not api_key:
        raise HTTPException(status_code=404, detail="API key not found")
    api_key = await crud.api_key.remove(db=db, id=id, current_user=app_context.user)
    return api_key
