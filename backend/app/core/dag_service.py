"""DAG service."""

from uuid import UUID

from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app import crud, schemas
from app.schemas.dag import DagEdgeCreate, DagNodeCreate, SyncDagDefinitionCreate


class DagService:
    """DAG service."""

    @staticmethod
    async def create_initial_dag(
        db: AsyncSession,
        *,
        sync_id: UUID,
        current_user: schemas.User,
    ) -> schemas.SyncDagDefinitionCreate:
        """Create an initial DAG with source, entities, and destination."""
        ## Get sync
        sync = await crud.sync.get(db, id=sync_id, current_user=current_user)

        ## Get entities from the source
        source_connection = await crud.connection.get(
            db, id=sync.source_connection_id, current_user=current_user
        )
        if not source_connection:
            raise HTTPException(status_code=404, detail="Source connection not found")

        source = await crud.source.get_by_short_name(db, short_name=source_connection.short_name)
        output_entity_definition_ids = source.output_entity_definition_ids

        entity_definitions = await crud.entity_definition.get_multi_by_ids(
            db, ids=output_entity_definition_ids
        )

        nodes: list[DagNodeCreate] = []
        edges: list[DagEdgeCreate] = []

        # Create source node
        source_node = DagNodeCreate(
            type="source",
            name=source.name,
            source_id=source.id,
        )
        nodes.append(source_node)

        # Create entity nodes
        for entity_definition in entity_definitions:
            entity_node = DagNodeCreate(
                type="entity",
                name=entity_definition.name,
                entity_definition_id=entity_definition.id,
            )
            nodes.append(entity_node)

        # Create destination node
        if sync.destination_connection_id:
            destination_connection = await crud.connection.get(
                db, id=sync.destination_connection_id, current_user=current_user
            )
            if not destination_connection:
                raise HTTPException(status_code=404, detail="Destination connection not found")

            destination_connection = await crud.connection.get(
                db, id=destination_connection.id, current_user=current_user
            )
            destination_node = DagNodeCreate(
                type="destination",
                name="Native",
                destination_id=destination_connection.destination_id,
            )
        else:
            destination = await crud.destination.get_by_short_name(db, short_name="weaviate_native")
            destination_node = DagNodeCreate(
                type="destination",
                name="Native Weaviate",
                destination_id=destination.id,
            )
        nodes.append(destination_node)

        # Create edges
        for node in nodes:
            if node.type == "source":
                edges.append(DagEdgeCreate(from_node_id=node.id, to_node_id=nodes[1].id))
            elif node.type == "entity":
                edges.append(DagEdgeCreate(from_node_id=node.id, to_node_id=nodes[2].id))

        sync_dag_definition_create = SyncDagDefinitionCreate(
            name=f"DAG for {sync.name}",
            nodes=nodes,
            edges=edges,
        )

        sync_dag_definition = await crud.sync_dag_definition.create(
            db, obj_in=sync_dag_definition_create, current_user=current_user
        )

        return schemas.SyncDagDefinition.model_validate(sync_dag_definition, from_attributes=True)


dag_service = DagService()
