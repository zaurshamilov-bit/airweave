"""Search service for vector database integrations."""

import logging
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from airweave import crud, schemas
from airweave.core.exceptions import NotFoundException
from airweave.platform.destinations.weaviate import WeaviateDestination
from airweave.platform.embedding_models.local_text2vec import LocalText2Vec
from airweave.platform.locator import resource_locator

logger = logging.getLogger(__name__)


class SearchService:
    """Service for handling vector database searches."""

    async def search(
        self,
        db: AsyncSession,
        query: str,
        sync_id: UUID,
        current_user: schemas.User,
    ) -> list[dict]:
        """Search across vector database using existing connections.

        Args:
            db (AsyncSession): Database session
            query (str): Search query text
            sync_id (UUID): ID of the sync to search within
            current_user (schemas.User): Current user performing the search

        Returns:
            list[dict]: List of search results

        Raises:
            NotFoundException: If sync or connections not found
        """
        try:
            # Get sync configuration
            sync = await crud.sync.get(db, id=sync_id, current_user=current_user)
            if not sync:
                raise NotFoundException("Sync not found")

            # Get destination connection if specified, otherwise use default Weaviate
            destination = None
            if sync.destination_connection_id:
                connection = await crud.connection.get(
                    db, sync.destination_connection_id, current_user
                )
                if not connection:
                    raise NotFoundException("Destination connection not found")

                destination_model = await crud.destination.get_by_short_name(
                    db, connection.short_name
                )
                if not destination_model:
                    raise NotFoundException("Destination not found")

                # Get credentials
                integration_credential = await crud.integration_credential.get(
                    db,
                    connection.integration_credential_id,
                    current_user,
                )
                if not integration_credential:
                    raise NotFoundException("Destination credentials not found")

                # Initialize destination class
                destination_class = resource_locator.get_destination(destination_model)
                destination = await destination_class.create(
                    sync_id=sync_id,
                    embedding_model=LocalText2Vec(),  # Default model if none specified
                )

            # If no destination connection, use default Weaviate
            if not destination:
                destination = await WeaviateDestination.create(
                    sync_id=sync_id,
                    embedding_model=LocalText2Vec(),
                )

            # Perform search
            results = await destination.search_for_sync_id(
                query_text=query,
                sync_id=sync_id,
            )

            return results

        except Exception as e:
            logger.error(f"Search error: {str(e)}")
            raise


# Create singleton instance
search_service = SearchService()
