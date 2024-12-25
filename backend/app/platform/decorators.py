"""Decorators for the platform integrations."""

from typing import Callable

from app.platform.auth.schemas import AuthType


def source(name: str, short_name: str, auth_type: AuthType) -> Callable[[type], type]:
    """Class decorator to mark a class as representing an Airweave source.

    Args:
    ----
        name (str): The name of the source.
        short_name (str): The short name of the source.
        auth_type (AuthType): The authentication type of the source.

    Returns:
    -------
        Callable[[type], type]: The decorated class.

    """

    def decorator(cls: type) -> type:
        cls._is_source = True
        cls._name = name
        cls._short_name = short_name
        cls._auth_type = auth_type
        return cls

    return decorator
