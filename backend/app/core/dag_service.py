"""DAG service."""

from typing import Dict, List, Optional, Set, Tuple, Type
from uuid import UUID, uuid4

from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app import crud, schemas
from app.db.unit_of_work import UnitOfWork
from app.platform.entities._base import BaseEntity, ChunkEntity, FileEntity, ParentEntity
from app.platform.locator import resource_locator
from app.schemas.dag import DagEdgeCreate, DagNodeCreate, SyncDagCreate


class DagService:
    """DAG service."""

    async def create_initial_dag(
        self,
        db: AsyncSession,
        *,
        sync_id: UUID,
        current_user: schemas.User,
        uow: UnitOfWork,
    ) -> schemas.SyncDag:
        """Create an initial DAG with source, entities, and destination."""
        # Get sync and validate
        sync = await self._get_and_validate_sync(db, sync_id, current_user)

        # Get file chunker transformer
        file_chunker = await self._get_file_chunker(db)

        # Get source connection and entity definitions
        source, source_connection, entity_definitions = (
            await self._get_source_and_entity_definitions(db, sync, current_user)
        )

        # Get or create destination
        destination, destination_connection = await self._get_destination(db, sync, current_user)

        # Initialize DAG components
        nodes: List[DagNodeCreate] = []
        edges: List[DagEdgeCreate] = []
        processed_entity_ids: Set[UUID] = set()

        # Create source and destination nodes
        source_node_id = uuid4()
        destination_node_id = uuid4()

        # Add source node
        nodes.append(
            DagNodeCreate(
                id=source_node_id,
                type="source",
                name=source.name,
                connection_id=source_connection.id,
            )
        )

        # Add destination node
        nodes.append(
            DagNodeCreate(
                id=destination_node_id,
                type="destination",
                name=destination.name,
                connection_id=destination_connection.id if destination_connection else None,
            )
        )

        # Process entity definitions
        for entity_definition_id, entity_data in entity_definitions.items():
            if entity_definition_id in processed_entity_ids:
                continue

            processed_entity_ids.add(entity_definition_id)
            entity_class = entity_data["entity_class"]
            entity_definition = entity_data["entity_definition"]

            # Handle file entities
            if issubclass(entity_class, FileEntity):
                await self._process_file_entity(
                    db=db,
                    entity_class=entity_class,
                    entity_definition=entity_definition,
                    file_chunker=file_chunker,
                    source_node_id=source_node_id,
                    destination_node_id=destination_node_id,
                    nodes=nodes,
                    edges=edges,
                    processed_entity_ids=processed_entity_ids,
                )
            # Handle regular entities
            else:
                entity_node_id = uuid4()
                nodes.append(
                    DagNodeCreate(
                        id=entity_node_id,
                        type="entity",
                        name=entity_definition.name,
                        entity_definition_id=entity_definition_id,
                    )
                )

                # Connect source to entity
                edges.append(
                    DagEdgeCreate(
                        from_node_id=source_node_id,
                        to_node_id=entity_node_id,
                    )
                )

                # Connect entity to destination
                edges.append(
                    DagEdgeCreate(
                        from_node_id=entity_node_id,
                        to_node_id=destination_node_id,
                    )
                )

        # Create and return the DAG
        sync_dag_create = SyncDagCreate(
            name=f"DAG for {sync.name}",
            sync_id=sync_id,
            nodes=nodes,
            edges=edges,
        )

        sync_dag = await crud.sync_dag.create_with_nodes_and_edges(
            db, obj_in=sync_dag_create, current_user=current_user, uow=uow
        )

        return schemas.SyncDag.model_validate(sync_dag, from_attributes=True)

    async def _get_and_validate_sync(
        self, db: AsyncSession, sync_id: UUID, current_user: schemas.User
    ) -> schemas.Sync:
        """Get and validate sync exists."""
        sync = await crud.sync.get(db, id=sync_id, current_user=current_user)
        if not sync:
            raise Exception(f"Sync for {sync_id} not found")
        return sync

    async def _get_file_chunker(self, db: AsyncSession) -> schemas.Transformer:
        """Get the file chunker transformer."""
        transformers = await crud.transformer.get_all(db)
        file_chunker = next(
            (t for t in transformers if t.method_name == "file_chunker"),
            None,
        )
        if not file_chunker:
            raise Exception("No file chunker found")
        return file_chunker

    async def _get_source_and_entity_definitions(
        self, db: AsyncSession, sync: schemas.Sync, current_user: schemas.User
    ) -> Tuple[schemas.Source, schemas.Connection, Dict]:
        """Get source connection and entity definitions."""
        source_connection = await crud.connection.get(
            db, id=sync.source_connection_id, current_user=current_user
        )
        if not source_connection:
            raise Exception(f"Source connection for {sync.source_connection_id} not found")

        source = await crud.source.get_by_short_name(db, short_name=source_connection.short_name)

        entity_definitions = await crud.entity_definition.get_multi_by_ids(
            db, ids=source.output_entity_definition_ids
        )

        entity_definitions_dict = {
            entity_definition.id: {
                "entity_class": resource_locator.get_entity_definition(entity_definition),
                "entity_definition": entity_definition,
            }
            for entity_definition in entity_definitions
        }

        return source, source_connection, entity_definitions_dict

    async def _get_destination(
        self, db: AsyncSession, sync: schemas.Sync, current_user: schemas.User
    ) -> Tuple[schemas.Destination, Optional[schemas.Connection]]:
        """Get or create destination."""
        if sync.destination_connection_id:
            destination_connection = await crud.connection.get(
                db, id=sync.destination_connection_id, current_user=current_user
            )
            if not destination_connection:
                raise HTTPException(status_code=404, detail="Destination connection not found")

            destination = await crud.destination.get_by_short_name(
                db, short_name=destination_connection.short_name
            )
            return destination, destination_connection
        else:
            destination = await crud.destination.get_by_short_name(db, short_name="weaviate_native")
            return destination, None

    async def _process_file_entity(
        self,
        db: AsyncSession,
        entity_class: Type[FileEntity],
        entity_definition: schemas.EntityDefinition,
        file_chunker: schemas.Transformer,
        source_node_id: UUID,
        destination_node_id: UUID,
        nodes: List[DagNodeCreate],
        edges: List[DagEdgeCreate],
        processed_entity_ids: Set[UUID],
    ) -> None:
        """Process a file entity and create necessary nodes and edges."""
        # Get parent and chunk entity classes
        parent_entity_class, chunk_entity_class = entity_class.create_parent_chunk_models()

        # Get entity definitions for parent and chunk
        parent_entity_definition = await self._get_entity_definition_for_entity_class(
            db, parent_entity_class
        )
        chunk_entity_definition = await self._get_entity_definition_for_entity_class(
            db, chunk_entity_class
        )

        # Mark parent and chunk entity definitions as processed
        if parent_entity_definition:
            processed_entity_ids.add(parent_entity_definition.id)
        if chunk_entity_definition:
            processed_entity_ids.add(chunk_entity_definition.id)

        # Create file entity node
        file_node_id = uuid4()
        nodes.append(
            DagNodeCreate(
                id=file_node_id,
                type="entity",
                name=entity_definition.name,
                entity_definition_id=entity_definition.id,
            )
        )

        # Create file chunker transformer node
        chunker_node_id = uuid4()
        nodes.append(
            DagNodeCreate(
                id=chunker_node_id,
                type="transformer",
                name=file_chunker.name,
                transformer_id=file_chunker.id,
            )
        )

        # Create parent chunk node
        parent_node_id = uuid4()
        nodes.append(
            DagNodeCreate(
                id=parent_node_id,
                type="entity",
                name=parent_entity_definition.name,
                entity_definition_id=parent_entity_definition.id,
            )
        )

        # Create chunk entity node
        chunk_node_id = uuid4()
        nodes.append(
            DagNodeCreate(
                id=chunk_node_id,
                type="entity",
                name=chunk_entity_definition.name,
                entity_definition_id=chunk_entity_definition.id,
            )
        )

        # Create edges
        # Source -> File Entity
        edges.append(DagEdgeCreate(from_node_id=source_node_id, to_node_id=file_node_id))

        # File Entity -> File Chunker
        edges.append(DagEdgeCreate(from_node_id=file_node_id, to_node_id=chunker_node_id))

        # File Chunker -> Parent Entity
        edges.append(DagEdgeCreate(from_node_id=chunker_node_id, to_node_id=parent_node_id))

        # File Chunker -> Chunk Entity
        edges.append(DagEdgeCreate(from_node_id=chunker_node_id, to_node_id=chunk_node_id))

        # Parent Entity -> Destination
        edges.append(DagEdgeCreate(from_node_id=parent_node_id, to_node_id=destination_node_id))

        # Chunk Entity -> Destination
        edges.append(DagEdgeCreate(from_node_id=chunk_node_id, to_node_id=destination_node_id))

    async def _get_parent_and_chunk_entity_classes_for_entity_definition(
        self, entity_definition: schemas.EntityDefinition
    ) -> tuple[Type[ParentEntity], Type[ChunkEntity]]:
        """Get the parent and chunk entity classes for a given entity definition.

        Args:
        ----
            entity_definition (schemas.EntityDefinition): The entity definition to get the parent
                and chunk entity classes for.

        Returns:
        -------
            tuple[Type[ParentEntity], Type[ChunkEntity]]: The parent and chunk entity classes.
        """
        entity_class = resource_locator.get_entity_definition(entity_definition)
        return entity_class.create_parent_chunk_models()

    async def _get_entity_definition_for_entity_class(
        self, db: AsyncSession, entity_class: Type[BaseEntity]
    ) -> schemas.EntityDefinition:
        """Get the entity definition for a given entity class.

        Args:
        ----
            db (AsyncSession): The database session.
            entity_class (Type[BaseEntity]): The entity class to get the entity definition for.

        Returns:
        -------
            schemas.EntityDefinition: The entity definition.
        """
        entity_definition = await crud.entity_definition.get_by_entity_class_name(
            db, entity_class_name=entity_class.__name__
        )
        return entity_definition


dag_service = DagService()
