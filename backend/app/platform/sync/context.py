"""Module for sync context."""

from typing import Optional

from app import schemas
from app.platform.destinations._base import BaseDestination
from app.platform.embedding_models._base import BaseEmbeddingModel
from app.platform.sources._base import BaseSource


class SyncContext:
    """Context container for a sync."""

    source: BaseSource
    destination: BaseDestination
    embedding_model: BaseEmbeddingModel
    sync: schemas.Sync
    sync: schemas.SyncJob
    white_label: Optional[schemas.WhiteLabel] = None

    def __init__(
        self,
        source: BaseSource,
        destination: BaseDestination,
        embedding_model: BaseEmbeddingModel,
        sync: schemas.Sync,
        sync_job: schemas.SyncJob,
        white_label: Optional[schemas.WhiteLabel] = None,
    ):
        """Initialize the sync context."""
        self.source = source
        self.destination = destination
        self.embedding_model = embedding_model
        self.sync = sync
        self.sync_job = sync_job
        self.white_label = white_label
