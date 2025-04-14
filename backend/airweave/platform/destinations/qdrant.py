"""Qdrant destination implementation."""

from uuid import UUID

from pydantic import Field
from qdrant_client import QdrantClient
from qdrant_client.http import models as rest

from airweave.core.config import settings
from airweave.core.logging import logger
from airweave.platform.auth.schemas import AuthType
from airweave.platform.configs.auth import AuthConfig
from airweave.platform.decorators import destination
from airweave.platform.destinations._base import VectorDBDestination
from airweave.platform.entities._base import ChunkEntity


class QdrantAuthConfig(AuthConfig):
    """Qdrant authentication credentials schema."""

    url: str = Field(title="URL", description="The URL of the Qdrant service")
    api_key: str = Field(
        title="API Key", description="The API key for the Qdrant service (if required)"
    )


@destination("Qdrant", "qdrant", AuthType.config_class, "QdrantAuthConfig", labels=["Vector"])
class QdrantDestination(VectorDBDestination):
    """Qdrant destination implementation.

    This class directly interacts with the Qdrant client and assumes entities
    already have vector embeddings.
    """

    def __init__(self):
        """Initialize Qdrant destination."""
        self.collection_name: str | None = None
        self.sync_id: UUID | None = None
        self.url: str | None = None
        self.api_key: str | None = None
        self.client: QdrantClient | None = None
        self.vector_size: int = 1536  # Default vector size

    @classmethod
    async def create(
        cls,
        sync_id: UUID,
        vector_size: int = 1536,
    ) -> "QdrantDestination":
        """Create a new Qdrant destination.

        Args:
            sync_id (UUID): The ID of the sync.
            vector_size (int): The size of the vectors to use.

        Returns:
            QdrantDestination: The created destination.
        """
        instance = cls()
        instance.sync_id = sync_id
        instance.collection_name = f"Entities_{instance._sanitize_collection_name(sync_id)}"
        instance.vector_size = vector_size

        # Get credentials for sync_id
        credentials = await cls.get_credentials()
        if credentials:
            instance.url = credentials.url
            instance.api_key = credentials.api_key
        else:
            instance.url = None
            instance.api_key = None

        # Initialize client
        await instance.connect_to_qdrant()

        # Set up initial collection
        await instance.setup_collection(sync_id)
        return instance

    @classmethod
    async def get_credentials(cls) -> QdrantAuthConfig | None:
        """Get credentials for the destination.

        Returns:
            QdrantAuthConfig | None: The credentials for the destination.
        """
        # TODO: Implement this
        return None

    async def connect_to_qdrant(self) -> None:
        """Connect to Qdrant service with appropriate authentication."""
        if self.client is None:
            try:
                # Configure client
                client_config = {
                    "location": self.url or settings.QDRANT_URL,
                    "prefer_grpc": False,  # Use HTTP by default
                }

                # Add API key if provided
                api_key = self.api_key or settings.QDRANT_API_KEY
                if api_key:
                    client_config["api_key"] = api_key

                # Initialize client
                self.client = QdrantClient(**client_config)

                # Test connection
                self.client.get_collections()
                logger.info("Successfully connected to Qdrant service.")
            except Exception as e:
                logger.error(f"Error connecting to Qdrant service: {e}")
                self.client = None
                raise

    async def ensure_client_readiness(self) -> None:
        """Ensure the client is ready to accept requests."""
        if self.client is None:
            await self.connect_to_qdrant()
            if self.client is None:
                raise Exception("Qdrant client failed to connect.")

    async def close_connection(self) -> None:
        """Close the connection to the Qdrant service."""
        if self.client:
            logger.info("Closing Qdrant client connection gracefully...")
            # Qdrant client doesn't have an explicit close method, but we can set it to None
            self.client = None
        else:
            logger.info("No Qdrant client connection to close.")

    async def collection_exists(self, collection_name: str) -> bool:
        """Check if a collection exists in Qdrant.

        Args:
            collection_name (str): The name of the collection.

        Returns:
            bool: True if the collection exists, False otherwise.
        """
        await self.ensure_client_readiness()
        try:
            collections = self.client.get_collections().collections
            return any(collection.name == collection_name for collection in collections)
        except Exception as e:
            logger.error(f"Error checking if collection exists: {e}")
            return False

    async def setup_collection(self, sync_id: UUID) -> None:  # noqa: C901
        """Set up the Qdrant collection for storing entities.

        Args:
            sync_id (UUID): The ID of the sync.
        """
        await self.ensure_client_readiness()

        # Define collection schema with payload properties
        payload_schema = {
            "source_name": "keyword",
            "entity_id": "keyword",
            "sync_id": "keyword",
            "sync_job_id": "keyword",
            "content": "text",
            "url": "keyword",
            "sync_metadata": "text",
            "white_label_user_identifier": "keyword",
            "white_label_id": "keyword",
            "white_label_name": "keyword",
        }

        try:
            # Check if collection exists
            if await self.collection_exists(self.collection_name):
                logger.info(f"Collection {self.collection_name} already exists.")
                return

            logger.info(f"Creating collection {self.collection_name}...")

            # Define schema mapping for payload fields
            schema_mapping = {}
            for field_name, field_type in payload_schema.items():
                if field_type == "keyword":
                    schema_mapping[field_name] = rest.PayloadSchemaType.KEYWORD
                elif field_type == "text":
                    schema_mapping[field_name] = rest.PayloadSchemaType.TEXT
                elif field_type == "integer":
                    schema_mapping[field_name] = rest.PayloadSchemaType.INTEGER
                elif field_type == "float":
                    schema_mapping[field_name] = rest.PayloadSchemaType.FLOAT
                elif field_type == "boolean":
                    schema_mapping[field_name] = rest.PayloadSchemaType.BOOL
                elif field_type == "geo":
                    schema_mapping[field_name] = rest.PayloadSchemaType.GEO

            # Create the collection
            self.client.create_collection(
                collection_name=self.collection_name,
                vectors_config=rest.VectorParams(
                    size=self.vector_size,
                    distance=rest.Distance.COSINE,
                ),
                optimizers_config=rest.OptimizersConfigDiff(
                    indexing_threshold=20000,  # Default indexing threshold
                ),
                on_disk_payload=True,  # Store payload on disk to save memory
            )

            # Add payload schema for indexing
            for field_name, field_type in schema_mapping.items():
                self.client.create_payload_index(
                    collection_name=self.collection_name,
                    field_name=field_name,
                    field_schema=field_type,
                )

        except Exception as e:
            if "already exists" not in str(e):
                raise

    async def insert(self, entity: ChunkEntity) -> None:
        """Insert a single entity into Qdrant.

        Args:
            entity (ChunkEntity): The entity to insert.
        """
        await self.ensure_client_readiness()

        # Use the entity's to_storage_dict method to get properly serialized data
        data_object = entity.to_storage_dict()

        # Use the entity's vector directly
        if not hasattr(entity, "vector") or entity.vector is None:
            raise ValueError(f"Entity {entity.entity_id} has no vector")

        # Insert point with vector from entity
        self.client.upsert(
            collection_name=self.collection_name,
            points=[
                rest.PointStruct(
                    id=str(entity.db_entity_id),
                    vector=entity.vector,
                    payload=data_object,
                )
            ],
        )

    async def bulk_insert(self, entities: list[ChunkEntity]) -> None:
        """Bulk insert entities into Qdrant.

        Args:
            entities (list[ChunkEntity]): The entities to insert.
        """
        if not entities:
            return

        await self.ensure_client_readiness()

        # Convert entities to Qdrant points
        point_structs = []
        for entity in entities:
            # Use the entity's to_storage_dict method to get properly serialized data
            entity_data = entity.to_storage_dict()

            # Use the entity's vector directly
            if not hasattr(entity, "vector") or entity.vector is None:
                logger.warning(f"Entity {entity.entity_id} has no vector, skipping")
                continue

            # Create point for Qdrant
            point_structs.append(
                rest.PointStruct(
                    id=str(entity.db_entity_id),
                    vector=entity.vector,
                    payload=entity_data,
                )
            )

        if not point_structs:
            logger.warning("No valid entities to insert")
            return

        # Bulk upsert
        operation_response = self.client.upsert(
            collection_name=self.collection_name,
            points=point_structs,
            wait=True,  # Wait for operation to complete
        )

        if hasattr(operation_response, "errors") and operation_response.errors:
            raise Exception(f"Errors during bulk insert: {operation_response.errors}")

    async def delete(self, db_entity_id: UUID) -> None:
        """Delete a single entity from Qdrant.

        Args:
            db_entity_id (UUID): The ID of the entity to delete.
        """
        await self.ensure_client_readiness()

        self.client.delete(
            collection_name=self.collection_name,
            points_selector=rest.PointIdsList(
                points=[str(db_entity_id)],
            ),
            wait=True,  # Wait for operation to complete
        )

    async def bulk_delete(self, entity_ids: list[str]) -> None:
        """Bulk delete entities from Qdrant.

        Args:
            entity_ids (list[str]): The IDs of the entities to delete.
        """
        if not entity_ids:
            return

        await self.ensure_client_readiness()

        self.client.delete(
            collection_name=self.collection_name,
            points_selector=rest.PointIdsList(
                points=entity_ids,
            ),
            wait=True,  # Wait for operation to complete
        )

    async def bulk_delete_by_parent_id(self, parent_id: str, sync_id: str) -> None:
        """Bulk delete entities from Qdrant by parent ID and sync ID.

        This deletes all entities that have the specified parent_entity_id and sync_id.

        Args:
            parent_id (str): The parent ID to delete children for.
            sync_id (str): The sync ID.
        """
        if not parent_id:
            return

        await self.ensure_client_readiness()

        # Create filter for parent_id and sync_id
        filter_condition = {
            "must": [
                {"key": "parent_entity_id", "match": {"value": parent_id}},
                {"key": "sync_id", "match": {"value": sync_id}},
            ]
        }

        # Convert dict filter to Qdrant filter format
        qdrant_filter = rest.Filter.parse_obj(filter_condition)

        self.client.delete(
            collection_name=self.collection_name,
            points_selector=rest.FilterSelector(
                filter=qdrant_filter,
            ),
            wait=True,  # Wait for operation to complete
        )

    async def search_for_sync_id(self, query_vector: list[float], sync_id: UUID) -> list[dict]:
        """Search for a sync_id in the destination.

        Args:
            query_vector (list[float]): The query vector to search with.
            sync_id (UUID): The sync_id to search for.

        Returns:
            list[dict]: The search results.
        """
        await self.ensure_client_readiness()

        # Create filter for sync_id
        filter_condition = {
            "must": [
                {"key": "sync_id", "match": {"value": str(sync_id)}},
            ]
        }

        # Convert dict filter to Qdrant filter format
        qdrant_filter = rest.Filter.parse_obj(filter_condition)

        # Perform search
        search_results = self.client.search(
            collection_name=self.collection_name,
            query_vector=query_vector,
            query_filter=qdrant_filter,
            limit=10,
            with_payload=True,
        )

        # Convert results to a standard format
        results = []
        for result in search_results:
            results.append(
                {
                    "id": result.id,
                    "score": result.score,
                    "payload": result.payload,
                }
            )

        return results

    @staticmethod
    def _sanitize_collection_name(collection_name: UUID) -> str:
        """Sanitize the collection name to be a valid Qdrant collection name.

        Args:
            collection_name (UUID): The collection name to sanitize.

        Returns:
            str: The sanitized collection name.
        """
        return str(collection_name).replace("-", "_")
