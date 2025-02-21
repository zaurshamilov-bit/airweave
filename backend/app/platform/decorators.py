"""Decorators for the platform integrations."""

from functools import wraps
from typing import Any, AsyncGenerator, Callable, Optional, TypeVar

from app.platform.auth.schemas import AuthType
from app.platform.entities._base import ChunkEntity


def source(
    name: str, short_name: str, auth_type: AuthType, auth_config_class: Optional[str] = None
) -> Callable[[type], type]:
    """Class decorator to mark a class as representing an Airweave source.

    Args:
    ----
        name (str): The name of the source.
        short_name (str): The short name of the source.
        auth_type (AuthType): The authentication type of the source.
        auth_config_class (Optional[str]): The authentication config class of the source.

    Returns:
    -------
        Callable[[type], type]: The decorated class.

    """

    def decorator(cls: type) -> type:
        cls._is_source = True
        cls._name = name
        cls._short_name = short_name
        cls._auth_type = auth_type
        cls._auth_config_class = auth_config_class
        return cls

    return decorator


def destination(
    name: str,
    short_name: str,
    auth_type: Optional[AuthType] = None,
    auth_config_class: Optional[str] = None,
) -> Callable[[type], type]:
    """Class decorator to mark a class as representing an Airweave destination.

    Args:
    ----
        name (str): The name of the destination.
        short_name (str): The short name of the destination.
        auth_type (AuthType): The authentication type of the destination.
        auth_config_class (str): The authentication config class of the destination.

    Returns:
    -------
        Callable[[type], type]: The decorated class.

    """

    def decorator(cls: type) -> type:
        cls._is_destination = True
        cls._name = name
        cls._short_name = short_name
        cls._auth_type = auth_type
        cls._auth_config_class = auth_config_class
        return cls

    return decorator


def embedding_model(
    name: str,
    short_name: str,
    provider: str,
    auth_type: Optional[AuthType] = None,
    auth_config_class: Optional[str] = None,
    model_name: Optional[str] = None,
    model_version: Optional[str] = None,
) -> Callable[[type], type]:
    """Class decorator to mark a class as representing an Airweave embedding model.

    Args:
    ----
        name (str): The name of the embedding model.
        short_name (str): The short name of the embedding model.
        provider (str): The provider of the embedding model.
        auth_type (AuthType): The authentication type of the embedding model.
        auth_config_class (Optional[str]): The authentication config class of the embedding model.
        model_name (Optional[str]): The name of the embedding model.
        model_version (Optional[str]): The version of the embedding model.

    Returns:
    -------
        Callable[[type], type]: The decorated class.

    """

    def decorator(cls: type) -> type:
        cls._is_embedding_model = True
        cls._name = name
        cls._short_name = short_name
        cls._auth_type = auth_type
        cls._auth_config_class = auth_config_class
        cls._model_name = model_name if model_name else cls._name
        cls._model_version = model_version if model_version else "1.0"
        cls._provider = provider
        return cls

    return decorator


T = TypeVar("T", bound=ChunkEntity)
U = TypeVar("U", bound=ChunkEntity)


def transformer(
    name: str,
    short_name: str,
    auth_type: Optional[AuthType] = None,
    auth_config_class: Optional[str] = None,
) -> Callable[[Callable], Callable]:
    """Method decorator to mark a function as an Airweave transformer.

    Args:
        name (str): The name of the transformer.
        short_name (str): The short name of the transformer.
        auth_type (AuthType, optional): The authentication type.
        auth_config_class (str, optional): The auth config class.

    Returns:
        Callable: The decorated function.
    """

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(
            entity: Any, credentials: Optional[Any] = None
        ) -> AsyncGenerator[Any, None]:
            async for transformed in func(entity):
                yield transformed

        # Add transformer metadata
        wrapper._is_transformer = True
        wrapper._name = name
        wrapper._short_name = short_name
        wrapper._auth_type = auth_type
        wrapper._auth_config_class = auth_config_class
        wrapper.__doc__ = func.__doc__

        return wrapper

    return decorator
