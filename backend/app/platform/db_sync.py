"""Module for syncing embedding models, sources, and destinations with the database."""

import importlib
import inspect
import os
from typing import Dict, Type

from sqlalchemy.ext.asyncio import AsyncSession

from app import crud, schemas
from app.core.logging import logger
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


async def _sync_sources(db: AsyncSession, sources: list[Type[BaseSource]]) -> None:
    """Sync sources with the database.

    Args:
        db (AsyncSession): Database session
        sources (list[Type[BaseSource]]): List of source classes
    """
    sync_logger.info("Syncing sources to database.")

    source_definitions = []
    for source_class in sources:
        source_def = schemas.SourceCreate(
            name=source_class._name,
            description=source_class.__doc__,
            auth_type=source_class._auth_type,
            auth_config_class=source_class._auth_config_class,
            short_name=source_class._short_name,
            class_name=source_class.__name__,
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

    await _sync_embedding_models(db, components["embedding_models"])
    await _sync_sources(db, components["sources"])
    await _sync_destinations(db, components["destinations"])

    sync_logger.info("Platform components sync completed.")
