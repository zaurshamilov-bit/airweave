"""Search service for vector database integrations."""

import logging

from sqlalchemy.ext.asyncio import AsyncSession

from airweave import crud, schemas
from airweave.core.config import settings
from airweave.core.exceptions import NotFoundException
from airweave.platform.embedding_models.local_text2vec import LocalText2Vec
from airweave.platform.embedding_models.openai_text2vec import OpenAIText2Vec
from airweave.platform.locator import resource_locator

logger = logging.getLogger(__name__)


class SearchService:
    """Service for handling vector database searches."""

    async def search(
        self,
        db: AsyncSession,
        query: str,
        readable_id: str,
        current_user: schemas.User,
    ) -> list[dict]:
        """Search across vector database using existing connections.

        Args:
            db (AsyncSession): Database session
            query (str): Search query text
            readable_id (str): Readable ID of the collection to search within
            current_user (schemas.User): Current user performing the search

        Returns:
            list[dict]: List of search results

        Raises:
            NotFoundException: If sync or connections not found
        """
        try:
            collection = await crud.collection.get_by_readable_id(db, readable_id, current_user)
            if not collection:
                raise NotFoundException("Collection not found")

            # Get the destination model
            destination_model = await crud.destination.get_by_short_name(db, "qdrant_native")
            if not destination_model:
                raise NotFoundException("Destination not found")

            # Initialize destination class
            destination_class = resource_locator.get_destination(destination_model)

            # Use OpenAI embeddings if API key is available
            if settings.OPENAI_API_KEY:
                logger.info(
                    "Using OpenAI embedding model for search in "
                    f"collection {readable_id} {collection.id}"
                )
                embedding_model = OpenAIText2Vec(api_key=settings.OPENAI_API_KEY)
            else:
                logger.info(
                    "Using local embedding model for search in "
                    f"collection {readable_id} {collection.id}"
                )
                embedding_model = LocalText2Vec()

            vector = await embedding_model.embed(query)
            destination = await destination_class.create(collection_id=collection.id)

            # Perform search
            results = await destination.search(vector)

            return results

        except Exception as e:
            logger.error(f"Search error: {str(e)}")
            raise


# Create singleton instance
search_service = SearchService()
