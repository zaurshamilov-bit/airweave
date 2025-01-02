"""Module for data synchronization."""

from sqlalchemy.ext.asyncio import AsyncSession

from app import crud, schemas
from app.platform.sync.context import SyncContext


class SyncService:
    """Main service for data synchronization."""

    async def create(
        self, db: AsyncSession, sync: schemas.SyncCreate, current_user: schemas.User
    ) -> schemas.Sync:
        """Create a new sync."""
        return await crud.sync.create(db, sync, current_user)

    async def run(
        self,
        db: AsyncSession,
        sync: schemas.Sync,
        current_user: schemas.User,
    ) -> schemas.Sync:
        """Run a sync."""
        sync_context = await self.create_sync_context(db, sync, current_user)

    async def create_sync_context(
        self, db: AsyncSession, sync: schemas.Sync, current_user: schemas.User
    ) -> SyncContext:
        """Create a sync context."""
        source_connection = await crud.connection.get(db, sync.source_id, current_user)
        destination_connection = await crud.connection.get(db, sync.destination_id, current_user)
        embedding_model_connection = await crud.connection.get(
            db, sync.embedding_model_id, current_user
        )

        if not source_connection or not destination_connection:
            raise ValueError("Source or destination connection not found")

        if not embedding_model_connection:
            pass  # TODO: revert to base embedding model

        source = source_connection.source
        destination = destination_connection.destination
        embedding_model = embedding_model_connection.embedding_model

        return SyncContext(source, destination, embedding_model, sync)
