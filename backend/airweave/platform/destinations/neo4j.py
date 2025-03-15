"""Neo4j destination implementation."""

import os
from uuid import UUID

from neo4j import AsyncGraphDatabase

from airweave import schemas
from airweave.platform.decorators import destination
from airweave.platform.destinations._base import GraphDBDestination
from airweave.platform.entities._base import ChunkEntity


@destination("Neo4j", "neo4j", labels=["Graph"])
class Neo4jDestination(GraphDBDestination):
    """Neo4j destination implementation."""

    def __init__(self):
        """Initialize the Neo4j destination."""
        self.driver = None
        self.db_uri = None
        self.user = None
        self.password = None

    async def get_credentials(self, user: schemas.User) -> None:
        """Load credentials for connecting to Neo4j from environment variables."""
        self.db_uri = os.getenv("NEO4J_URI", "bolt://localhost:7687")
        self.user = os.getenv("NEO4J_USER", "neo4j")
        self.password = os.getenv("NEO4J_PASSWORD", "password")
        self.driver = AsyncGraphDatabase.driver(self.db_uri, auth=(self.user, self.password))

    async def create(self, user: schemas.User) -> None:
        """Initialize the Neo4j destination by loading credentials and setting up the driver."""
        await self.get_credentials(user)

    async def setup_collection(self, sync_id: UUID) -> None:
        """Set up the graph by creating necessary constraints.

        For example, a uniqueness constraint on db_entity_id for Entity nodes.
        """
        query = "CREATE CONSTRAINT IF NOT EXISTS FOR (c:Entity) REQUIRE c.db_entity_id IS UNIQUE"
        async with self.driver.session() as session:
            await session.run(query)

    async def insert(self, entity: ChunkEntity) -> None:
        """Insert a single entity as a node in Neo4j.

        The entity is stored as a node with label 'Entity'.
        """
        data = entity.model_dump()
        query = "CREATE (c:Entity) SET c = $props"
        async with self.driver.session() as session:
            await session.run(query, props=data)

    async def bulk_insert(self, entities: list[ChunkEntity]) -> None:
        """Bulk insert entities as nodes in Neo4j using UNWIND."""
        nodes = [entity.model_dump() for entity in entities]
        query = "UNWIND $nodes as props CREATE (c:Entity) SET c = props"
        async with self.driver.session() as session:
            await session.run(query, nodes=nodes)

    async def delete(self, db_entity_id: UUID) -> None:
        """Delete a single entity node from Neo4j identified by its db_entity_id."""
        query = "MATCH (c:Entity {db_entity_id: $id}) DETACH DELETE c"
        async with self.driver.session() as session:
            await session.run(query, id=str(db_entity_id))

    async def bulk_delete(self, entity_ids: list[str]) -> None:
        """Bulk delete entity nodes from Neo4j whose db_entity_id is in the provided list."""
        query = "MATCH (c:Entity) WHERE c.db_entity_id IN $ids DETACH DELETE c"
        async with self.driver.session() as session:
            await session.run(query, ids=entity_ids)

    async def search_for_sync_id(self, sync_id: UUID) -> None:
        """Search for entity nodes in Neo4j matching a given sync_id."""
        query = "MATCH (c:Entity {sync_id: $sync_id}) RETURN c"
        async with self.driver.session() as session:
            result = await session.run(query, sync_id=str(sync_id))
            records = await result.data()
            return records

    async def create_node(self, node_properties: dict, label: str) -> None:
        """Create a node with the specified label and properties.

        WARNING: Using string interpolation for the label; ensure it is trusted.
        """
        query = f"CREATE (n:{label} $props) RETURN n"
        async with self.driver.session() as session:
            await session.run(query, props=node_properties)

    async def create_relationship(
        self, from_node_id: str, to_node_id: str, rel_type: str, properties: dict = None
    ) -> None:
        """Create relationship of type rel_type between two nodes identified by their 'id' property.

        WARNING: Using string interpolation for rel_type; ensure it is trusted.
        """
        query = (
            f"MATCH (a {{id: $from_id}}), (b {{id: $to_id}}) "
            f"CREATE (a)-[r:{rel_type} $props]->(b) RETURN r"
        )
        async with self.driver.session() as session:
            await session.run(query, from_id=from_node_id, to_id=to_node_id, props=properties or {})

    async def bulk_create_nodes(self, nodes: list[dict]) -> None:
        """Bulk create nodes from a list of dictionaries.

        Each dict should have 'label' and 'properties'.
        """
        async with self.driver.session() as session:
            for node in nodes:
                label = node.get("label", "Node")
                props = node.get("properties", {})
                query = f"CREATE (n:{label} $props) RETURN n"
                await session.run(query, props=props)

    async def bulk_create_relationships(self, relationships: list[dict]) -> None:
        """Bulk create relationships from a list of dictionaries.

        Each dict should include 'from_node_id', 'to_node_id', 'rel_type',
            and optionally 'properties'.
        """
        async with self.driver.session() as session:
            for rel in relationships:
                query = (
                    f"MATCH (a {{id: $from_id}}), (b {{id: $to_id}}) "
                    f"CREATE (a)-[r:{rel['rel_type']} $props]->(b) RETURN r"
                )
                await session.run(
                    query,
                    from_id=rel.get("from_node_id"),
                    to_id=rel.get("to_node_id"),
                    props=rel.get("properties", {}),
                )
