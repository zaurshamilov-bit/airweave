"""Decorators for the platform integrations."""

from typing import Callable, Optional

from app.platform.auth.schemas import AuthType


def source(
    name: str,
    short_name: str,
    auth_type: Optional[AuthType] = None,
    auth_config_class: Optional[str] = None,
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
