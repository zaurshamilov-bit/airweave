"""Resource locator for platform resources."""

import importlib
from typing import Callable, Type

from app import schemas
from app.platform.configs._base import BaseConfig
from app.platform.destinations._base import BaseDestination
from app.platform.embedding_models._base import BaseEmbeddingModel
from app.platform.sources._base import BaseSource

PLATFORM_PATH = "app.platform"


class ResourceLocator:
    """Resource locator for platform resources.

    Gets the following:
    - embedding models
    - destinations
    - sources
    - configs
    - transformers
    """

    @staticmethod
    def get_embedding_model(model: schemas.EmbeddingModel) -> Type[BaseEmbeddingModel]:
        """Get the embedding model class.

        Args:
            model (schemas.EmbeddingModel): Embedding model schema

        Returns:
            Type[BaseEmbeddingModel]: Instantiated embedding model
        """
        module = importlib.import_module(f"{PLATFORM_PATH}.embedding_models.{model.short_name}")
        return getattr(module, model.class_name)

    @staticmethod
    def get_source(source: schemas.Source) -> Type[BaseSource]:
        """Get the source class.

        Args:
            source (schemas.Source): Source schema

        Returns:
            Type[BaseSource]: Source class
        """
        module = importlib.import_module(f"{PLATFORM_PATH}.sources.{source.short_name}")
        return getattr(module, source.class_name)

    @staticmethod
    def get_destination(destination: schemas.Destination) -> Type[BaseDestination]:
        """Get the destination class.

        Args:
            destination (schemas.Destination): Destination schema

        Returns:
            Type[BaseDestination]: Destination class
        """
        module = importlib.import_module(f"{PLATFORM_PATH}.destinations.{destination.short_name}")
        return getattr(module, destination.class_name)

    @staticmethod
    def get_auth_config(auth_config_class: str) -> Type[BaseConfig]:
        """Get the auth config class.

        Args:
            auth_config_class (str): Auth config class name

        Returns:
            Type[BaseConfig]: Auth config class
        """
        module = importlib.import_module(f"{PLATFORM_PATH}.configs.auth")
        auth_config_class = getattr(module, auth_config_class)
        return auth_config_class

    @staticmethod
    def get_transformer(transformer: schemas.Transformer) -> Callable:
        """Get the transformer function.

        Args:
            transformer (schemas.Transformer): Transformer schema

        Returns:
            Callable: Transformer function
        """
        module = importlib.import_module(f"{PLATFORM_PATH}.transformers.{transformer.short_name}")
        return getattr(module, transformer.function_name)


resource_locator = ResourceLocator()
