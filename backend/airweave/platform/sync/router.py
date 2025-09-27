"""DAG router."""

import asyncio
from typing import Optional
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from airweave import crud
from airweave.core.config import settings
from airweave.core.constants.reserved_ids import RESERVED_TABLE_ENTITY_ID
from airweave.core.logging import ContextualLogger
from airweave.platform.entities._base import (
    BaseEntity,
    ChunkEntity,
    CodeFileEntity,
    FileEntity,
    PolymorphicEntity,
)
from airweave.platform.locator import resource_locator
from airweave.platform.transformers.code_file_chunker import code_file_chunker
from airweave.platform.transformers.code_file_summarizer import code_file_summarizer
from airweave.platform.transformers.default_file_chunker import file_chunker
from airweave.platform.transformers.entity_field_chunker import entity_chunker
from airweave.schemas.dag import DagNode, NodeType, SyncDag


class SyncDAGRouter:
    """Routes entities through the DAG based on producer and entity type."""

    def __init__(
        self,
        dag: SyncDag,
        entity_map: dict[type[BaseEntity], UUID],
        logger: ContextualLogger,
    ):
        """Initialize the DAG router."""
        self.dag = dag
        self.entity_map = entity_map
        self.route = self._build_execution_route()
        # Add transformer cache to eliminate 1.5s database lookups
        self._transformer_cache = {}
        self.logger = logger

    async def initialize_transformer_cache(self, db: AsyncSession) -> None:
        """Pre-load all transformers to eliminate database lookups during processing."""
        # Get all transformer IDs used in the DAG
        transformer_ids = set()
        for node in self.dag.nodes:
            if node.transformer_id:
                transformer_ids.add(node.transformer_id)

        # Batch load all transformers
        for transformer_id in transformer_ids:
            transformer = await crud.transformer.get(db, id=transformer_id)
            if transformer:
                self._transformer_cache[transformer_id] = transformer

    def _build_execution_route(self) -> dict[tuple[UUID, UUID], list[Optional[UUID]]]:
        """Construct an execution route for the DAG.

        Maps a tuple of a producer node id with a entity definition id to a consumer node id.

        If the entity is sent to a destination, the route is set to None, this stops the entity
        from being routed further.
        """
        route_map = {}
        for node in self.dag.nodes:
            if node.type == NodeType.entity:
                edge_inwards = self.dag.get_edges_to_node(node.id)

                # Get the producer node
                producer = edge_inwards[0].from_node_id

                edges_outwards = self.dag.get_edges_from_node(node.id)

                # Check if all outgoing edges go to destination nodes
                if edges_outwards:
                    all_destinations = True
                    for edge in edges_outwards:
                        consumer_node = self.dag.get_node(edge.to_node_id)
                        if consumer_node.type != NodeType.destination:
                            all_destinations = False
                            break

                    if all_destinations:
                        # If all outgoing edges go to destinations, stop routing
                        route_map[(producer, node.entity_definition_id)] = None
                    elif len(edges_outwards) == 1:
                        # If there's only one outgoing edge and it's not to a destination,
                        # route to that node
                        route_map[(producer, node.entity_definition_id)] = edges_outwards[
                            0
                        ].to_node_id
                    else:
                        # If there are multiple outgoing edges and not all go to destinations,
                        # this is an invalid configuration
                        raise ValueError(
                            f"Entity node {node.id} has multiple outbound edges "
                            "to non-destination nodes."
                        )
                else:
                    # No outgoing edges, this is a terminal node
                    route_map[(producer, node.entity_definition_id)] = None

        return route_map

    def _get_entity_definition_id(self, entity_type: type) -> UUID:
        """Get entity definition ID for a given entity type.

        This method first tries to find the exact type in the entity map.
        If not found, it tries to find a matching class by name and module.
        This handles dynamically created classes like Parent and Chunk models.

        Args:
            entity_type: The entity type to look up

        Returns:
            The entity definition ID

        Raises:
            ValueError: If no matching entity definition is found
        """
        # First try direct lookup
        if entity_type in self.entity_map:
            return self.entity_map[entity_type]

        # Handle PolymorphicEntity subclasses
        if hasattr(entity_type, "__mro__") and issubclass(entity_type, PolymorphicEntity):
            return RESERVED_TABLE_ENTITY_ID

        # Handle dynamically created Parent/Chunk/UnifiedChunk classes
        entity_name = entity_type.__name__
        entity_module = entity_type.__module__

        base_name = None
        if entity_name.endswith("Parent"):
            base_name = entity_name.replace("Parent", "Entity")
        elif entity_name.endswith("Chunk"):
            base_name = entity_name.replace("Chunk", "Entity")
        elif entity_name.endswith("UnifiedChunk"):
            base_name = entity_name.replace("UnifiedChunk", "Entity")

        if base_name:
            for cls, definition_id in self.entity_map.items():
                if cls.__name__ == base_name and cls.__module__ == entity_module:
                    # Cache the result for future lookups
                    self.entity_map[entity_type] = definition_id
                    return definition_id

        self.logger.warning(f"No entity definition found for {entity_type}")
        raise ValueError(f"No entity definition found for {entity_type}")

    async def process_entity(self, producer_id: UUID, entity: BaseEntity) -> list[BaseEntity]:
        """Route an entity to its next consumer based on DAG structure."""
        entity_context = f"Entity({entity.entity_id})"
        entity_type = type(entity)
        router_start = asyncio.get_running_loop().time()

        # Handle special entity types with dedicated processing
        if self._is_code_file_entity(entity_type, entity):
            return await self._handle_code_file_entity(entity, entity_context, router_start)

        if self._is_regular_file_entity(entity_type, entity):
            return await self._handle_regular_file_entity(entity, entity_context, router_start)

        if self._is_chunk_entity_for_field_processing(entity_type, entity):
            return await self._handle_chunk_entity_processing(entity, entity_context, router_start)

        # Normal DAG routing for other entities
        return await self._handle_dag_routing(
            producer_id, entity, entity_context, entity_type, router_start
        )

    def _is_code_file_entity(self, entity_type: type, entity: BaseEntity) -> bool:
        """Check if entity is a CodeFileEntity."""
        return issubclass(entity_type, CodeFileEntity) or isinstance(entity, CodeFileEntity)

    def _is_regular_file_entity(self, entity_type: type, entity: BaseEntity) -> bool:
        """Check if entity is a regular FileEntity (not CodeFileEntity)."""
        return (
            issubclass(entity_type, FileEntity)
            and not issubclass(entity_type, CodeFileEntity)
            and not isinstance(entity, CodeFileEntity)
        )

    def _is_chunk_entity_for_field_processing(self, entity_type: type, entity: BaseEntity) -> bool:
        """Check if entity is a ChunkEntity that needs field processing."""
        return (
            issubclass(entity_type, ChunkEntity)
            and not issubclass(entity_type, FileEntity)
            and not isinstance(entity, FileEntity)
        )

    async def _handle_code_file_entity(
        self, entity: BaseEntity, entity_context: str, router_start: float
    ) -> list[BaseEntity]:
        """Handle CodeFileEntity processing with chunking and optional summarization."""
        transformed_entities = await code_file_chunker(entity, self.logger)

        if settings.CODE_SUMMARIZER_ENABLED:
            transformed_entities = await self._apply_code_summarization(
                transformed_entities, entity_context
            )

        return transformed_entities

    async def _apply_code_summarization(
        self, transformed_entities: list[BaseEntity], entity_context: str
    ) -> list[BaseEntity]:
        """Apply code summarization to transformed entities."""
        for transformed_entity in transformed_entities:
            transformed_entity = await code_file_summarizer(transformed_entity, self.logger)

        return transformed_entities

    async def _handle_regular_file_entity(
        self, entity: BaseEntity, entity_context: str, router_start: float
    ) -> list[BaseEntity]:
        """Handle regular FileEntity processing."""
        # Try to use optimized chunker if available
        try:
            from airweave.platform.transformers.optimized_file_chunker import (
                optimized_file_chunker,
            )

            transformed_entities = await optimized_file_chunker(entity, self.logger)
        except ImportError:
            transformed_entities = await file_chunker(entity, self.logger)

        return transformed_entities

    async def _handle_chunk_entity_processing(
        self, entity: BaseEntity, entity_context: str, router_start: float
    ) -> list[BaseEntity]:
        """Handle ChunkEntity field processing."""
        chunked_entities = await entity_chunker(entity, self.logger)

        if len(chunked_entities) > 1:
            return chunked_entities
        else:
            # Continue with normal DAG routing since no chunking occurred
            return [entity]

    async def _handle_dag_routing(
        self,
        producer_id: UUID,
        entity: BaseEntity,
        entity_context: str,
        entity_type: type,
        router_start: float,
    ) -> list[BaseEntity]:
        """Handle normal DAG routing for entities."""
        try:
            entity_definition_id = self._get_entity_definition_id(entity_type)
        except ValueError as e:
            self.logger.warning(f"No entity definition found for {entity_type}: {str(e)}")
            # Return entity as-is if no definition found
            return [entity]

        route_key = (producer_id, entity_definition_id)

        if route_key not in self.route:
            return [entity]

        consumer_id = self.route[route_key]

        if consumer_id is None:
            return [entity]

        # Get the consumer node and apply transformer
        consumer = self.dag.get_node(consumer_id)
        transformed_entities = await self._apply_transformer(consumer, entity)

        # Route the transformed entities recursively
        return await self._route_transformed_entities(
            consumer_id, transformed_entities, entity_context, router_start
        )

    async def _route_transformed_entities(
        self,
        consumer_id: UUID,
        transformed_entities: list[BaseEntity],
        entity_context: str,
        router_start: float,
    ) -> list[BaseEntity]:
        """Route transformed entities recursively."""
        result_entities = []
        for transformed_entity in transformed_entities:
            sub_entities = await self.process_entity(consumer_id, transformed_entity)
            result_entities.extend(sub_entities)

        return result_entities

    def _get_if_node_is_destination(self, node: DagNode) -> bool:
        """Get if a node is a destination."""
        return node.type == NodeType.destination

    async def _apply_transformer(self, consumer: DagNode, entity: BaseEntity) -> list[BaseEntity]:
        """Apply the transformer to the entity."""
        entity_context = f"Entity({entity.entity_id})"

        if consumer.transformer_id:
            # Use cached transformer instead of database lookup
            transformer = self._transformer_cache.get(consumer.transformer_id)
            if not transformer:
                self.logger.warning(
                    f"Transformer {consumer.transformer_id} not in cache, falling back to lookup"
                )
                # Create a temporary database session just for this lookup
                from airweave.db.session import get_db_context

                async with get_db_context() as db:
                    transformer = await crud.transformer.get(db, id=consumer.transformer_id)
                    # Cache for future use
                    if transformer:
                        self._transformer_cache[consumer.transformer_id] = transformer

            transformer_callable = resource_locator.get_transformer(transformer)
            result = await transformer_callable(entity, self.logger)

            return result
        else:
            self.logger.error(
                f"❌ ROUTER_NO_TRANSFORMER [{entity_context}] "
                f"No transformer found for node {consumer.id}"
            )
            raise ValueError(f"No transformer found for node {consumer.id}")
