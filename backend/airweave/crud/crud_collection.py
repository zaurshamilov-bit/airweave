"""CRUD operations for collections."""

from typing import List, Optional
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from airweave import schemas
from airweave.crud._base import CRUDBase
from airweave.models.collection import Collection
from airweave.schemas.collection import CollectionCreate, CollectionStatus, CollectionUpdate


class CRUDCollection(CRUDBase[Collection, CollectionCreate, CollectionUpdate]):
    """CRUD operations for collections."""

    async def get_by_readable_id(
        self, db: AsyncSession, readable_id: str, current_user: schemas.User
    ) -> Optional[Collection]:
        """Get a collection by its readable ID."""
        result = await db.execute(select(Collection).where(Collection.readable_id == readable_id))
        db_obj = result.scalar_one_or_none()
        if db_obj is None:
            return None
        self._validate_if_user_has_permission(db_obj, current_user)
        return db_obj

    async def get_multi_by_organization(
        self, db: AsyncSession, organization_id: UUID, skip: int = 0, limit: int = 100
    ) -> List[Collection]:
        """Get all collections for a specific organization."""
        result = await db.execute(
            select(Collection)
            .where(Collection.organization_id == organization_id)
            .offset(skip)
            .limit(limit)
        )
        return list(result.scalars().all())

    async def update_status(
        self,
        db: AsyncSession,
        db_obj: Collection,
        status: CollectionStatus,
        current_user: schemas.User,
    ) -> Collection:
        """Update the status of a collection."""
        self._validate_if_user_has_permission(db_obj, current_user)
        db_obj.status = status
        db.add(db_obj)
        await db.commit()
        await db.refresh(db_obj)
        return db_obj


collection = CRUDCollection(Collection)
