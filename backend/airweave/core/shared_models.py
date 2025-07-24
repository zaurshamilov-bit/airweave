"""Shared models for the backend."""

from enum import Enum


class ConnectionStatus(str, Enum):
    """Connection status enum."""

    ACTIVE = "active"
    INACTIVE = "inactive"
    ERROR = "error"


class SyncJobStatus(str, Enum):
    """Sync job status enum."""

    CREATED = "created"
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class IntegrationType(str, Enum):
    """Integration type enum."""

    SOURCE = "source"
    DESTINATION = "destination"
    EMBEDDING_MODEL = "embedding_model"
    AUTH_PROVIDER = "auth_provider"


class SyncStatus(str, Enum):
    """Sync status enum."""

    ACTIVE = "active"
    INACTIVE = "inactive"
    ERROR = "error"


class SourceConnectionStatus(str, Enum):
    """Source connection status enum."""

    ACTIVE = "active"
    IN_PROGRESS = "in_progress"
    FAILING = "failing"


class CollectionStatus(str, Enum):
    """Collection status enum."""

    ACTIVE = "ACTIVE"
    PARTIAL_ERROR = "PARTIAL ERROR"
    NEEDS_SOURCE = "NEEDS SOURCE"
    ERROR = "ERROR"


class ActionType(str, Enum):
    """Action type enum."""

    SYNCS = "syncs"
    ENTITIES = "entities"
    QUERIES = "queries"
    COLLECTIONS = "collections"
    SOURCE_CONNECTIONS = "source_connections"


class SubscriptionType(str, Enum):
    """Subscription type enum for different pricing tiers."""

    FREE = "free"
    BASIC = "basic"
    PRO = "pro"
    TEAM = "team"
    ENTERPRISE = "enterprise"


class PaymentStatus(str, Enum):
    """Payment status enum for subscription billing."""

    CURRENT = "current"  # Payments are up to date
    GRACE_PERIOD = "grace_period"  # In grace period, service still active
    LATE = "late"  # Payment overdue, service may be restricted
    PAID = "paid"  # Recently paid/settled
