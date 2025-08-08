"""Qdrant destination implementation."""

from typing import Literal, Optional
from uuid import UUID

from fastembed import SparseEmbedding
from qdrant_client import AsyncQdrantClient
from qdrant_client.http import models as rest
from qdrant_client.local.local_collection import DEFAULT_VECTOR_NAME

from airweave.core.config import settings
from airweave.core.logging import ContextualLogger
from airweave.core.logging import logger as default_logger
from airweave.platform.auth.schemas import AuthType
from airweave.platform.configs.auth import QdrantAuthConfig
from airweave.platform.decorators import destination
from airweave.platform.destinations._base import VectorDBDestination
from airweave.platform.entities._base import ChunkEntity


@destination("Qdrant", "qdrant", AuthType.config_class, "QdrantAuthConfig", labels=["Vector"])
class QdrantDestination(VectorDBDestination):
    """Qdrant destination implementation.

    This class directly interacts with the Qdrant client and assumes entities
    already have vector embeddings.
    """

    def __init__(self):
        """Initialize Qdrant destination."""
        super().__init__()  # Initialize base class for logger support
        self.collection_name: str | None = None
        self.collection_id: UUID | None = None
        self.url: str | None = None
        self.api_key: str | None = None
        self.client: AsyncQdrantClient | None = None
        self.vector_size: int = 384  # Default vector size

    @classmethod
    async def create(
        cls, collection_id: UUID, logger: Optional[ContextualLogger] = None
    ) -> "QdrantDestination":
        """Create a new Qdrant destination.

        Args:
            collection_id (UUID): The ID of the collection.
            vector_size (int): The size of the vectors to use.
            logger (Optional[ContextualLogger]): The logger to use.

        Returns:
            QdrantDestination: The created destination.
        """
        instance = cls()
        instance.set_logger(logger or default_logger)
        instance.collection_id = collection_id
        instance.collection_name = str(collection_id)

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
                if self.url:
                    location = self.url
                else:
                    location = settings.qdrant_url

                client_config = {
                    "location": location,
                    "prefer_grpc": False,  # Use HTTP by default
                }

                if location[-4:] != ":6333":
                    # allow railway to work
                    client_config["port"] = None

                # Add API key if provided
                api_key = self.api_key
                if api_key:
                    client_config["api_key"] = api_key

                # Initialize client
                self.client = AsyncQdrantClient(**client_config)

                # Test connection
                await self.client.get_collections()
                self.logger.debug("Successfully connected to Qdrant service.")
            except Exception as e:
                self.logger.error(f"Error connecting to Qdrant service at {location}: {e}")
                self.client = None
                # Provide more specific error messages
                if "connection refused" in str(e).lower():
                    raise ConnectionError(
                        f"Qdrant service is not running or refusing connections at {location}"
                    ) from e
                elif "timeout" in str(e).lower():
                    raise ConnectionError(
                        f"Connection to Qdrant service timed out at {location}"
                    ) from e

                elif "authentication" in str(e).lower() or "unauthorized" in str(e).lower():
                    raise ConnectionError(
                        f"Authentication failed for Qdrant service at {location}"
                    ) from e
                else:
                    raise ConnectionError(
                        f"Failed to connect to Qdrant service at {location}: {str(e)}"
                    ) from e

    async def ensure_client_readiness(self) -> None:
        """Ensure the client is ready to accept requests."""
        if self.client is None:
            await self.connect_to_qdrant()
            if self.client is None:
                raise ConnectionError(
                    "Failed to establish connection to Qdrant service. Please check if "
                    "the service is running and accessible."
                )

    async def close_connection(self) -> None:
        """Close the connection to the Qdrant service."""
        if self.client:
            self.logger.debug("Closing Qdrant client connection gracefully...")
            # Qdrant client doesn't have an explicit close method, but we can set it to None
            self.client = None
        else:
            self.logger.debug("No Qdrant client connection to close.")

    async def collection_exists(self, collection_name: str) -> bool:
        """Check if a collection exists in Qdrant.

        Args:
            collection_name (str): The name of the collection.

        Returns:
            bool: True if the collection exists, False otherwise.
        """
        await self.ensure_client_readiness()
        try:
            collections_response = await self.client.get_collections()
            collections = collections_response.collections
            return any(collection.name == collection_name for collection in collections)
        except Exception as e:
            self.logger.error(f"Error checking if collection exists: {e}")
            raise  # Re-raise the exception instead of returning False

    async def setup_collection(self, vector_size: int) -> None:  # noqa: C901
        """Set up the Qdrant collection for storing entities.

        Args:
            vector_size (int): The size of the vectors to use.
        """
        await self.ensure_client_readiness()

        try:
            # Check if collection exists
            if await self.collection_exists(self.collection_name):
                self.logger.debug(f"Collection {self.collection_name} already exists.")
                return

            self.logger.info(f"Creating collection {self.collection_name}...")

            # Create the collection
            await self.client.create_collection(
                collection_name=self.collection_name,
                vectors_config={
                    # Existing collections will have the default vector config,
                    # so we should tick to it even for new collections.
                    # Annoyingly, the DEFAULT_VECTOR_NAME is an empty string.
                    # Source: https://python-client.qdrant.tech/_modules/qdrant_client/local/local_collection
                    DEFAULT_VECTOR_NAME: rest.VectorParams(
                        size=vector_size if vector_size else self.vector_size,
                        distance=rest.Distance.COSINE,
                    ),
                },
                sparse_vectors_config={
                    "bm25": rest.SparseVectorParams(
                        modifier=rest.Modifier.IDF,
                    )
                },
                optimizers_config=rest.OptimizersConfigDiff(
                    indexing_threshold=20000,  # Default indexing threshold
                ),
                on_disk_payload=True,  # Store payload on disk to save memory
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
        await self.client.upload_points(
            self.collection_name,
            points=[
                rest.PointStruct(
                    id=str(entity.db_entity_id),
                    vector={
                        DEFAULT_VECTOR_NAME: entity.vector[0],
                        "bm25": entity.vector[1].as_object(),
                    },
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
            if not hasattr(entity, "vectors") or entity.vectors is None:
                self.logger.warning(f"Entity {entity.entity_id} has no vector, skipping")
                continue

            if hasattr(entity_data, "vectors"):
                entity_data.pop("vectors")

            # Create point for Qdrant
            point_structs.append(
                rest.PointStruct(
                    id=str(entity.db_entity_id),
                    vector={
                        DEFAULT_VECTOR_NAME: entity.vectors[0],
                        "bm25": entity.vectors[1].as_object(),
                    },
                    payload=entity_data,
                )
            )

        if not point_structs:
            self.logger.warning("No valid entities to insert")
            return

        # Bulk upsert
        operation_response = await self.client.upload_points(
            self.collection_name,
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

        await self.client.delete(
            collection_name=self.collection_name,
            points_selector=rest.PointIdsList(
                points=[str(db_entity_id)],
            ),
            wait=True,  # Wait for operation to complete
        )

    async def delete_by_sync_id(self, sync_id: UUID) -> None:
        """Delete entities from the destination by sync ID."""
        await self.ensure_client_readiness()

        await self.client.delete(
            collection_name=self.collection_name,
            points_selector=rest.FilterSelector(
                filter=rest.Filter(
                    should=[
                        rest.FieldCondition(
                            key="sync_id", match=rest.MatchValue(value=str(sync_id))
                        )
                    ]
                )
            ),
            wait=True,  # Wait for operation to complete
        )

    async def bulk_delete(self, entity_ids: list[str], sync_id: UUID) -> None:
        """Bulk delete entities from Qdrant.

        Args:
            entity_ids (list[str]): The IDs of the entities to delete.
            sync_id (UUID): The sync ID.
        """
        if not entity_ids:
            return

        await self.ensure_client_readiness()

        await self.client.delete(
            collection_name=self.collection_name,
            points_selector=rest.FilterSelector(
                filter=rest.Filter(
                    must=[
                        rest.FieldCondition(
                            key="sync_id", match=rest.MatchValue(value=str(sync_id))
                        ),
                        rest.FieldCondition(key="entity_id", match=rest.MatchAny(any=entity_ids)),
                    ]
                )
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

        # Ensure sync_id is a string
        sync_id_str = str(sync_id)
        parent_id_str = str(parent_id)

        # Create filter for parent_id and sync_id using the correct Qdrant structure
        filter_condition = {
            "must": [
                {"key": "parent_entity_id", "match": {"value": parent_id_str}},
                {"key": "sync_id", "match": {"value": sync_id_str}},
            ]
        }

        # Use try-except to handle any filter validation errors
        try:
            # Convert dict filter to Qdrant filter format
            qdrant_filter = rest.Filter.model_validate(filter_condition)

            await self.client.delete(
                collection_name=self.collection_name,
                points_selector=rest.FilterSelector(
                    filter=qdrant_filter,
                ),
                wait=True,  # Wait for operation to complete
            )
        except Exception as e:
            self.logger.error(f"Error creating Qdrant filter: {e}")
            self.logger.error(f"Filter condition: {filter_condition}")
            # Fallback to a different approach if needed
            raise

    async def search(
        self,
        query_vector: list[float],
        filter: dict | None = None,
        limit: int = 10,
        offset: int = 0,
        score_threshold: float | None = None,
        with_payload: bool = True,
    ) -> list[dict]:
        """Search for entities in the destination.

        Args:
            query_vector (list[float]): The query vector to search with.
            filter (dict | None): Optional filter conditions as a dictionary.
            limit (int): Maximum number of results to return.
            offset (int): Number of results to skip.
            score_threshold (float | None): Optional minimum score threshold.
            with_payload (bool): Whether to include payload in results.

        Returns:
            list[dict]: The search results.
        """
        await self.ensure_client_readiness()

        try:
            # Build search parameters
            search_params = {
                "collection_name": self.collection_name,
                "query": query_vector,
                "limit": limit,
                "with_payload": with_payload,
            }

            # Add optional parameters
            if offset and offset > 0:
                search_params["offset"] = offset

            if score_threshold is not None:
                search_params["score_threshold"] = score_threshold

            if filter:
                # Convert dict filter to Qdrant filter
                qdrant_filter = rest.Filter.model_validate(filter)
                search_params["query_filter"] = qdrant_filter

            # Perform search
            search_results = await self.client.query_points(**search_params)

            # Convert results to a standard format
            results = []
            for result in search_results.points:
                results.append(
                    {
                        "id": result.id,
                        "score": result.score,
                        "payload": result.payload if with_payload else None,
                    }
                )

            return results
        except Exception as e:
            self.logger.error(f"Error searching with Qdrant filter: {e}")
            raise  # Re-raise the exception instead of returning empty list

    async def _prepare_query_request(
        self,
        query_vector: list[float],
        limit: int,
        sparse_vector: SparseEmbedding | None,
        search_method: Literal["hybrid", "neural", "keyword"],
    ) -> rest.QueryRequest:
        """Prepare a query request for Qdrant.

        Args:
            query_vector (list[float]): The query vector to search with.
            limit (int): Maximum number of results to return.
            sparse_vector (SparseEmbedding | None): Optional sparse vector to search with.
            search_method (Literal["hybrid", "neural", "keyword"]): The search method to use.

        Returns:
            rest.QueryRequest: The prepared query request.
        """
        query_request_params = {}

        if search_method == "neural":
            query_request_params = {
                "query": query_vector,
                "using": DEFAULT_VECTOR_NAME,
                "limit": limit,
            }

        if search_method == "keyword":
            if not sparse_vector:
                raise ValueError("Keyword search requires sparse vector")

            query_request_params = {
                "query": rest.SparseVector(**sparse_vector.as_object()),
                "using": "bm25",
                "limit": limit,
            }

        if search_method == "hybrid":
            if not sparse_vector:
                raise ValueError("Keyword search requires sparse vector")

            query_request_params["prefetch"] = [
                # Neural embedding
                rest.Prefetch(
                    query=query_vector,
                    using=DEFAULT_VECTOR_NAME,
                    limit=limit,
                ),
                # BM25 embedding
                rest.Prefetch(
                    query=rest.SparseVector(**sparse_vector.as_object()),
                    using="bm25",
                    limit=limit,
                ),
            ]

            # Qdrant doesn't support doing weighted fusion with RRF.
            # https://github.com/qdrant/qdrant/issues/6067
            query_request_params["query"] = rest.FusionQuery(
                fusion=rest.Fusion.RRF,
            )

        return query_request_params

    async def bulk_search(
        self,
        query_vectors: list[list[float]],
        limit: int = 10,
        score_threshold: float | None = None,
        with_payload: bool = True,
        filter_conditions: list[dict] | None = None,
        sparse_vectors: list[SparseEmbedding] | None = None,
        search_method: Literal["hybrid", "neural", "keyword"] = "neural",
    ) -> list[list[dict]]:
        """Perform batch search for multiple query vectors in a single request.

        Args:
            query_vectors (list[list[float]]): List of query vectors to search with.
            limit (int): Maximum number of results per query. Defaults to 10.
            score_threshold (float | None): Optional minimum score threshold for results.
            with_payload (bool): Whether to include payload in results. Defaults to True.
            filter_conditions (list[dict] | None): Optional list of filter conditions,
                one per query vector. If provided, must have same length as query_vectors.
            sparse_vectors (List[SparseEmbedding] | None): Optional list of sparse vectors.
                If provided, must have same length as query_vectors.
            search_method (Literal["hybrid", "neural", "keyword"]): The search method to use.
                Defaults to "neural".

        Returns:
            list[list[dict]]: List of search results for each query vector.
                Each inner list contains results for the corresponding query vector.
        """
        await self.ensure_client_readiness()

        # Validate inputs
        if not query_vectors:
            return []

        if filter_conditions and len(filter_conditions) != len(query_vectors):
            raise ValueError(
                f"Number of filter conditions ({len(filter_conditions)}) must match "
                f"number of query vectors ({len(query_vectors)})"
            )

        if sparse_vectors and len(query_vectors) != len(sparse_vectors):
            print(
                f"Number of query vectors ({len(query_vectors)}) must match "
                f"number of sparse vectors ({len(sparse_vectors)})"
            )
            raise ValueError(
                f"Number of query vectors ({len(query_vectors)}) must match "
                f"number of sparse vectors ({len(sparse_vectors)})"
            )

        try:
            query_requests = []
            for i, query_vector in enumerate(query_vectors):
                # Create base query request
                sparse_vector = sparse_vectors[i] if sparse_vectors else None

                query_request_params = self._prepare_query_request(
                    query_vector, limit, sparse_vector, search_method
                )
                request = rest.QueryRequest(
                    score_threshold=score_threshold,
                    with_payload=with_payload,
                    **query_request_params,
                )

                # Add filter if provided
                if filter_conditions and filter_conditions[i]:
                    request.filter = rest.Filter.model_validate(filter_conditions[i])

                query_requests.append(request)

            # Perform batch search
            batch_results = await self.client.query_batch_points(
                collection_name=self.collection_name, requests=query_requests
            )

            # Convert results to standard format
            all_results = []
            for search_results in batch_results:
                results = []
                for result in search_results.points:
                    result_dict = {
                        "id": result.id,
                        "score": result.score,
                    }
                    if with_payload:
                        result_dict["payload"] = result.payload
                    results.append(result_dict)
                all_results.append(results)

            return all_results

        except Exception as e:
            self.logger.error(f"Error performing batch search with Qdrant: {e}")
            raise
