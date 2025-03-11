"""CRUD operations for syncs."""

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from airweave import schemas
from airweave.crud._base import CRUDBase
from airweave.db.unit_of_work import UnitOfWork
from airweave.models.connection import Connection
from airweave.models.sync import Sync
from airweave.schemas.sync import SyncCreate, SyncUpdate


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

    async def remove_all_for_connection(
        self, db: AsyncSession, connection_id: UUID, current_user: schemas.User, uow: UnitOfWork
    ) -> list[Sync]:
        """Remove all syncs for a connection.

        Args:
            db (AsyncSession): The database session
            connection_id (UUID): The ID of the connection
            current_user (schemas.User): The current user
            uow (UnitOfWork): The unit of work
        Returns:
            list[Sync]: The removed syncs
        """
        stmt = (
            select(Sync)
            .where(
                (Sync.source_connection_id == connection_id)
                | (Sync.destination_connection_id == connection_id)
            )
            .where(Sync.organization_id == current_user.organization_id)
        )
        result = await db.execute(stmt)
        syncs = result.scalars().unique().all()

        removed_syncs = []
        for sync in syncs:
            removed_sync = await self.remove(db, id=sync.id, current_user=current_user, uow=uow)
            removed_syncs.append(removed_sync)

        return removed_syncs


sync = CRUDSync(Sync)
