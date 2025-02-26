"""DAG router."""

from typing import Optional
from uuid import UUID

from app.platform.entities._base import BaseEntity
from app.schemas.dag import DagNode, NodeType, SyncDag


class SyncDAGRouter:
    """Routes entities through the DAG based on producer and entity type."""

    def __init__(
        self,
        dag: SyncDag,
    ):
        """Initialize the DAG router."""
        self.dag = dag
        self.route = self._build_execution_route()

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

                # It's only allowed to have multiple consumers if the entity is sent to destinations
                if len(edges_outwards) > 1:
                    consumer_nodes = [
                        self.dag.get_node(edge.from_node_id) for edge in edges_outwards
                    ]
                    if any(
                        consumer_node.type != NodeType.destination
                        for consumer_node in consumer_nodes
                    ):
                        raise ValueError(
                            f"Entity node {node.id} has multiple outbound edges"
                            "to non-destination nodes."
                        )
                    # Setting to None stops the entity from being routed further
                    route_map[(producer, node.entity_definition_id)] = None
                elif len(edges_outwards) == 1 and self._get_if_node_is_destination(
                    self.dag.get_node(edges_outwards[0].to_node_id)
                ):
                    route_map[(producer, node.entity_definition_id)] = None
                else:
                    raise ValueError(
                        f"Entity node {node.id} has no outbound edges to a destination."
                    )

        return route_map

    async def process_entity(self, producer_id: UUID, entity: BaseEntity) -> list[BaseEntity]:
        """Route an entity to its next destinations based on DAG structure.

        Returning condition:
        - If the entity is sent to a destination, return it, so the orchestrator can send it to the
          destinations
        - If the entity is sent to a transformer, return the transformed entities, so the next
          transformer can be called until the entity is sent to a destination
        """
        route_key = (producer_id, entity.entity_definition_id)
        if route_key not in self.route:
            raise ValueError(f"No route found for entity {entity.entity_definition_id}")

        consumer_id = self.route[route_key]

        # If the entity is sent to a destination, return it
        if consumer_id is None:
            return [entity]

        # Get the consumer node
        consumer = self.dag.get_node(consumer_id)

        # Apply the transformer
        transformed_entities = await self._apply_transformer(consumer, entity)

        # Route the transformed entities
        result_entities = []
        for transformed_entity in transformed_entities:
            result_entities.extend(await self.process_entity(consumer_id, transformed_entity))

        return result_entities

    def _get_if_node_is_destination(self, node: DagNode) -> bool:
        """Get if a node is a destination."""
        return node.type == NodeType.destination
