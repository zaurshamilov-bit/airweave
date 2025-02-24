"""Module for syncing embedding models, sources, and destinations with the database."""

import importlib
import inspect
import os
from typing import Callable, Dict, Type, Union
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession
from typing_extensions import get_type_hints

from app import crud, schemas
from app.core.logging import logger
from app.models.entity_definition import EntityType
from app.platform.destinations._base import BaseDestination
from app.platform.embedding_models._base import BaseEmbeddingModel
from app.platform.sources._base import BaseSource

sync_logger = logger.with_prefix("Platform sync: ").with_context(component="platform_sync")


def _get_decorated_classes(directory: str) -> Dict[str, list[Type | Callable]]:
    """Scan directory for decorated classes and functions.

    Args:
        directory (str): The directory to scan.

    Returns:
        Dict[str, list[Type | Callable]]: Dictionary of decorated classes and functions by type.
    """
    components = {
        "sources": [],
        "destinations": [],
        "embedding_models": [],
        "transformers": [],
    }

    base_package = directory.replace("/", ".")

    for root, _, files in os.walk(directory):
        # Skip files in the root directory
        if root == directory:
            continue

        for filename in files:
            if not filename.endswith(".py") or filename.startswith("_"):
                continue

            relative_path = os.path.relpath(root, directory)
            module_path = os.path.join(relative_path, filename[:-3]).replace("/", ".")
            full_module_name = f"{base_package}.{module_path}"

            module = importlib.import_module(full_module_name)

            # Scan for classes
            for _, cls in inspect.getmembers(module, inspect.isclass):
                if getattr(cls, "_is_source", False):
                    components["sources"].append(cls)
                elif getattr(cls, "_is_destination", False):
                    components["destinations"].append(cls)
                elif getattr(cls, "_is_embedding_model", False):
                    components["embedding_models"].append(cls)

            # Scan for transformer functions
            for _, func in inspect.getmembers(module, inspect.isfunction):
                if getattr(func, "_is_transformer", False):
                    components["transformers"].append(func)

    return components


async def _sync_embedding_models(db: AsyncSession, models: list[Type[BaseEmbeddingModel]]) -> None:
    """Sync embedding models with the database.

    Args:
        db (AsyncSession): Database session
        models (list[Type[BaseEmbeddingModel]]): List of embedding model classes
    """
    sync_logger.info("Syncing embedding models to database.")

    model_definitions = []
    for model_class in models:
        model_def = schemas.EmbeddingModelCreate(
            name=model_class._name,
            short_name=model_class._short_name,
            description=model_class.__doc__,
            provider=model_class._provider,
            model_name=model_class._model_name,
            model_version=model_class._model_version,
            auth_type=model_class._auth_type,
            auth_config_class=model_class._auth_config_class,
        )
        model_definitions.append(model_def)

    await crud.embedding_model.sync(db, model_definitions)
    sync_logger.info(f"Synced {len(model_definitions)} embedding models to database.")


async def _sync_entity_definitions(db: AsyncSession) -> Dict[str, dict]:
    """Sync entity definitions with the database based on chunk classes.

    Args:
        db (AsyncSession): Database session

    Returns:
        Dict[str, dict]: Mapping of entity names to their details:
            - ids: list[str] - UUIDs of entity definitions
            - class_name: str - Full class name of the entity
    """
    sync_logger.info("Syncing entity definitions to database.")

    # Get all Python files in the entities directory that aren't base or init files
    entity_files = [
        f
        for f in os.listdir("app/platform/entities")
        if f.endswith(".py") and not f.startswith("__")
    ]

    from app.platform.entities._base import BaseEntity

    entity_definitions = []
    entity_registry = {}  # Track all entities system-wide

    for entity_file in entity_files:
        module_name = entity_file[:-3]  # Remove .py extension
        # Import the module to get its chunk classes
        full_module_name = f"app.platform.entities.{module_name}"
        module = importlib.import_module(full_module_name)

        # Find all chunk classes (subclasses of BaseEntity) in the module
        for name, cls in inspect.getmembers(module, inspect.isclass):
            # Check if it's a subclass of BaseEntity (but not BaseEntity itself)
            # AND the class is actually defined in this module (not imported)
            if (
                issubclass(cls, BaseEntity)
                and cls != BaseEntity
                and cls.__module__ == full_module_name
            ):

                if name in entity_registry:
                    raise ValueError(
                        f"Duplicate entity name '{name}' found in {full_module_name}. "
                        f"Already registered from {entity_registry[name]['module']}"
                    )

                # Register the entity
                entity_registry[name] = {
                    "class_name": f"{cls.__module__}.{cls.__name__}",
                    "module": full_module_name,
                }

                # Create entity definition
                entity_def = schemas.EntityDefinitionCreate(
                    name=name,
                    description=cls.__doc__ or f"Data from {name}",
                    type=EntityType.JSON,
                    schema=cls.model_json_schema(),  # Get the actual schema from the Pydantic model
                )
                entity_definitions.append(entity_def)

    # Sync entities
    await crud.entity_definition.sync(db, entity_definitions, unique_field="name")

    # Get all entities to build the mapping
    all_entities = await crud.entity_definition.get_all(db)

    # Create final mapping with both IDs and class names
    entity_map = {
        name: {
            "ids": [str(e.id) for e in all_entities if e.name == name],
            "class_name": details["class_name"],
        }
        for name, details in entity_registry.items()
    }

    sync_logger.info(f"Synced {len(entity_definitions)} entity definitions to database.")
    return entity_map


async def _sync_sources(
    db: AsyncSession, sources: list[Type[BaseSource]], entity_id_map: Dict[str, list[str]]
) -> None:
    """Sync sources with the database.

    Args:
        db (AsyncSession): Database session
        sources (list[Type[BaseSource]]): List of source classes
        entity_id_map (Dict[str, list[str]]): Mapping of chunk names to their entity definition IDs as strings
    """
    sync_logger.info("Syncing sources to database.")

    source_definitions = []
    for source_class in sources:
        # Get the chunk type from the source class name
        # For example, if source is GoogleDriveSource, look for google_drive chunk
        source_name = source_class.__name__.replace("Source", "").lower()
        chunk_name = "_".join(word for word in source_name.split() if word)

        # Get all entity IDs for this source's chunk type (already as strings)
        output_entity_ids = entity_id_map.get(chunk_name, [])

        source_def = schemas.SourceCreate(
            name=source_class._name,
            description=source_class.__doc__,
            auth_type=source_class._auth_type,
            auth_config_class=source_class._auth_config_class,
            short_name=source_class._short_name,
            class_name=source_class.__name__,
            output_entity_definition_ids=output_entity_ids,
        )
        source_definitions.append(source_def)

    await crud.source.sync(db, source_definitions)
    sync_logger.info(f"Synced {len(source_definitions)} sources to database.")


async def _sync_destinations(db: AsyncSession, destinations: list[Type[BaseDestination]]) -> None:
    """Sync destinations with the database.

    Args:
        db (AsyncSession): Database session
        destinations (list[Type[BaseDestination]]): List of destination classes
    """
    sync_logger.info("Syncing destinations to database.")

    destination_definitions = []
    for dest_class in destinations:
        dest_def = schemas.DestinationCreate(
            name=dest_class._name,
            description=dest_class.__doc__,
            short_name=dest_class._short_name,
            class_name=dest_class.__name__,
            auth_type=dest_class._auth_type,
            auth_config_class=dest_class._auth_config_class,
        )
        destination_definitions.append(dest_def)

    await crud.destination.sync(db, destination_definitions)
    sync_logger.info(f"Synced {len(destination_definitions)} destinations to database.")


def _get_type_names(type_hint) -> list[str]:
    """Extract type names from a type hint, handling Union types correctly.

    Args:
        type_hint: The type hint to extract names from

    Returns:
        list[str]: List of type names
    """
    # Handle Union types (both typing.Union and types.UnionType (|))
    if hasattr(type_hint, "__origin__"):
        if type_hint.__origin__ is Union or str(type_hint.__origin__) == "typing.Union":
            return [t.__name__ for t in type_hint.__args__]
        if str(type_hint.__origin__) == "|":  # Python 3.10+ Union type
            return [t.__name__ for t in type_hint.__args__]
        if type_hint.__origin__ is list:
            # For list types, process the inner type
            return _get_type_names(type_hint.__args__[0])
        # Handle other generic types
        return [type_hint.__args__[0].__name__]

    # Handle UnionType at the base level (Python 3.10+ |)
    if str(type(type_hint)) == "<class 'types.UnionType'>":
        return [t.__name__ for t in type_hint.__args__]

    # Handle simple types
    return [type_hint.__name__]


async def _sync_transformers(
    db: AsyncSession, transformers: list[Callable], entity_map: Dict[str, dict]
) -> None:
    """Sync transformers with the database.

    Args:
        db (AsyncSession): Database session
        transformers (list[Callable]): List of transformer functions
        entity_map (Dict[str, dict]): Mapping of entity names to their details
    """
    sync_logger.info("Syncing transformers to database.")

    transformer_definitions = []
    for transformer_func in transformers:
        # Get type hints for input/output
        type_hints = get_type_hints(transformer_func)

        # Get input type from first parameter
        first_param = next(iter(inspect.signature(transformer_func).parameters.values()))
        input_type = type_hints[first_param.name]
        input_type_name = input_type.__name__

        if input_type_name not in entity_map:
            raise ValueError(
                f"Transformer {transformer_func._name} has unknown input type {input_type_name}"
            )

        # Get output types from return annotation
        return_type = type_hints["return"]
        output_types = _get_type_names(return_type)

        # Validate output types
        for type_name in output_types:
            if type_name not in entity_map:
                raise ValueError(
                    f"Transformer {transformer_func._name} has unknown output type {type_name}"
                )

        transformer_def = schemas.TransformerCreate(
            name=transformer_func._name,
            description=transformer_func.__doc__,
            method_name=transformer_func.__name__,
            auth_type=getattr(transformer_func, "_auth_type", None),
            auth_config_class=getattr(transformer_func, "_auth_config_class", None),
            config_schema=getattr(transformer_func, "_config_schema", {}),
            input_entity_definition_ids=[UUID(id) for id in entity_map[input_type_name]["ids"]],
            output_entity_definition_ids=[
                UUID(id) for type_name in output_types for id in entity_map[type_name]["ids"]
            ],
        )
        transformer_definitions.append(transformer_def)

    await crud.transformer.sync(db, transformer_definitions, unique_field="method_name")
    sync_logger.info(f"Synced {len(transformer_definitions)} transformers to database.")


async def sync_platform_components(platform_dir: str, db: AsyncSession) -> None:
    """Sync all platform components with the database.

    Args:
        platform_dir (str): Directory containing platform components
        db (AsyncSession): Database session
    """
    sync_logger.info("Starting platform components sync...")

    components = _get_decorated_classes(platform_dir)

    # First sync entities to get their IDs
    entity_id_map = await _sync_entity_definitions(db)

    await _sync_embedding_models(db, components["embedding_models"])
    await _sync_sources(db, components["sources"], entity_id_map)
    await _sync_destinations(db, components["destinations"])
    await _sync_transformers(db, components["transformers"], entity_id_map)

    sync_logger.info("Platform components sync completed.")
