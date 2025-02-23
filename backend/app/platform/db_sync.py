"""Module for syncing embedding models, sources, and destinations with the database."""

import importlib
import inspect
import os
from typing import Dict, Type

from sqlalchemy.ext.asyncio import AsyncSession

from app import crud, schemas
from app.core.logging import logger
from app.models.entity_definition import EntityType
from app.platform.destinations._base import BaseDestination
from app.platform.embedding_models._base import BaseEmbeddingModel
from app.platform.sources._base import BaseSource

sync_logger = logger.with_prefix("Platform sync: ").with_context(component="platform_sync")


def _get_decorated_classes(directory: str) -> Dict[str, list[Type]]:
    """Scan directory for decorated classes (sources, destinations, embedding models).

    Args:
        directory (str): The directory to scan.

    Returns:
        Dict[str, list[Type]]: Dictionary of decorated classes by type.
    """
    components = {"sources": [], "destinations": [], "embedding_models": []}

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
            for _, cls in inspect.getmembers(module, inspect.isclass):
                if getattr(cls, "_is_source", False):
                    components["sources"].append(cls)
                elif getattr(cls, "_is_destination", False):
                    components["destinations"].append(cls)
                elif getattr(cls, "_is_embedding_model", False):
                    components["embedding_models"].append(cls)

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


async def _sync_entity_definitions(db: AsyncSession) -> Dict[str, list[str]]:
    """Sync entity definitions with the database based on chunk classes.

    Args:
        db (AsyncSession): Database session

    Returns:
        Dict[str, list[str]]: Mapping of chunk names to their entity definition IDs as strings
    """
    sync_logger.info("Syncing entity definitions to database.")

    # Get all Python files in the entities directory that aren't base or init files
    chunk_files = [
        f
        for f in os.listdir("app/platform/entities")
        if f.endswith(".py") and not f.startswith("_")
    ]

    from app.platform.entities._base import BaseEntity

    entity_definitions = []
    module_to_entities = {}  # Track which entities belong to which module

    for chunk_file in chunk_files:
        module_name = chunk_file[:-3]  # Remove .py extension
        # Import the module to get its chunk classes
        full_module_name = f"app.platform.entities.{module_name}"
        module = importlib.import_module(full_module_name)

        # Initialize list for this module's entities
        module_to_entities[module_name] = []

        # Find all chunk classes (subclasses of BaseEntity) in the module
        for name, cls in inspect.getmembers(module, inspect.isclass):
            if issubclass(cls, BaseEntity) and cls != BaseEntity:
                # Create entity definition
                entity_def = schemas.EntityDefinitionCreate(
                    name=name,
                    description=cls.__doc__ or f"Data from {name}",
                    type=EntityType.JSON,
                    schema=cls.model_json_schema(),  # Get the actual schema from the Pydantic model
                )
                entity_definitions.append(entity_def)
                module_to_entities[module_name].append(name)  # Track all entities for this module

    # Sync entities
    await crud.entity_definition.sync(db, entity_definitions, unique_field="name")

    # Get all entities to build the mapping
    all_entities = await crud.entity_definition.get_all(db)
    # Map module names to lists of entity IDs as strings
    name_to_ids = {
        module_name: [str(e.id) for e in all_entities if e.name in entity_names]
        for module_name, entity_names in module_to_entities.items()
    }

    sync_logger.info(f"Synced {len(entity_definitions)} entity definitions to database.")
    return name_to_ids


async def _sync_sources(
    db: AsyncSession, sources: list[Type[BaseSource]], entity_id_map: Dict[str, list[str]]
) -> None:
    """Sync sources with the database.

    Args:
    -----
        db (AsyncSession): Database session
        sources (list[Type[BaseSource]]): List of source classes
        entity_id_map (Dict[str, list[str]]): Mapping of chunk names to their entity definition IDs
            as strings
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


async def sync_platform_components(platform_dir: str, db: AsyncSession) -> None:
    """Sync all platform components (embedding models, sources, destinations) with the database.

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

    sync_logger.info("Platform components sync completed.")
