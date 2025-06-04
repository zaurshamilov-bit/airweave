"""Module for entity processing within the sync architecture."""

import asyncio
from typing import Dict, List, Optional, Set

from sqlalchemy.ext.asyncio import AsyncSession

from airweave import crud, schemas
from airweave.platform.entities._base import BaseEntity, DestinationAction
from airweave.platform.sync.context import SyncContext


class EntityProcessor:
    """Processes entities through a pipeline of stages."""

    def __init__(self):
        """Initialize the entity processor with empty tracking dictionary."""
        self._entities_encountered_count: Dict[str, Set[str]] = {}

    def initialize_tracking(self, sync_context: SyncContext) -> None:
        """Initialize entity tracking with entity types from the DAG.

        Args:
            sync_context: The sync context containing the DAG
        """
        self._entities_encountered_count.clear()

        # Get all entity nodes from the DAG
        entity_nodes = [
            node for node in sync_context.dag.nodes if node.type == schemas.dag.NodeType.entity
        ]

        # Create a dictionary with entity names as keys and empty sets as values
        for node in entity_nodes:
            if node.name.endswith("Entity"):
                self._entities_encountered_count[node.name] = set()

    async def process(
        self,
        entity: BaseEntity,
        source_node: schemas.DagNode,
        sync_context: SyncContext,
        db: AsyncSession,
    ) -> List[BaseEntity]:
        """Process an entity through the complete pipeline."""
        # Flag to track if we've already accounted for this entity in stats
        entity_accounted_for = False

        # Get entity number for logging (default to "?" if not set)
        entity_number = getattr(entity, "entity_number", "?")

        try:
            sync_context.logger.info(
                f"Processing entity #{entity_number} ({entity.entity_id}) through pipeline"
            )

            # Track the current entity
            entity_type = entity.__class__.__name__

            # Validate entity type is known
            if entity_type not in self._entities_encountered_count:
                self._entities_encountered_count[entity_type] = set()

            # If we encounter the same entity from a different path, silently skip it
            if entity.entity_id in self._entities_encountered_count[entity_type]:
                sync_context.logger.info("\nalready encountered this entity, so silently skip\n")
                return []

            # Add the entity id to the entity_type set - we're processing it now
            self._entities_encountered_count[entity_type].add(entity.entity_id)

            # Update progress tracker with latest entities encountered
            await sync_context.progress.update_entities_encountered_count(
                self._entities_encountered_count
            )

            # Stage 1: Enrich entity with metadata
            enriched_entity = await self._enrich(entity, sync_context)

            # Stage 2: Determine action for entity
            db_entity, action = await self._determine_action(enriched_entity, sync_context, db)
            sync_context.logger.info(
                f"Determined action {action} for entity #{entity_number} ({entity.entity_id})"
            )

            # Stage 2.5: Skip further processing if KEEP
            if action == DestinationAction.KEEP:
                await sync_context.progress.increment("kept", 1)
                entity_accounted_for = True
                return []

            # Stage 3: Process entity through DAG
            processed_entities = await self._transform(
                enriched_entity, source_node, sync_context, db
            )
            sync_context.logger.info(
                f"Transformed entity #{entity_number} ({entity.entity_id}) into "
                f"{len(processed_entities)} entities"
            )

            # Check if transformation resulted in no entities
            if len(processed_entities) == 0:
                sync_context.logger.warning(
                    f"Transformation resulted in 0 entities for #{entity_number} "
                    f"({entity.entity_id}), marking as skipped"
                )
                await sync_context.progress.increment("skipped", 1)
                entity_accounted_for = True
                return []

            # Stage 4: Compute vector
            processed_entities_with_vector = await self._compute_vector(
                processed_entities, sync_context
            )

            # Stage 5: Persist entities based on action
            await self._persist(
                enriched_entity, processed_entities_with_vector, db_entity, action, sync_context, db
            )

            entity_accounted_for = True
            return processed_entities

        except Exception as e:
            sync_context.logger.error(
                f"Error processing entity #{entity_number} ({entity.entity_id}): "
                f"{type(e).__name__}: {str(e)}"
            )

            # If we haven't already accounted for this entity in stats, mark it as skipped
            if not entity_accounted_for:
                await sync_context.progress.increment("skipped", 1)
                sync_context.logger.warning(
                    f"Entity #{entity_number} ({entity.entity_id}) marked as skipped "
                    f"due to processing error"
                )

            # DON'T RE-RAISE! Just return empty list to indicate no entities were produced
            # This allows the sync to continue with other entities
            return []

    async def _enrich(self, entity: BaseEntity, sync_context: SyncContext) -> BaseEntity:
        """Enrich entity with sync metadata."""
        entity.source_name = sync_context.source._name
        entity.sync_id = sync_context.sync.id
        entity.sync_job_id = sync_context.sync_job.id
        entity.sync_metadata = sync_context.sync.sync_metadata

        return entity

    async def _determine_action(
        self, entity: BaseEntity, sync_context: SyncContext, db: AsyncSession
    ) -> tuple[schemas.Entity, DestinationAction]:
        """Determine what action to take for an entity."""
        sync_context.logger.info(
            f"Determining action for entity {entity.entity_id} (type: {type(entity).__name__})"
        )

        db_entity = await crud.entity.get_by_entity_and_sync_id(
            db=db, entity_id=entity.entity_id, sync_id=sync_context.sync.id
        )

        # Hash computation can be CPU-bound, run in thread pool
        current_hash = await asyncio.to_thread(entity.hash)

        if db_entity:
            sync_context.logger.info(
                f"Found existing entity in DB with id {db_entity.id}, "
                f"comparing hashes: stored={db_entity.hash}, current={current_hash}"
            )

            if db_entity.hash != current_hash:
                action = DestinationAction.UPDATE
                sync_context.logger.info(
                    f"Hashes differ for entity {entity.entity_id}, will UPDATE"
                )
            else:
                action = DestinationAction.KEEP
                sync_context.logger.info(
                    f"Hashes match for entity {entity.entity_id}, will KEEP (no changes)"
                )
        else:
            action = DestinationAction.INSERT
            sync_context.logger.info(
                f"No existing entity found for {entity.entity_id} in sync "
                f"{sync_context.sync.id}, will INSERT"
            )

        return db_entity, action

    async def _transform(
        self,
        entity: BaseEntity,
        source_node: schemas.DagNode,
        sync_context: SyncContext,
        db: AsyncSession,
    ) -> List[BaseEntity]:
        """Transform entity through DAG routing."""
        sync_context.logger.info(
            f"Starting transformation for entity {entity.entity_id} "
            f"(type: {type(entity).__name__}) from source node {source_node.id}"
        )

        transformed_entities = await sync_context.router.process_entity(
            db=db,
            producer_id=source_node.id,
            entity=entity,
        )

        # Log details about the transformed entities
        entity_types = {}
        for e in transformed_entities:
            entity_type = type(e).__name__
            if entity_type in entity_types:
                entity_types[entity_type] += 1
            else:
                entity_types[entity_type] = 1

        type_summary = ", ".join([f"{count} {t}" for t, count in entity_types.items()])
        sync_context.logger.info(
            f"Transformation complete: entity {entity.entity_id} transformed into "
            f"{len(transformed_entities)} entities ({type_summary})"
        )

        return transformed_entities

    async def _persist(
        self,
        parent_entity: BaseEntity,
        processed_entities: List[BaseEntity],
        db_entity: schemas.Entity,
        action: DestinationAction,
        sync_context: SyncContext,
        db: AsyncSession,
    ) -> None:
        """Persist entities to destinations based on action.

        Args:
            parent_entity: The parent entity of the processed entities
            processed_entities: The entities to persist
            db_entity: The database entity to update
            action: The action to take
            sync_context: The sync context
            db: The database session
        """
        if action == DestinationAction.KEEP:
            await self._handle_keep(sync_context)
        elif action == DestinationAction.INSERT:
            await self._handle_insert(
                parent_entity, processed_entities, db_entity, sync_context, db
            )
        elif action == DestinationAction.UPDATE:
            await self._handle_update(
                parent_entity, processed_entities, db_entity, sync_context, db
            )

    async def _compute_vector(
        self,
        processed_entities: List[BaseEntity],
        sync_context: SyncContext,
    ) -> List[BaseEntity]:
        """Compute vector for entities.

        Args:
            processed_entities: The entities to compute vector for
            sync_context: The sync context

        Returns:
            The entities with vector computed
        """
        if not processed_entities:
            sync_context.logger.info("No entities to vectorize, returning empty list")
            return []

        try:
            entity_context = self._get_entity_context(processed_entities)
            self._log_vectorization_start(processed_entities, sync_context, entity_context)

            # Convert entities to dictionaries for embedding
            entity_dicts = await self._convert_entities_to_dicts(processed_entities, sync_context)

            # Get embeddings from the model
            embeddings = await self._get_embeddings(entity_dicts, sync_context, entity_context)

            # Assign vectors to entities
            processed_entities = await self._assign_vectors_to_entities(
                processed_entities, embeddings, sync_context
            )

            return processed_entities

        except Exception as e:
            sync_context.logger.error(f"Error computing vectors: {str(e)}")
            raise

    def _get_entity_context(self, processed_entities: List[BaseEntity]) -> str:
        """Get entity context string for logging."""
        if processed_entities:
            first_entity = processed_entities[0]
            entity_number = getattr(first_entity, "entity_number", "?")
            return f"Entity #{entity_number} batch"
        return "Entity batch"

    def _log_vectorization_start(
        self, processed_entities: List[BaseEntity], sync_context: SyncContext, entity_context: str
    ) -> None:
        """Log vectorization startup information."""
        embedding_model = sync_context.embedding_model
        entity_count = len(processed_entities)

        sync_context.logger.info(
            f"Computing vectors for {entity_count} entities using {embedding_model.model_name}"
        )

        # Log entity content lengths for debugging
        content_lengths = [len(str(entity.to_storage_dict())) for entity in processed_entities]
        total_length = sum(content_lengths)
        avg_length = total_length / entity_count if entity_count else 0
        max_length = max(content_lengths) if content_lengths else 0

        sync_context.logger.info(
            f"Entity content stats: total={total_length}, "
            f"avg={avg_length:.2f}, max={max_length}, count={entity_count}"
        )

    async def _convert_entities_to_dicts(
        self, processed_entities: List[BaseEntity], sync_context: SyncContext
    ) -> List[str]:
        """Convert entities to dictionary representations."""

        def _convert_entities_to_dicts_sync(entities):
            entity_dicts = []
            for entity in entities:
                try:
                    entity_dict = str(entity.to_storage_dict())
                    entity_dicts.append(entity_dict)
                except Exception as e:
                    sync_context.logger.error(f"Error converting entity to dict: {str(e)}")
                    # Provide a fallback empty string to maintain array alignment
                    entity_dicts.append("")
            return entity_dicts

        return await asyncio.to_thread(_convert_entities_to_dicts_sync, processed_entities)

    async def _get_embeddings(
        self, entity_dicts: List[str], sync_context: SyncContext, entity_context: str
    ) -> List[List[float]]:
        """Get embeddings from the embedding model."""
        import asyncio
        import inspect

        embedding_model = sync_context.embedding_model
        loop = asyncio.get_event_loop()
        cpu_start = loop.time()

        # Get embeddings from the model with entity context
        if hasattr(embedding_model, "embed_many"):
            # Check if the embedding model supports entity_context parameter
            embed_many_signature = inspect.signature(embedding_model.embed_many)
            if "entity_context" in embed_many_signature.parameters:
                embeddings = await embedding_model.embed_many(
                    entity_dicts, entity_context=entity_context
                )
            else:
                embeddings = await embedding_model.embed_many(entity_dicts)
        else:
            embeddings = await embedding_model.embed_many(entity_dicts)

        cpu_elapsed = loop.time() - cpu_start
        sync_context.logger.info(
            f"Vector computation completed in {cpu_elapsed:.2f}s for {len(embeddings)} entities"
        )

        return embeddings

    async def _assign_vectors_to_entities(
        self,
        processed_entities: List[BaseEntity],
        embeddings: List[List[float]],
        sync_context: SyncContext,
    ) -> List[BaseEntity]:
        """Assign vectors to entities."""
        # Validate we got the expected number of embeddings
        if len(embeddings) != len(processed_entities):
            sync_context.logger.warning(
                f"Embedding count mismatch: got {len(embeddings)} embeddings "
                f"for {len(processed_entities)} entities"
            )

        # Assign vectors to entities in thread pool (CPU-bound operation for many entities)
        def _assign_vectors_to_entities_sync(entities, vectors):
            for i, (processed_entity, vector) in enumerate(zip(entities, vectors, strict=False)):
                try:
                    if vector is None:
                        sync_context.logger.warning(f"Received None vector for entity at index {i}")
                        continue

                    vector_dim = len(vector) if vector else 0
                    sync_context.logger.info(
                        f"Assigning vector of dimension {vector_dim} to "
                        f"entity {processed_entity.entity_id}"
                    )
                    processed_entity.vector = vector
                except Exception as e:
                    sync_context.logger.error(
                        f"Error assigning vector to entity at index {i}: {str(e)}"
                    )
            return entities

        return await asyncio.to_thread(
            _assign_vectors_to_entities_sync, processed_entities, embeddings
        )

    async def _handle_keep(self, sync_context: SyncContext) -> None:
        """Handle KEEP action."""
        await sync_context.progress.increment(kept=1)

    async def _handle_insert(
        self,
        parent_entity: BaseEntity,
        processed_entities: List[BaseEntity],
        db_entity: Optional[schemas.Entity],
        sync_context: SyncContext,
        db: AsyncSession,
    ) -> None:
        """Handle INSERT action."""
        if len(processed_entities) == 0:
            sync_context.logger.warning(
                f"No processed entities to insert for {parent_entity.entity_id}, marking as skipped"
            )
            await sync_context.progress.increment("skipped", 1)
            return

        # Prepare entities with parent reference
        for processed_entity in processed_entities:
            if (
                not hasattr(processed_entity, "parent_entity_id")
                or not processed_entity.parent_entity_id
            ):
                processed_entity.parent_entity_id = parent_entity.entity_id

        # Insert into database - hash computation is CPU-bound
        parent_hash = await asyncio.to_thread(parent_entity.hash)
        new_db_entity = await crud.entity.create(
            db=db,
            obj_in=schemas.EntityCreate(
                sync_job_id=sync_context.sync_job.id,
                sync_id=sync_context.sync.id,
                entity_id=parent_entity.entity_id,
                hash=parent_hash,
            ),
            organization_id=sync_context.sync.organization_id,
        )
        parent_entity.db_entity_id = new_db_entity.id

        # Insert to destinations
        for destination in sync_context.destinations:
            await destination.bulk_insert(processed_entities)

        await sync_context.progress.increment("inserted", 1)

    async def _handle_update(
        self,
        parent_entity: BaseEntity,
        processed_entities: List[BaseEntity],
        db_entity: schemas.Entity,
        sync_context: SyncContext,
        db: AsyncSession,
    ) -> None:
        """Handle UPDATE action."""
        if len(processed_entities) == 0:
            sync_context.logger.warning(
                f"No processed entities to update for {parent_entity.entity_id}, marking as skipped"
            )
            await sync_context.progress.increment("skipped", 1)
            return

        # Prepare entities with parent reference
        for processed_entity in processed_entities:
            if (
                not hasattr(processed_entity, "parent_entity_id")
                or not processed_entity.parent_entity_id
            ):
                processed_entity.parent_entity_id = parent_entity.entity_id

        # Update hash in database - hash computation is CPU-bound
        parent_hash = await asyncio.to_thread(parent_entity.hash)
        await crud.entity.update(
            db=db,
            db_obj=db_entity,
            obj_in=schemas.EntityUpdate(hash=parent_hash),
        )
        parent_entity.db_entity_id = db_entity.id

        # Update in destinations (delete then insert)
        for destination in sync_context.destinations:
            await destination.bulk_delete_by_parent_id(
                parent_entity.entity_id, sync_context.sync.id
            )
            await destination.bulk_insert(processed_entities)

        await sync_context.progress.increment("updated", 1)
