"""Collection service."""

from typing import Optional

from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from airweave import crud, schemas
from airweave.core.config import settings
from airweave.db.unit_of_work import UnitOfWork
from airweave.platform.destinations.qdrant import QdrantDestination


def _determine_vector_size() -> int:
    """Determine the vector size for a collection based on the source connection."""
    if settings.OPENAI_API_KEY:
        return 1536
    else:
        return 384


class CollectionService:
    """Service for managing collections.

    Manages the lifecycle of collections across the SQL datamodel and Qdrant.
    """

    async def create(
        self,
        db: AsyncSession,
        collection_in: schemas.CollectionCreate,
        current_user: schemas.User,
        uow: Optional[UnitOfWork] = None,
    ) -> schemas.Collection:
        """Create a new collection."""
        if uow is None:
            # Unit of work is not provided, so we create a new one
            async with UnitOfWork(db) as uow:
                collection = await self._create(
                    db, collection_in=collection_in, current_user=current_user, uow=uow
                )
        else:
            # Unit of work is provided, so we just create the collection
            collection = await self._create(
                db, collection_in=collection_in, current_user=current_user, uow=uow
            )

        return collection

    async def _create(
        self,
        db: AsyncSession,
        collection_in: schemas.CollectionCreate,
        current_user: schemas.User,
        uow: UnitOfWork,
    ) -> schemas.Collection:
        """Create a new collection."""
        # Check if the collection already exists
        existing_collection = await crud.collection.get_by_readable_id(
            db, readable_id=collection_in.readable_id, current_user=current_user
        )
        if existing_collection:
            raise HTTPException(
                status_code=400, detail="Collection with this readable_id already exists"
            )

        collection = await crud.collection.create(
            db, obj_in=collection_in, current_user=current_user, uow=uow
        )
        await uow.session.flush()

        # Create a Qdrant destination
        qdrant_destination = await QdrantDestination.create(collection_id=collection.id)

        # Setup the collection on Qdrant
        await qdrant_destination.setup_collection(vector_size=_determine_vector_size())

        return schemas.Collection.model_validate(collection, from_attributes=True)


# Singleton instance
collection_service = CollectionService()
