"""DAG service."""

from uuid import UUID

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
        source_connection = await crud.connection.get(
            db, id=sync.source_connection_id, current_user=current_user
        )
        destination_connection = await crud.connection.get(
            db, id=sync.destination_connection_id, current_user=current_user
        )

        source_connection = await crud.connection.get(
            db, id=source_connection.id, current_user=current_user
        )
        destination_connection = await crud.connection.get(
            db, id=destination_connection.id, current_user=current_user
        )

        ## Get entities from the source
        source = await crud.source.get(db, id=sync.source_id, current_user=current_user)
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
        destination_node = DagNodeCreate(
            type="destination",
            name="Destination",
            destination_id=sync.destination_id,
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
