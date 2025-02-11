"""PostgreSQL source implementation.

This source connects to a PostgreSQL database and generates chunks for each table
based on its schema structure. It dynamically creates chunk classes at runtime
using the PolymorphicChunk system.
"""

from datetime import datetime
from typing import Any, AsyncGenerator, Dict, List, Optional, Type

import asyncpg

from app.platform.auth.schemas import AuthType
from app.platform.chunks._base import BaseChunk, PolymorphicChunk
from app.platform.decorators import source
from app.platform.sources._base import BaseSource

# Mapping of PostgreSQL types to Python types
PG_TYPE_MAP = {
    "integer": int,
    "bigint": int,
    "smallint": int,
    "decimal": float,
    "numeric": float,
    "real": float,
    "double precision": float,
    "character varying": str,
    "character": str,
    "text": str,
    "boolean": bool,
    "timestamp": datetime,
    "timestamp with time zone": datetime,
    "date": datetime,
    "time": datetime,
    "json": Dict[str, Any],
    "jsonb": Dict[str, Any],
}


@source("PostgreSQL", "postgresql", AuthType.config_class, "PostgreSQLAuthConfig")
class PostgreSQLSource(BaseSource):
    """PostgreSQL source implementation.

    This source connects to a PostgreSQL database and generates chunks for each table
    in the specified schemas. It uses database introspection to:
    1. Discover tables and their structures
    2. Create appropriate chunk classes dynamically
    3. Generate chunks for each table's data
    """

    def __init__(self):
        """Initialize the PostgreSQL source."""
        self.conn: Optional[asyncpg.Connection] = None
        self.chunk_classes: Dict[str, Type[PolymorphicChunk]] = {}

    @classmethod
    async def create(cls, config: Dict[str, Any]) -> "PostgreSQLSource":
        """Create a new PostgreSQL source instance.

        Args:
            config: Dictionary containing connection details:
                - host: Database host
                - port: Database port
                - database: Database name
                - user: Username
                - password: Password
                - schema: Schema to sync (defaults to 'public')
                - tables: Table to sync (defaults to '*')
        """
        instance = cls()
        instance.config = config.model_dump()
        return instance

    async def _connect(self) -> None:
        """Establish database connection with timeout and error handling."""
        if not self.conn:
            try:
                # Convert localhost to 127.0.0.1 to avoid DNS resolution issues
                host = (
                    "127.0.0.1"
                    if self.config["host"].lower() in ("localhost", "127.0.0.1")
                    else self.config["host"]
                )

                self.conn = await asyncpg.connect(
                    host=host,
                    port=self.config["port"],
                    user=self.config["user"],
                    password=self.config["password"],
                    database=self.config["database"],
                    timeout=10.0,  # Add connection timeout
                    command_timeout=10.0,  # Add command timeout
                )
            except asyncpg.InvalidPasswordError as e:
                raise ValueError("Invalid database credentials") from e
            except asyncpg.InvalidCatalogNameError as e:
                raise ValueError(f"Database '{self.config['database']}' does not exist") from e
            except (
                OSError,
                asyncpg.CannotConnectNowError,
                asyncpg.ConnectionDoesNotExistError,
            ) as e:
                raise ValueError(
                    f"Could not connect to database at {self.config['host']}:{self.config['port']}."
                    " Please check if the database is running and the port is correct. "
                    f"Error: {str(e)}"
                ) from e
            except Exception as e:
                raise ValueError(f"Database connection failed: {str(e)}") from e

    async def _get_table_info(self, schema: str, table: str) -> Dict[str, Any]:
        """Get table structure information.

        Args:
            schema: Schema name
            table: Table name

        Returns:
            Dictionary containing column information and primary keys
        """
        # Get column information
        columns_query = """
            SELECT
                column_name,
                data_type,
                is_nullable,
                column_default
            FROM information_schema.columns
            WHERE table_schema = $1 AND table_name = $2
            ORDER BY ordinal_position
        """
        columns = await self.conn.fetch(columns_query, schema, table)

        # Get primary key information
        pk_query = """
            SELECT a.attname
            FROM pg_index i
            JOIN pg_attribute a ON a.attrelid = i.indrelid AND a.attnum = ANY(i.indkey)
            WHERE i.indrelid = ($1 || '.' || $2)::regclass AND i.indisprimary
        """
        primary_keys = [pk["attname"] for pk in await self.conn.fetch(pk_query, schema, table)]

        # Build column metadata
        column_info = {}
        for col in columns:
            pg_type = col["data_type"].lower()
            python_type = PG_TYPE_MAP.get(pg_type, Any)

            column_info[col["column_name"]] = {
                "python_type": python_type,
                "nullable": col["is_nullable"] == "YES",
                "default": col["column_default"],
                "pg_type": pg_type,
            }

        return {
            "columns": column_info,
            "primary_keys": primary_keys,
        }

    async def _create_chunk_class(self, schema: str, table: str) -> Type[PolymorphicChunk]:
        """Create a chunk class for a specific table.

        Args:
            schema: Schema name
            table: Table name

        Returns:
            Dynamically created chunk class for the table
        """
        table_info = await self._get_table_info(schema, table)

        return PolymorphicChunk.create_table_chunk_class(
            table_name=table,
            schema_name=schema,
            columns=table_info["columns"],
            primary_keys=table_info["primary_keys"],
        )

    async def _get_tables(self, schema: str) -> List[str]:
        """Get list of tables in a schema.

        Args:
            schema: Schema name

        Returns:
            List of table names
        """
        query = """
            SELECT table_name
            FROM information_schema.tables
            WHERE table_schema = $1
            AND table_type = 'BASE TABLE'
        """
        tables = await self.conn.fetch(query, schema)
        return [table["table_name"] for table in tables]

    async def generate_chunks(self) -> AsyncGenerator[BaseChunk, None]:
        """Generate chunks for all tables in specified schemas."""
        try:
            await self._connect()

            schema = self.config.get("schema", "public")
            tables_config = self.config.get("tables", "*")

            # Handle both wildcard and CSV list of tables
            if tables_config == "*":
                tables = await self._get_tables(schema)
            else:
                # Split by comma and strip whitespace
                tables = [t.strip() for t in tables_config.split(",")]
                # Validate that all specified tables exist
                available_tables = await self._get_tables(schema)
                invalid_tables = set(tables) - set(available_tables)
                if invalid_tables:
                    raise ValueError(
                        f"Tables not found in schema '{schema}': {', '.join(invalid_tables)}"
                    )

            # Start a transaction
            async with self.conn.transaction():
                for table in tables:
                    # Create chunk class if not already created
                    if f"{schema}.{table}" not in self.chunk_classes:
                        self.chunk_classes[f"{schema}.{table}"] = await self._create_chunk_class(
                            schema, table
                        )

                    chunk_class = self.chunk_classes[f"{schema}.{table}"]

                    # Fetch and yield data
                    query = f'SELECT * FROM "{schema}"."{table}"'
                    async for record in self.conn.cursor(query):
                        # Convert record to dict
                        data = dict(record)

                        # Create entity_id from primary key values
                        # Access class_vars directly from the model
                        model_fields = chunk_class.model_fields
                        primary_keys = model_fields["primary_key_columns"].default_factory()
                        pk_values = [str(data[pk]) for pk in primary_keys]
                        entity_id = f"{schema}.{table}:" + ":".join(pk_values)

                        # Create and yield chunk
                        chunk = chunk_class(entity_id=entity_id, **data)
                        yield chunk

        finally:
            if self.conn:
                await self.conn.close()
                self.conn = None
