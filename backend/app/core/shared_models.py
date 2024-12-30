from enum import Enum


class ConnectionStatus(str, Enum):
    """Connection status enum."""

    ACTIVE = "active"
    INACTIVE = "inactive"
    ERROR = "error"
