from typing import AsyncGenerator, Dict, List, Set, Tuple
from uuid import UUID

from app.crud import crud_entity
from app.db.session import AsyncSession
from app.platform.entities._base import BaseEntity
from app.schemas.dag import DagNode, SyncDagDefinition
from app.schemas.entity import Entity as DbEntity


class EntityProcessingResult:
    """Result of processing an entity through a node."""

    def __init__(
        self,
        entity: BaseEntity,
        db_entity: DbEntity | None = None,
        action: Literal["insert", "update", "skip"] = "insert",
    ):
        self.entity = entity
        self.db_entity = db_entity
        self.action = action


class EntityRouter:
    def __init__(
        self, dag: SyncDagDefinition, db: AsyncSession, sync_id: UUID, organization_id: UUID
    ):
        self.dag = dag
        self.db = db
        self.sync_id = sync_id
        self.organization_id = organization_id
        self.entity_routes = self._build_routes()
        self.processed_entities: Set[str] = set()  # Track processed entity_ids

    def _build_routes(self) -> Dict[Tuple[UUID, str], List[DagNode]]:
        """Build routing table mapping (producer_id, entity_type) to next nodes"""
        routes = {}
        for node in self.dag.nodes:
            if node.type == "entity":
                producers = self._get_producers(node)
                consumers = self._get_consumers(node)

                for producer in producers:
                    key = (producer.id, node.entity_definition_id)
                    routes[key] = consumers
        return routes

    async def process_entity(
        self,
        producer_node: DagNode,
        entity: BaseEntity,
    ) -> AsyncGenerator[EntityProcessingResult, None]:
        """Process an entity through the DAG, handling versioning and routing.
        Yields EntityProcessingResult for each processed entity.
        """
        # Skip if we've already processed this entity
        if entity.entity_id in self.processed_entities:
            return

        self.processed_entities.add(entity.entity_id)

        # Check version and get processing action
        db_entity = await self._check_version(entity)

        # Create processing result for initial entity
        result = EntityProcessingResult(
            entity=entity,
            db_entity=db_entity,
            action=(
                "skip"
                if db_entity and db_entity.hash == entity.hash
                else "update" if db_entity else "insert"
            ),
        )

        # Always yield the initial entity result
        yield result

        # Find and process through next nodes
        route_key = (producer_node.id, entity.__class__.__name__)
        next_nodes = self.entity_routes.get(route_key, [])

        for node in next_nodes:
            # Process through node (transformer or destination)
            async for processed_result in self._process_through_node(node, result):
                yield processed_result

    async def _check_version(self, entity: BaseEntity) -> DbEntity | None:
        """Check if entity exists and get its current version."""
        return await crud_entity.get_by_entity_id(
            self.db,
            entity_id=entity.entity_id,
            sync_id=self.sync_id,
            organization_id=self.organization_id,
        )

    async def _process_through_node(
        self,
        node: DagNode,
        input_result: EntityProcessingResult,
    ) -> AsyncGenerator[EntityProcessingResult, None]:
        """Process an entity through a node (transformer or destination)"""
        if node.type == "transformer":
            transformer = self._get_transformer(node)
            # Transform entity and yield results
            async for transformed_entity in transformer.transform(input_result.entity):
                # Check version for transformed entity
                db_entity = await self._check_version(transformed_entity)
                yield EntityProcessingResult(
                    entity=transformed_entity,
                    db_entity=db_entity,
                    action=(
                        "skip"
                        if db_entity and db_entity.hash == transformed_entity.hash
                        else "update" if db_entity else "insert"
                    ),
                )

        elif node.type == "destination":
            destination = self._get_destination(node)
            # Process based on action
            if input_result.action == "insert":
                await destination.insert(input_result.entity)
            elif input_result.action == "update":
                await destination.update(input_result.entity)
            # Skip if action is "skip"
