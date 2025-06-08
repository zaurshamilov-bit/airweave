"""Example endpoint patterns demonstrating AuthContext usage.

This file demonstrates the recommended patterns for using AuthContext
in FastAPI endpoints for both new implementations and backward compatibility.
"""

from typing import List

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from airweave import crud, schemas
from airweave.api.deps import get_auth_context, get_user
from airweave.db.session import get_db

router = APIRouter()


# New AuthContext Pattern (Recommended)
@router.get("/collections/", response_model=List[schemas.Collection])
async def list_collections_new(
    auth_context: schemas.AuthContext = Depends(get_auth_context),
    db: AsyncSession = Depends(get_db),
):
    """List all collections in current organization using AuthContext.

    This endpoint works with both Auth0 users and API keys.
    """
    return await crud.collection.get_multi(db, auth_context)


@router.post("/collections/", response_model=schemas.Collection)
async def create_collection_new(
    collection_data: schemas.CollectionCreate,
    auth_context: schemas.AuthContext = Depends(get_auth_context),
    db: AsyncSession = Depends(get_db),
):
    """Create a new collection using AuthContext.

    This endpoint works with both Auth0 users and API keys.
    Tracking fields will be populated appropriately based on auth method.
    """
    return await crud.collection.create(db, obj_in=collection_data, auth_context=auth_context)


# Backward Compatible Pattern (Legacy endpoints)
@router.get("/api-keys/", response_model=List[schemas.APIKey])
async def list_api_keys_legacy(
    current_user: schemas.User = Depends(get_user),
    db: AsyncSession = Depends(get_db),
):
    """List all API keys using legacy User dependency.

    This endpoint only works with Auth0 users, not API keys.
    Use this pattern for gradual migration of existing endpoints.
    """
    return await crud.api_key.get_multi(db, current_user=current_user, skip=0, limit=100)


# Mixed Pattern (for endpoints that need user context)
@router.get("/user/profile/", response_model=schemas.User)
async def get_user_profile(
    auth_context: schemas.AuthContext = Depends(get_auth_context),
    db: AsyncSession = Depends(get_db),
):
    """Get user profile - requires user context.

    This endpoint uses AuthContext but requires a user to be present.
    API key requests will fail appropriately.
    """
    if not auth_context.user:
        from fastapi import HTTPException

        raise HTTPException(status_code=401, detail="User context required for profile access")

    return auth_context.user


# Demonstration of auth method specific logic
@router.get("/debug/auth-info/")
async def get_auth_info(
    auth_context: schemas.AuthContext = Depends(get_auth_context),
):
    """Debug endpoint showing auth context information."""
    return {
        "auth_method": auth_context.auth_method,
        "organization_id": str(auth_context.organization_id),
        "has_user_context": auth_context.has_user_context,
        "tracking_email": auth_context.tracking_email,
        "is_api_key_auth": auth_context.is_api_key_auth,
        "is_user_auth": auth_context.is_user_auth,
        "auth_metadata": auth_context.auth_metadata,
        "user_id": str(auth_context.user_id) if auth_context.user_id else None,
    }
