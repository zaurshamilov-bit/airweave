"""PostgreSQL source implementation.

This source connects to a PostgreSQL database and generates entities for each table
based on its schema structure. It dynamically creates entity classes at runtime
using the PolymorphicEntity system.
"""

import json
from datetime import datetime
from typing import Any, AsyncGenerator, Dict, List, Optional, Type, Union

import asyncpg

from airweave.platform.auth.schemas import AuthType
from airweave.platform.decorators import source
from airweave.platform.entities._base import ChunkEntity, PolymorphicEntity
from airweave.platform.sources._base import BaseSource

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
    "json": Any,  # JSON can be dict, list, or primitive
    "jsonb": Any,  # JSONB can be dict, list, or primitive
}


@source(
    name="PostgreSQL",
    short_name="postgresql",
    auth_type=AuthType.config_class,
    auth_config_class="PostgreSQLAuthConfig",
    config_class="PostgreSQLConfig",
    labels=["Database"],
)
class PostgreSQLSource(BaseSource):
    """PostgreSQL source connector integrates with PostgreSQL databases to extract structured data.

    Synchronizes data from database tables.

    It uses dynamic schema introspection to create appropriate entity classes
    and provides comprehensive access to relational data with proper type mapping and relationships.
    """

    def __init__(self):
        """Initialize the PostgreSQL source."""
        super().__init__()  # Initialize BaseSource to get cursor support
        self.conn: Optional[asyncpg.Connection] = None
        self.entity_classes: Dict[str, Type[PolymorphicEntity]] = {}

    @classmethod
    async def create(
        cls, credentials: Dict[str, Any], config: Optional[Dict[str, Any]] = None
    ) -> "PostgreSQLSource":
        """Create a new PostgreSQL source instance.

        Args:
            credentials: Dictionary containing connection details:
                - host: Database host
                - port: Database port
                - database: Database name
                - user: Username
                - password: Password
                - schema: Schema to sync (defaults to 'public')
                - tables: Table to sync (defaults to '*')
            config: Optional configuration parameters for the PostgreSQL source.
        """
        instance = cls()
        instance.config = credentials.model_dump()
        return instance

    def get_default_cursor_field(self) -> Optional[str]:
        """Get the default cursor field for PostgreSQL source.

        PostgreSQL doesn't have a universal default cursor field since it depends
        on the table schema. Common patterns are 'updated_at' or 'modified_at'.

        Returns:
            None - user must specify cursor field for PostgreSQL
        """
        # PostgreSQL requires user to specify cursor field
        # since table schemas vary widely

        # NOTE: the fact that the source does not have a default cursor field
        # indicates that it should be set by the user

        return None

    def validate_cursor_field(self, cursor_field: str) -> None:
        """Validate if the given cursor field is valid for PostgreSQL.

        For PostgreSQL, we accept a JSON structure that maps tables to cursor fields.
        Format: {"schema.table": "cursor_column", ...}
        Or a single field name to use for all tables.

        Args:
            cursor_field: The cursor field specification to validate
        """
        # PostgreSQL accepts either:
        # 1. A single column name (applies to all tables)
        # 2. A JSON string mapping tables to columns
        if cursor_field.startswith("{") and cursor_field.endswith("}"):
            # Validate JSON format
            try:
                import json

                cursor_map = json.loads(cursor_field)
                if not isinstance(cursor_map, dict):
                    raise ValueError(
                        "Cursor field mapping must be a JSON object like: "
                        '{"public.users": "updated_at", "public.orders": "modified_at"}'
                    )
            except json.JSONDecodeError as e:
                raise ValueError(f"Invalid JSON in cursor field mapping: {e}") from e
        # Otherwise accept any string as a column name

    def _get_cursor_data(self) -> Dict[str, Any]:
        """Get cursor data from cursor.

        Returns:
            Cursor data dictionary, empty dict if no cursor exists
        """
        if self.cursor:
            return self.cursor.cursor_data or {}
        return {}

    def _get_cursor_field_for_table(self, schema: str, table: str) -> Optional[str]:
        """Get the cursor field to use for a specific table.

        Args:
            schema: Schema name
            table: Table name

        Returns:
            The cursor field for this table, or None if not specified
        """
        cursor_field = self.get_effective_cursor_field()
        if not cursor_field:
            return None

        # Check if cursor_field is a JSON mapping
        if cursor_field.startswith("{") and cursor_field.endswith("}"):
            try:
                import json

                cursor_map = json.loads(cursor_field)
                # Try exact match first
                table_key = f"{schema}.{table}"
                if table_key in cursor_map:
                    return cursor_map[table_key]
                # Fall back to table name without schema
                if table in cursor_map:
                    return cursor_map[table]
            except json.JSONDecodeError:
                # If JSON parsing fails, treat as single field
                pass

        # Single field applies to all tables
        return cursor_field

    def _update_cursor_data(self, schema: str, table: str, cursor_value: Any):
        """Update cursor data with the latest cursor value for a table.

        Args:
            schema: Schema name
            table: Table name
            cursor_value: Latest cursor value from the table
        """
        if not self.cursor:
            return

        # Store cursor value per table
        cursor_key = f"{schema}.{table}"
        if not self.cursor.cursor_data:
            self.cursor.cursor_data = {}

        # Convert datetime to ISO format string for JSON serialization
        if isinstance(cursor_value, datetime):
            cursor_value = cursor_value.isoformat()

        # Store the maximum value seen for this table
        existing_value = self.cursor.cursor_data.get(cursor_key)

        # Handle comparison when existing value might be a string (ISO format)
        if existing_value is not None:
            # Convert existing string back to datetime for comparison if needed
            if isinstance(existing_value, str) and isinstance(cursor_value, str):
                # Both are ISO strings, compare as strings (works for ISO format)
                should_update = cursor_value > existing_value
            else:
                should_update = cursor_value > existing_value
        else:
            should_update = True

        if should_update:
            self.cursor.cursor_data[cursor_key] = cursor_value
            self.logger.debug(f"Updated cursor for table '{cursor_key}': {cursor_value}")

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

    async def _create_entity_class(self, schema: str, table: str) -> Type[PolymorphicEntity]:
        """Create a entity class for a specific table.

        Args:
            schema: Schema name
            table: Table name

        Returns:
            Dynamically created entity class for the table
        """
        table_info = await self._get_table_info(schema, table)

        return PolymorphicEntity.create_table_entity_class(
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

    async def _get_table_list(self, schema: str) -> List[str]:
        """Get the list of tables to process based on configuration."""
        tables_config = self.config.get("tables", "*")

        # Handle both wildcard and CSV list of tables
        if tables_config == "*":
            return await self._get_tables(schema)

        # Split by comma and strip whitespace
        tables = [t.strip() for t in tables_config.split(",")]
        # Validate that all specified tables exist
        available_tables = await self._get_tables(schema)
        invalid_tables = set(tables) - set(available_tables)
        if invalid_tables:
            raise ValueError(f"Tables not found in schema '{schema}': {', '.join(invalid_tables)}")
        return tables

    async def _convert_field_values(
        self, data: Dict[str, Any], model_fields: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Convert field values to the expected types based on the entity model.

        Args:
            data: The raw data dictionary from the database record
            model_fields: The model fields from the entity class

        Returns:
            Dict with processed field values matching the expected types
        """
        processed_data = {}
        for field_name, field_value in data.items():
            # Handle the case where the field name is 'id' in the database
            model_field_name = field_name + "_" if field_name == "id" else field_name

            # Skip if the field doesn't exist in the model
            if model_field_name not in model_fields:
                continue

            # If value is None, keep it as None
            if field_value is None:
                processed_data[model_field_name] = None
                continue

            # Get expected type from model field
            field_info = model_fields[model_field_name]
            field_type = field_info.annotation

            # Handle Union types (including Optional which is Union[T, None])
            if hasattr(field_type, "__origin__") and field_type.__origin__ is Union:
                # For Union types, get the non-None type (if it's Optional pattern)
                union_args = field_type.__args__
                # Filter out NoneType to get the actual type
                non_none_types = [arg for arg in union_args if arg is not type(None)]
                if non_none_types:
                    field_type = non_none_types[0]  # Take the first non-None type

            # Simple conversion: if target is string, convert to string
            if field_type is str and field_value is not None:
                processed_data[model_field_name] = str(field_value)
            else:
                # Let Pydantic handle everything else
                processed_data[model_field_name] = field_value

        return processed_data

    async def _process_table_batch(
        self,
        schema: str,
        table: str,
        entity_class: Type[PolymorphicEntity],
        batch: List,
        cursor_field: Optional[str] = None,
    ) -> AsyncGenerator[ChunkEntity, None]:
        """Process a batch of records from a table.

        Args:
            schema: Schema name
            table: Table name
            entity_class: Entity class for the table
            batch: Batch of records to process
            cursor_field: Field to track for cursor updates

        Yields:
            Entity instances
        """
        max_cursor_value = None

        for record in batch:
            data = dict(record)

            # Track max cursor value if cursor field is specified
            if cursor_field and cursor_field in data:
                cursor_value = data[cursor_field]
                if cursor_value is not None:
                    if max_cursor_value is None or cursor_value > max_cursor_value:
                        max_cursor_value = cursor_value

            # Simply try to convert all strings to JSON
            for key, value in data.items():
                if isinstance(value, str):
                    try:
                        parsed_value = json.loads(value)
                        data[key] = parsed_value
                    except (json.JSONDecodeError, ValueError):
                        # Keep as string if not valid JSON
                        pass

            model_fields = entity_class.model_fields
            primary_keys = model_fields["primary_key_columns"].default_factory()
            pk_values = [str(data[pk]) for pk in primary_keys]
            entity_id = f"{schema}.{table}:" + ":".join(pk_values)

            # Convert field values to match expected types in the entity model
            processed_data = await self._convert_field_values(data, model_fields)

            yield entity_class(entity_id=entity_id, **processed_data)

        # Update cursor with the max value from this batch
        if cursor_field and max_cursor_value is not None:
            self._update_cursor_data(schema, table, max_cursor_value)

    def _prepare_cursor_value(self, last_cursor_value: Any) -> Any:
        """Convert ISO string back to datetime for PostgreSQL query if needed."""
        if last_cursor_value and isinstance(last_cursor_value, str):
            try:
                # Try to parse as ISO datetime string
                from datetime import datetime

                return datetime.fromisoformat(last_cursor_value)
            except (ValueError, TypeError):
                # If not a datetime string, use as-is (could be an integer ID, etc.)
                pass
        return last_cursor_value

    def _log_sync_type(self, table_key: str, cursor_field: Optional[str], last_cursor_value: Any):
        """Log the type of sync being performed for a table."""
        if cursor_field and last_cursor_value:
            self.logger.info(
                f"Table {table_key}: INCREMENTAL sync using field '{cursor_field}' "
                f"(changes after {last_cursor_value})"
            )
        elif cursor_field:
            self.logger.info(
                f"Table {table_key}: FULL sync (will track '{cursor_field}' for next sync)"
            )
        else:
            self.logger.debug(f"Table {table_key}: FULL sync (no cursor field configured)")

    def _build_table_query(
        self,
        schema: str,
        table: str,
        cursor_field: Optional[str],
        last_cursor_value: Any,
        batch_size: int,
        offset: int,
    ) -> tuple[str, Optional[Any]]:
        """Build the query for fetching table data."""
        if cursor_field and last_cursor_value:
            # Incremental query - only get records updated after last sync
            query = (
                f'SELECT * FROM "{schema}"."{table}" '
                f'WHERE "{cursor_field}" > $1 '
                f'ORDER BY "{cursor_field}" '
                f"LIMIT {batch_size} OFFSET {offset}"
            )
            return query, last_cursor_value
        elif cursor_field:
            # Full sync with cursor field - order by it for consistent results
            query = (
                f'SELECT * FROM "{schema}"."{table}" '
                f'ORDER BY "{cursor_field}" '
                f"LIMIT {batch_size} OFFSET {offset}"
            )
            return query, None
        else:
            # No cursor field, regular full sync
            query = f'SELECT * FROM "{schema}"."{table}" LIMIT {batch_size} OFFSET {offset}'
            return query, None

    async def _process_table(
        self,
        schema: str,
        table: str,
        cursor_data: Dict[str, Any],
    ) -> AsyncGenerator[ChunkEntity, None]:
        """Process a single table with incremental support.

        Args:
            schema: Schema name
            table: Table name
            cursor_data: Cursor data from previous syncs

        Yields:
            Entities from the table
        """
        # Create entity class if not already created
        if f"{schema}.{table}" not in self.entity_classes:
            self.entity_classes[f"{schema}.{table}"] = await self._create_entity_class(
                schema, table
            )

        entity_class = self.entity_classes[f"{schema}.{table}"]
        cursor_field = self._get_cursor_field_for_table(schema, table)
        table_key = f"{schema}.{table}"

        # Get and prepare last cursor value
        last_cursor_value = cursor_data.get(table_key) if cursor_data else None
        last_cursor_value = self._prepare_cursor_value(last_cursor_value)

        # Log sync type
        self._log_sync_type(table_key, cursor_field, last_cursor_value)

        # Process table in batches
        BATCH_SIZE = 50
        offset = 0

        while True:
            # Build and execute query
            query, query_param = self._build_table_query(
                schema, table, cursor_field, last_cursor_value, BATCH_SIZE, offset
            )

            if query_param is not None:
                records = await self.conn.fetch(query, query_param)
            else:
                records = await self.conn.fetch(query)

            # Break if no more records
            if not records:
                if offset == 0 and cursor_field and last_cursor_value:
                    self.logger.info(f"Table {table_key}: No new records since last sync")
                break

            # Process the batch with cursor tracking
            async for entity in self._process_table_batch(
                schema, table, entity_class, records, cursor_field
            ):
                yield entity

            # Increment offset for next batch
            offset += BATCH_SIZE

    async def generate_entities(self) -> AsyncGenerator[ChunkEntity, None]:
        """Generate entities for all tables in specified schemas with incremental support."""
        try:
            await self._connect()
            schema = self.config.get("schema", "public")
            tables = await self._get_table_list(schema)

            # Get cursor data for incremental sync
            cursor_data = self._get_cursor_data()

            # Log sync type
            if cursor_data:
                self.logger.info(
                    f"Found cursor data with {len(cursor_data)} table(s). "
                    f"Will perform INCREMENTAL sync for changed records."
                )
            else:
                self.logger.info("No cursor data found. Will perform FULL sync (first sync).")

            # Start a transaction
            async with self.conn.transaction():
                for table in tables:
                    async for entity in self._process_table(schema, table, cursor_data):
                        yield entity

        finally:
            if self.conn:
                await self.conn.close()
                self.conn = None
