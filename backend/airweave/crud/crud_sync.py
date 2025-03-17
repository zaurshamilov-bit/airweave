"""CRUD operations for syncs."""

from typing import Optional
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from airweave import crud, models, schemas
from airweave.core.exceptions import NotFoundException
from airweave.core.shared_models import IntegrationType
from airweave.crud._base import CRUDBase
from airweave.db.unit_of_work import UnitOfWork
from airweave.models.connection import Connection
from airweave.models.sync import Sync
from airweave.models.sync_connection import SyncConnection
from airweave.schemas.sync import SyncCreate, SyncUpdate


class CRUDSync(CRUDBase[Sync, SyncCreate, SyncUpdate]):
    """CRUD operations for syncs."""

    async def get(
        self,
        db: AsyncSession,
        id: UUID,
        current_user: schemas.User,
        with_connections: bool = True,
    ) -> models.Sync:
        """Get the "naked" sync by ID without any connections.

        Args:
            db (AsyncSession): The database session
            id (UUID): The ID of the sync
            current_user (schemas.User): The current user
            with_connections (bool): Whether to include connections in the sync
        Returns:
            models.Sync: The sync without any connections
        """
        # Get the sync without any connections
        sync = await super().get(db, id=id, current_user=current_user)

        if not sync:
            raise HTTPException(status_code=404, detail="Sync not found")

        if with_connections:
            # Enrich the sync with all its connections
            sync = await self.enrich_sync_with_connections(db, sync=sync, current_user=current_user)

        # Validate user permissions
        self._validate_if_user_has_permission(
            sync, current_user
        )  # NB: raises airweave.core.exceptions.PermissionException if user doesn't have permission
        return sync

    async def get_all_for_user(
        self,
        db: AsyncSession,
        current_user: schemas.User,
        *,
        skip: int = 0,
        limit: int = 100,
        with_connections: bool = True,
    ) -> list[schemas.Sync]:
        """Get all syncs for a user.

        Args:
        ----
            db (AsyncSession): The database session
            current_user (schemas.User): The current user
            skip (int): The number of syncs to skip
            limit (int): The number of syncs to return
            with_connections (bool): Whether to include connections in the syncs

        Returns:
        -------
            list[schemas.Sync]: The syncs
        """
        # Get all syncs for the user using the base class method
        syncs = await super().get_all_for_user(db, current_user, skip=skip, limit=limit)

        # Enrich the syncs with their connections if requested
        if with_connections:
            syncs = [
                await self.enrich_sync_with_connections(db, sync, current_user) for sync in syncs
            ]
        return syncs

    async def enrich_sync_with_connections(
        self, db: AsyncSession, sync: models.Sync, current_user: schemas.User
    ) -> schemas.Sync:
        """Enrich a sync with all its connections.

        Args:
            db (AsyncSession): The database session
            sync (models.Sync): The sync
            current_user (schemas.User): The current user

        Returns:
            schemas.Sync: The sync with its connections
        """
        # Get all connections for the sync
        stmt = (
            select(Connection, SyncConnection)
            .join(SyncConnection, Connection.id == SyncConnection.connection_id)
            .where(SyncConnection.sync_id == sync.id)
        )
        result = await db.execute(stmt)
        connections = [conn for conn, _ in result.unique().all()]

        # Categorize connections based on their type
        source_connection = None
        destination_connections = []
        embedding_model_connection = None

        for conn in connections:
            if conn.integration_type == IntegrationType.SOURCE:
                source_connection = schemas.Connection.model_validate(conn)
            elif conn.integration_type == IntegrationType.DESTINATION:
                destination_connections.append(schemas.Connection.model_validate(conn))
            elif conn.integration_type == IntegrationType.EMBEDDING_MODEL:
                embedding_model_connection = schemas.Connection.model_validate(conn)

        # Extract connection IDs for the base schema fields
        source_connection_id = source_connection.id if source_connection else None
        destination_connection_ids = [conn.id for conn in destination_connections]
        embedding_model_connection_id = (
            embedding_model_connection.id if embedding_model_connection else None
        )

        # Prepare the data dictionary with all fields
        sync_dict = {**sync.__dict__}
        if "_sa_instance_state" in sync_dict:
            sync_dict.pop("_sa_instance_state")

        # Add connection IDs
        sync_dict["source_connection_id"] = source_connection_id
        sync_dict["destination_connection_ids"] = destination_connection_ids
        sync_dict["embedding_model_connection_id"] = embedding_model_connection_id

        # Construct the response with full connections
        return schemas.Sync.model_validate(sync_dict)

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
        # Use the SyncConnection join table to find syncs with the given source connection
        stmt = (
            select(Sync)
            .join(SyncConnection, Sync.id == SyncConnection.sync_id)
            .join(Connection, SyncConnection.connection_id == Connection.id)
            .where(SyncConnection.connection_id == source_connection_id)
            .where(Connection.integration_type == IntegrationType.SOURCE)
            .where(Sync.organization_id == current_user.organization_id)
        )
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
        # Use the SyncConnection join table to find syncs with the given destination connection
        stmt = (
            select(Sync)
            .join(SyncConnection, Sync.id == SyncConnection.sync_id)
            .join(Connection, SyncConnection.connection_id == Connection.id)
            .where(SyncConnection.connection_id == destination_connection_id)
            .where(Connection.integration_type == IntegrationType.DESTINATION)
            .where(Sync.organization_id == current_user.organization_id)
        )
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
        # First, get all syncs for the user
        syncs = await super().get_all_for_user(db, current_user)

        # Get all source connections for these syncs using the SyncConnection join table
        stmt = (
            select(Sync, Connection, SyncConnection)
            .join(SyncConnection, Sync.id == SyncConnection.sync_id)
            .join(Connection, SyncConnection.connection_id == Connection.id)
            .where(Sync.organization_id == current_user.organization_id)
            .where(Connection.integration_type == IntegrationType.SOURCE)
        )
        result = await db.execute(stmt)
        rows = result.unique().all()

        # Create a mapping of sync_id to source connection
        sync_to_source_connection = {
            sync.id: schemas.Connection.model_validate(connection) for sync, connection, _ in rows
        }

        # Enrich each sync with its connections
        result_syncs = []
        for sync in syncs:
            # Enrich the sync with all its connections
            enriched_sync = await self.enrich_sync_with_connections(db, sync, current_user)

            # Create the SyncWithSourceConnection object
            if sync.id in sync_to_source_connection:
                # The enriched_sync is already a schemas.Sync object, so we can use it directly
                sync_with_source = schemas.SyncWithSourceConnection(
                    **enriched_sync.model_dump(),
                    source_connection=sync_to_source_connection[sync.id],
                )
                result_syncs.append(sync_with_source)

        return result_syncs

    async def create(
        self,
        db: AsyncSession,
        *,
        obj_in: SyncCreate,
        current_user: schemas.User,
        uow: Optional[UnitOfWork] = None,
    ) -> schemas.Sync:
        """Create a sync.

        1. Pop off all the connection ids from the obj_in
        2. Then validate the connections
        3. Write sync object to db
        4. Write sync_connection objects to db
        5. Commit and refresh

        Args:
            db (AsyncSession): The database session
            obj_in (SyncCreate): The sync to create
            current_user (schemas.User): The current user
            uow (UnitOfWork, optional): The unit of work
        Returns:
            schemas.Sync: The model validated schema of the created sync
        """
        # Dump the obj_in to a dict
        obj_in_dict = obj_in.model_dump()

        # Pop off the connection ids
        source_connection_id = obj_in_dict.pop("source_connection_id")
        destination_connection_ids = obj_in_dict.pop("destination_connection_ids")  # this is a list
        embedding_model_connection_id = obj_in_dict.pop("embedding_model_connection_id")

        # Validate the connections
        await self._validate_connections(
            db,
            source_connection_id,
            destination_connection_ids,
            embedding_model_connection_id,
            current_user,
        )

        # Write the sync object to db
        sync = await super().create(db, obj_in=obj_in_dict, current_user=current_user, uow=uow)

        # Flush the session to ensure sync.id is available
        if uow:
            await uow.session.flush()
        else:
            await db.flush()

        # Write the sync_connection objects to db
        connection_ids = (
            [source_connection_id] + destination_connection_ids + [embedding_model_connection_id]
        )
        for connection_id in connection_ids:
            sync_connection = SyncConnection(
                sync_id=sync.id,
                connection_id=connection_id,
            )
            db.add(sync_connection)

        # Commit and refresh
        if not uow:
            await db.commit()
            await db.refresh(sync)

        # Re-add the connection IDs to create a fully model-validated schema
        sync_dict = {**sync.__dict__}
        if "_sa_instance_state" in sync_dict:
            sync_dict.pop("_sa_instance_state")

        sync_dict["source_connection_id"] = source_connection_id
        sync_dict["destination_connection_ids"] = destination_connection_ids
        sync_dict["embedding_model_connection_id"] = embedding_model_connection_id

        # Return a properly model-validated instance
        return schemas.Sync.model_validate(sync_dict)

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
        # Use the SyncConnection join table to find all syncs associated with this connection
        stmt = (
            select(Sync)
            .join(SyncConnection, Sync.id == SyncConnection.sync_id)
            .where(SyncConnection.connection_id == connection_id)
            .where(Sync.organization_id == current_user.organization_id)
        )
        result = await db.execute(stmt)
        syncs = result.scalars().unique().all()

        removed_syncs = []
        for sync in syncs:
            removed_sync = await self.remove(db, id=sync.id, current_user=current_user, uow=uow)
            removed_syncs.append(removed_sync)

        return removed_syncs

    async def _validate_connections(
        self,
        db: AsyncSession,
        source_connection_id: UUID,
        destination_connection_ids: list[UUID],
        embedding_model_connection_id: UUID,
        current_user: schemas.User,
    ) -> None:
        """Validate the connections.

        Args:
            db (AsyncSession): The database session
            source_connection_id (UUID): The ID of the source connection
            destination_connection_ids (list[UUID]): The IDs of the destination connections
            embedding_model_connection_id (UUID): The ID of the embedding model connection
            current_user (schemas.User): The current user
        """
        # Validate the source connection and that it is a source
        source_connection = await crud.connection.get(
            db, id=source_connection_id, current_user=current_user
        )
        if not source_connection:
            raise NotFoundException("Source connection not found")
        if source_connection.integration_type != IntegrationType.SOURCE:
            raise ValueError("Source connection is not a source")

        # Validate the destination connections and that they are destinations
        for destination_connection_id in destination_connection_ids:
            destination_connection = await crud.connection.get(
                db, id=destination_connection_id, current_user=current_user
            )
            if not destination_connection:
                raise NotFoundException("Destination connection not found")

            if destination_connection.integration_type != IntegrationType.DESTINATION:
                raise ValueError("Destination connection is not a destination")

        # Validate the embedding model connection and that it is an embedding model
        embedding_model_connection = await crud.connection.get(
            db, id=embedding_model_connection_id, current_user=current_user
        )
        if not embedding_model_connection:
            raise NotFoundException("Embedding model connection not found")
        if embedding_model_connection.integration_type != IntegrationType.EMBEDDING_MODEL:
            raise ValueError("Embedding model connection is not an embedding model")

    async def remove(
        self,
        db: AsyncSession,
        *,
        id: UUID,
        current_user: schemas.User,
        uow: Optional[UnitOfWork] = None,
    ) -> schemas.Sync:
        """Remove a sync.

        Override the base method to ensure the returned sync is enriched with connections.

        Args:
            db (AsyncSession): The database session
            id (UUID): The ID of the sync
            current_user (schemas.User): The current user
            uow (UnitOfWork, optional): The unit of work

        Returns:
            schemas.Sync: The model validated schema of the removed sync
        """
        # First, fetch the sync with its connections before deletion
        enriched_sync = await self.get(db, id=id, current_user=current_user)

        # Then remove using the base method
        removed_sync = await super().remove(db, id=id, current_user=current_user, uow=uow)

        # The connections are already deleted, so we need to create the response
        # from the previously enriched sync
        sync_dict = {**removed_sync.__dict__}
        if "_sa_instance_state" in sync_dict:
            sync_dict.pop("_sa_instance_state")

        # Add the connection IDs from the pre-fetched enriched sync
        sync_dict["source_connection_id"] = enriched_sync.source_connection_id
        sync_dict["destination_connection_ids"] = enriched_sync.destination_connection_ids
        sync_dict["embedding_model_connection_id"] = enriched_sync.embedding_model_connection_id

        # Return a properly model-validated instance
        return schemas.Sync.model_validate(sync_dict)


sync = CRUDSync(Sync)
