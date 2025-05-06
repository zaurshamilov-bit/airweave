"""API endpoints for collections."""

from typing import List, Optional

from fastapi import Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from airweave import crud, schemas
from airweave.api import deps
from airweave.api.router import TrailingSlashRouter
from airweave.models.user import User

router = TrailingSlashRouter()


@router.get("/", response_model=List[schemas.Collection])
async def list_collections(
    skip: int = 0,
    limit: int = 100,
    db: AsyncSession = Depends(deps.get_db),
    current_user: User = Depends(deps.get_user),
) -> List[schemas.Collection]:
    """List all collections for the current user's organization."""
    return await crud.collection.get_multi_by_organization(
        db, organization_id=current_user.organization_id, skip=skip, limit=limit
    )


@router.post("/", response_model=schemas.Collection)
async def create_collection(
    collection: schemas.CollectionCreate,
    db: AsyncSession = Depends(deps.get_db),
    current_user: User = Depends(deps.get_user),
) -> schemas.Collection:
    """Create a new collection."""
    return await crud.collection.create(db, obj_in=collection, current_user=current_user)


@router.get("/{readable_id}", response_model=schemas.Collection)
async def get_collection(
    readable_id: str,
    db: AsyncSession = Depends(deps.get_db),
    current_user: User = Depends(deps.get_user),
) -> schemas.Collection:
    """Get a specific collection by its readable ID."""
    db_obj = await crud.collection.get_by_readable_id(
        db, readable_id=readable_id, organization_id=current_user.organization_id
    )
    if db_obj is None:
        raise HTTPException(status_code=404, detail="Collection not found")
    return db_obj


@router.patch("/{readable_id}", response_model=schemas.Collection)
async def update_collection(
    readable_id: str,
    collection: schemas.CollectionUpdate,
    db: AsyncSession = Depends(deps.get_db),
    current_user: User = Depends(deps.get_user),
) -> schemas.Collection:
    """Update a collection by its readable ID."""
    db_obj = await crud.collection.get_by_readable_id(
        db, readable_id=readable_id, organization_id=current_user.organization_id
    )
    if db_obj is None:
        raise HTTPException(status_code=404, detail="Collection not found")
    return await crud.collection.update(
        db, db_obj=db_obj, obj_in=collection, current_user=current_user
    )


@router.delete("/{readable_id}", response_model=schemas.Collection)
async def delete_collection(
    readable_id: str,
    db: AsyncSession = Depends(deps.get_db),
    current_user: User = Depends(deps.get_user),
) -> schemas.Collection:
    """Delete a collection by its readable ID."""
    db_obj = await crud.collection.get_by_readable_id(
        db, readable_id=readable_id, organization_id=current_user.organization_id
    )
    if db_obj is None:
        raise HTTPException(status_code=404, detail="Collection not found")
    return await crud.collection.remove(db, id=db_obj.id, current_user=current_user)


@router.get("/{readable_id}/search", response_model=List[dict])
async def search_collection(
    readable_id: str,
    query: str = Query(..., description="Search query"),
    source_name: Optional[str] = Query(None, description="Optional source name filter"),
    limit: int = Query(10, description="Number of results to return"),
    offset: int = Query(0, description="Pagination offset"),
    db: AsyncSession = Depends(deps.get_db),
    current_user: User = Depends(deps.get_user),
) -> List[dict]:
    """Search within a collection identified by readable ID."""
    db_obj = await crud.collection.get_by_readable_id(
        db, readable_id=readable_id, organization_id=current_user.organization_id
    )
    if db_obj is None:
        raise HTTPException(status_code=404, detail="Collection not found")

    # search_query = schemas.CollectionSearchQuery(
    #     query=query, source_name=source_name, limit=limit, offset=offset
    # )

    # Note: This would require additional implementation for the actual search functionality
    # This is just a placeholder that follows the schema defined in collection.py
    return []  # Replace with actual search implementation
