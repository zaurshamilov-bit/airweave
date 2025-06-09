"""CRUD operations for collections."""

from typing import List, Optional
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from airweave.core.shared_models import CollectionStatus, SourceConnectionStatus
from airweave.crud._base_organization import CRUDBaseOrganization
from airweave.crud.crud_source_connection import source_connection as crud_source_connection
from airweave.models.collection import Collection
from airweave.schemas.auth import AuthContext
from airweave.schemas.collection import CollectionCreate, CollectionUpdate


class CRUDCollection(CRUDBaseOrganization[Collection, CollectionCreate, CollectionUpdate]):
    """CRUD operations for collections."""

    async def _compute_collection_status(
        self, db: AsyncSession, collection: Collection, auth_context: AuthContext
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
            auth_context: Authentication context

        Returns:
            The computed ephemeral status
        """
        # Get all source connections for this collection
        source_connections = await crud_source_connection.get_for_collection(
            db, readable_collection_id=collection.readable_id, auth_context=auth_context
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
        self, db: AsyncSession, collections: List[Collection], auth_context: AuthContext
    ) -> List[Collection]:
        """Attach ephemeral status to collections.

        Args:
            db: The database session
            collections: The collections to process
            auth_context: Authentication context

        Returns:
            Collections with computed status
        """
        if not collections:
            return []

        for collection in collections:
            # Compute and set the ephemeral status
            collection.status = await self._compute_collection_status(db, collection, auth_context)

        return collections

    async def get(
        self, db: AsyncSession, id: UUID, auth_context: AuthContext
    ) -> Optional[Collection]:
        """Get a collection by its ID with computed ephemeral status."""
        # Get the collection using the parent method
        collection = await super().get(db, id=id, auth_context=auth_context)

        if collection:
            # Compute and set the ephemeral status
            collection = (await self._attach_ephemeral_status(db, [collection], auth_context))[0]

        return collection

    async def get_by_readable_id(
        self, db: AsyncSession, readable_id: str, auth_context: AuthContext
    ) -> Optional[Collection]:
        """Get a collection by its readable ID with computed ephemeral status."""
        result = await db.execute(select(Collection).where(Collection.readable_id == readable_id))
        collection = result.scalar_one_or_none()

        if collection is None:
            return None

        await self._validate_organization_access(auth_context, collection.organization_id)

        # Compute and set the ephemeral status
        collection = (await self._attach_ephemeral_status(db, [collection], auth_context))[0]

        return collection

    async def get_multi(
        self, db: AsyncSession, *, skip: int = 0, limit: int = 100, auth_context: AuthContext
    ) -> List[Collection]:
        """Get multiple collections with computed ephemeral statuses."""
        # Get collections using the parent method
        collections = await super().get_multi(db, skip=skip, limit=limit, auth_context=auth_context)

        # Compute and set the ephemeral status for each collection
        collections = await self._attach_ephemeral_status(db, collections, auth_context)

        return collections


collection = CRUDCollection(Collection)
