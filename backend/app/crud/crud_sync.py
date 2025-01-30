"""CRUD operations for syncs."""

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app import schemas
from app.crud._base import CRUDBase
from app.models.connection import Connection
from app.models.sync import Sync
from app.schemas.sync import SyncCreate, SyncUpdate


class CRUDSync(CRUDBase[Sync, SyncCreate, SyncUpdate]):
    """CRUD operations for syncs."""

    async def get_all_for_white_label(
        self, db: AsyncSession, white_label_id: UUID, current_user: schemas.User
    ) -> list[Sync]:
        """Get sync by white label ID.

        Args:
            db (AsyncSession): The database session
            white_label_id (UUID): The ID of the white label
            current_user (schemas.User): The current user

        Returns:
            list[Sync]: The syncs
        """
        stmt = select(Sync).where(Sync.white_label_id == white_label_id)
        result = await db.execute(stmt)
        syncs = result.scalars().unique().all()
        for sync in syncs:
            self._validate_if_user_has_permission(sync, current_user)
        return syncs

    async def get_all_for_source_connection(
        self, db: AsyncSession, source_connection_id: UUID, current_user: schemas.User
    ) -> list[Sync]:
        """Get all syncs for a source connection.

        Args:
            db (AsyncSession): The database session
            source_connection_id (UUID): The ID of the source connection
            current_user (schemas.User): The current user
        Returns:
            list[Sync]: The syncs
        """
        stmt = select(Sync).where(Sync.source_connection_id == source_connection_id)
        result = await db.execute(stmt)
        syncs = result.scalars().unique().all()

        for sync in syncs:
            self._validate_if_user_has_permission(sync, current_user)

        return syncs

    async def get_all_for_destination_connection(
        self, db: AsyncSession, destination_connection_id: UUID, current_user: schemas.User
    ) -> list[Sync]:
        """Get all syncs for a destination connection.

        Args:
            db (AsyncSession): The database session
            destination_connection_id (UUID): The ID of the destination connection
            current_user (schemas.User): The current user

        Returns:
            list[Sync]: The syncs
        """
        stmt = select(Sync).where(Sync.destination_connection_id == destination_connection_id)
        result = await db.execute(stmt)
        syncs = result.scalars().unique().all()
        for sync in syncs:
            self._validate_if_user_has_permission(sync, current_user)
        return syncs

    async def get_all_syncs_join_with_source_connection(
        self, db: AsyncSession, current_user: schemas.User
    ) -> list[schemas.SyncWithSourceConnection]:
        """Get all syncs join with source connection.

        Args:
            db (AsyncSession): The database session
            current_user (schemas.User): The current user

        Returns:
            list[schemas.SyncWithSourceConnection]: The syncs with their source connections
        """
        stmt = (
            select(Sync, Connection)
            .join(Connection, Sync.source_connection_id == Connection.id)
            .where(Sync.organization_id == current_user.organization_id)
        )
        result = await db.execute(stmt)
        rows = result.unique().all()

        return [
            schemas.SyncWithSourceConnection(
                **sync.__dict__, source_connection=schemas.Connection.model_validate(connection)
            )
            for sync, connection in rows
        ]


sync = CRUDSync(Sync)
