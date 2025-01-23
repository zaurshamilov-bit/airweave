from enum import Enum


class ConnectionStatus(str, Enum):
    """Connection status enum."""

    ACTIVE = "active"
    INACTIVE = "inactive"
    ERROR = "error"


class SyncJobStatus(str, Enum):
    """Sync job status enum."""

    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"


class IntegrationType(str, Enum):
    """Integration type enum."""

    SOURCE = "source"
    DESTINATION = "destination"
    EMBEDDING_MODEL = "embedding_model"


class SyncStatus(str, Enum):
    """Sync status enum."""

    ACTIVE = "active"
    INACTIVE = "inactive"
    ERROR = "error"
