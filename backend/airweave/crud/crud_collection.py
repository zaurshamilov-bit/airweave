"""CRUD operations for collections."""

from typing import List, Optional
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from airweave import schemas
from airweave.core.shared_models import CollectionStatus, SourceConnectionStatus
from airweave.crud._base import CRUDBase
from airweave.crud.crud_source_connection import source_connection as crud_source_connection
from airweave.models.collection import Collection
from airweave.schemas.collection import CollectionCreate, CollectionUpdate


class CRUDCollection(CRUDBase[Collection, CollectionCreate, CollectionUpdate]):
    """CRUD operations for collections."""

    async def _compute_collection_status(
        self, db: AsyncSession, collection: Collection, current_user: schemas.User
    ) -> CollectionStatus:
        """Compute the ephemeral status of a collection based on its source connections.

        Logic:
        - If no source connections: NEEDS_SOURCE
        - If all source connections are failing: ERROR
        - If some source connections are failing: PARTIAL_ERROR
        - If any source connection is in progress: ACTIVE (this is considered an OK state)
        - Otherwise: ACTIVE

        Args:
            db: The database session
            collection: The collection
            current_user: Current user for authorization

        Returns:
            The computed ephemeral status
        """
        # Get all source connections for this collection
        source_connections = await crud_source_connection.get_for_collection(
            db, readable_collection_id=collection.readable_id, current_user=current_user
        )

        # If no source connections, the collection needs one
        if not source_connections:
            return CollectionStatus.NEEDS_SOURCE

        # Count the number of failing source connections
        failing_count = 0
        in_progress_count = 0

        for sc in source_connections:
            if sc.status == SourceConnectionStatus.FAILING:
                failing_count += 1
            elif sc.status == SourceConnectionStatus.IN_PROGRESS:
                in_progress_count += 1

        # If any are in progress, the collection is active (in progress is considered an OK state)
        if in_progress_count > 0:
            return CollectionStatus.ACTIVE

        # If all are failing, the collection is in error
        if failing_count == len(source_connections):
            return CollectionStatus.ERROR

        # If some but not all are failing, the collection is in partial error
        if failing_count > 0:
            return CollectionStatus.PARTIAL_ERROR

        # Otherwise, the collection is active
        return CollectionStatus.ACTIVE

    async def _attach_ephemeral_status(
        self, db: AsyncSession, collections: List[Collection], current_user: schemas.User
    ) -> List[Collection]:
        """Attach ephemeral status to collections.

        Args:
            db: The database session
            collections: The collections to process
            current_user: Current user for authorization

        Returns:
            Collections with computed status
        """
        if not collections:
            return []

        for collection in collections:
            # Compute and set the ephemeral status
            collection.status = await self._compute_collection_status(db, collection, current_user)

        return collections

    async def get(
        self, db: AsyncSession, id: UUID, current_user: schemas.User
    ) -> Optional[Collection]:
        """Get a collection by its ID with computed ephemeral status."""
        # Get the collection using the parent method
        collection = await super().get(db, id=id, current_user=current_user)

        if collection:
            # Compute and set the ephemeral status
            collection = (await self._attach_ephemeral_status(db, [collection], current_user))[0]

        return collection

    async def get_by_readable_id(
        self, db: AsyncSession, readable_id: str, current_user: schemas.User
    ) -> Optional[Collection]:
        """Get a collection by its readable ID with computed ephemeral status."""
        result = await db.execute(select(Collection).where(Collection.readable_id == readable_id))
        collection = result.scalar_one_or_none()

        if collection is None:
            return None

        self._validate_if_user_has_permission(collection, current_user)

        # Compute and set the ephemeral status
        collection = (await self._attach_ephemeral_status(db, [collection], current_user))[0]

        return collection

    async def get_multi(
        self, db: AsyncSession, *, skip: int = 0, limit: int = 100, current_user: schemas.User
    ) -> List[Collection]:
        """Get multiple collections with computed ephemeral statuses."""
        # Get collections using the parent method
        collections = await super().get_multi(db, skip=skip, limit=limit, current_user=current_user)

        # Compute and set the ephemeral status for each collection
        collections = await self._attach_ephemeral_status(db, collections, current_user)

        return collections

    async def get_multi_by_organization(
        self,
        db: AsyncSession,
        organization_id: UUID,
        current_user: schemas.User,
        skip: int = 0,
        limit: int = 100,
    ) -> List[Collection]:
        """Get all collections for a specific organization with computed ephemeral statuses."""
        result = await db.execute(
            select(Collection)
            .where(Collection.organization_id == organization_id)
            .offset(skip)
            .limit(limit)
        )
        collections = list(result.scalars().all())

        # Compute and set the ephemeral status for each collection
        collections = await self._attach_ephemeral_status(db, collections, current_user)

        return collections


collection = CRUDCollection(Collection)
