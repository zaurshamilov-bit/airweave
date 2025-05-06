"""Service for managing source connections."""

from typing import Optional, Tuple
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from airweave import crud, schemas
from airweave.core import credentials
from airweave.core.constants.native_connections import NATIVE_QDRANT_UUID, NATIVE_TEXT2VEC_UUID
from airweave.core.logging import logger
from airweave.core.shared_models import SourceConnectionStatus, SyncStatus
from airweave.core.sync_service import sync_service
from airweave.db.unit_of_work import UnitOfWork
from airweave.models.integration_credential import IntegrationType

source_connection_logger = logger.with_prefix("Source Connection Service: ").with_context(
    component="source_connection_service"
)


class SourceConnectionService:
    """Service for managing source connections.

    This service encapsulates the complex transactions required for source connections,
    including:
    - Creating source connections with related objects (integration credential, sync, dag)
    - Updating source connections and keeping related objects in sync
    - Deleting source connections and all related objects
    - Running sync jobs for source connections
    """

    async def create_source_connection(
        self,
        db: AsyncSession,
        source_connection_in: schemas.SourceConnectionCreate,
        current_user: schemas.User,
    ) -> Tuple[schemas.SourceConnection, Optional[schemas.SyncJob]]:
        """Create a new source connection with all related objects.

        This method:
        1. Creates an integration credential with auth fields if provided
        2. Creates a collection if not provided
        3. Creates the source connection
        4. Creates a sync configuration and DAG
        5. Creates a sync job if immediate execution is requested

        Args:
            db: The database session
            source_connection_in: The source connection to create
            current_user: The current user

        Returns:
            A tuple of (source_connection, sync_job)

        Raises:
            HTTPException: If the source is not found
        """
        async with UnitOfWork(db) as uow:
            # Get the source information
            source = await crud.source.get_by_short_name(
                db, short_name=source_connection_in.short_name
            )
            if not source:
                raise HTTPException(status_code=404, detail="Source not found")

            # 1. Create integration credential if auth fields are provided
            integration_credential_id = None
            if source_connection_in.auth_fields:
                # Encrypt the auth fields
                encrypted_credentials = credentials.encrypt(source_connection_in.auth_fields.dict())

                # Create the integration credential
                integration_cred_in = schemas.IntegrationCredentialCreateEncrypted(
                    name=f"{source.name} - {current_user.email}",
                    description=f"Credentials for {source.name} - {current_user.email}",
                    integration_short_name=source_connection_in.short_name,
                    integration_type=IntegrationType.SOURCE,
                    auth_type=source.auth_type,
                    encrypted_credentials=encrypted_credentials,
                    auth_config_class=source.auth_config_class,
                )

                integration_credential = await crud.integration_credential.create(
                    uow.session, obj_in=integration_cred_in, current_user=current_user, uow=uow
                )

                await uow.session.flush()
                integration_credential_id = integration_credential.id

            # 2. Check if we need to create a collection first
            collection_readable_id = source_connection_in.collection
            if not collection_readable_id:
                # Create a collection with the same name as the source connection
                collection_in = schemas.CollectionCreate(
                    name=f"Collection for {source_connection_in.name}",
                    description=f"Auto-generated collection for {source_connection_in.name}",
                )
                collection = await crud.collection.create(
                    db=uow.session, obj_in=collection_in, current_user=current_user, uow=uow
                )
                await uow.session.flush()
                collection_readable_id = collection.readable_id

            # 3. Create the source connection
            source_connection_create = schemas.SourceConnectionCreate(
                name=source_connection_in.name,
                description=source_connection_in.description,
                config_fields=source_connection_in.config_fields,
                collection=collection_readable_id,
                cron_schedule=source_connection_in.cron_schedule,
                sync_immediately=source_connection_in.sync_immediately,
                short_name=source_connection_in.short_name,
                integration_credential_id=integration_credential_id,
            )

            source_connection = await crud.source_connection.create(
                db=uow.session, obj_in=source_connection_create, current_user=current_user, uow=uow
            )
            await uow.session.flush()

            # 4. Create the sync
            sync_in = schemas.SyncCreate(
                name=f"Sync for {source_connection_in.name}",
                description=f"Auto-generated sync for {source_connection_in.name}",
                source_connection_id=source_connection.id,  # Use the source connection ID directly
                embedding_model_connection_id=NATIVE_TEXT2VEC_UUID,
                destination_connection_ids=[NATIVE_QDRANT_UUID],
                cron_schedule=source_connection_in.cron_schedule,
                status=SyncStatus.ACTIVE,
                run_immediately=source_connection_in.sync_immediately,
            )

            # 5. Use the sync service to create the sync and automatically the DAG
            sync, sync_job = await sync_service.create_and_run_sync(
                db=uow.session, sync_in=sync_in, current_user=current_user
            )

            # 6. Link the sync to the source connection
            source_connection_update = schemas.SourceConnectionUpdate(
                sync_id=sync.id,
            )
            source_connection = await crud.source_connection.update(
                db=uow.session,
                db_obj=source_connection,
                obj_in=source_connection_update,
                current_user=current_user,
                uow=uow,
            )

            await uow.commit()

            return source_connection, sync_job

    async def update_source_connection(
        self,
        db: AsyncSession,
        source_connection_id: UUID,
        source_connection_in: schemas.SourceConnectionUpdate,
        current_user: schemas.User,
    ) -> schemas.SourceConnection:
        """Update a source connection and related objects.

        This method:
        1. Updates the source connection
        2. Updates the sync cron schedule if changed
        3. Updates the auth fields in the integration credential if provided

        Args:
            db: The database session
            source_connection_id: The ID of the source connection to update
            source_connection_in: The updated source connection data
            current_user: The current user

        Returns:
            The updated source connection

        Raises:
            HTTPException: If the source connection is not found
        """
        source_connection = await crud.source_connection.get(
            db=db, id=source_connection_id, current_user=current_user
        )
        if not source_connection:
            raise HTTPException(status_code=404, detail="Source connection not found")

        async with UnitOfWork(db) as uow:
            # 1. Update source connection
            source_connection = await crud.source_connection.update(
                db=uow.session,
                db_obj=source_connection,
                obj_in=source_connection_in,
                current_user=current_user,
                uow=uow,
            )

            # 2. If cron_schedule was updated, also update the related sync
            if source_connection_in.cron_schedule is not None and source_connection.sync_id:
                sync = await crud.sync.get(
                    uow.session, id=source_connection.sync_id, current_user=current_user
                )
                if sync:
                    sync_update = schemas.SyncUpdate(
                        cron_schedule=source_connection_in.cron_schedule
                    )
                    await crud.sync.update(
                        uow.session,
                        db_obj=sync,
                        obj_in=sync_update,
                        current_user=current_user,
                        uow=uow,
                    )

            # 3. If auth_fields are provided, update the integration credential
            if source_connection_in.auth_fields and source_connection.integration_credential_id:
                # Get the credential and update it
                integration_credential = await crud.integration_credential.get(
                    uow.session,
                    id=source_connection.integration_credential_id,
                    current_user=current_user,
                )

                if integration_credential:
                    encrypted_credentials = credentials.encrypt(
                        source_connection_in.auth_fields.dict()
                    )
                    credential_update = schemas.IntegrationCredentialUpdate(
                        encrypted_credentials=encrypted_credentials
                    )
                    await crud.integration_credential.update(
                        uow.session,
                        db_obj=integration_credential,
                        obj_in=credential_update,
                        current_user=current_user,
                        uow=uow,
                    )

            await uow.commit()
            return source_connection

    async def delete_source_connection(
        self,
        db: AsyncSession,
        source_connection_id: UUID,
        current_user: schemas.User,
        delete_data: bool = False,
    ) -> schemas.SourceConnection:
        """Delete a source connection and all related components.

        This method:
        1. Deletes the sync if it exists
        2. Deletes the integration credential if it exists
        3. Deletes the source connection

        Args:
            db: The database session
            source_connection_id: The ID of the source connection to delete
            current_user: The current user
            delete_data: Whether to delete the data in destinations

        Returns:
            The deleted source connection

        Raises:
            HTTPException: If the source connection is not found
        """
        source_connection = await crud.source_connection.get(
            db=db, id=source_connection_id, current_user=current_user
        )
        if not source_connection:
            raise HTTPException(status_code=404, detail="Source connection not found")

        async with UnitOfWork(db) as uow:
            # 1. Delete the sync if it exists
            if source_connection.sync_id:
                await sync_service.delete_sync(
                    db=uow.session,
                    sync_id=source_connection.sync_id,
                    current_user=current_user,
                    delete_data=delete_data,
                )

            # 2. Delete the integration credential if it exists
            if source_connection.integration_credential_id:
                await crud.integration_credential.remove(
                    uow.session,
                    id=source_connection.integration_credential_id,
                    current_user=current_user,
                    uow=uow,
                )

            # 3. Delete the source connection
            source_connection = await crud.source_connection.remove(
                db=uow.session, id=source_connection_id, current_user=current_user, uow=uow
            )

            await uow.commit()
            return source_connection

    async def run_source_connection(
        self,
        db: AsyncSession,
        source_connection_id: UUID,
        current_user: schemas.User,
    ) -> schemas.SyncJob:
        """Trigger a sync run for a source connection.

        Args:
            db: The database session
            source_connection_id: The ID of the source connection to run
            current_user: The current user

        Returns:
            The created sync job

        Raises:
            HTTPException: If the source connection is not found or has no associated sync
        """
        source_connection = await crud.source_connection.get(
            db=db, id=source_connection_id, current_user=current_user
        )
        if not source_connection:
            raise HTTPException(status_code=404, detail="Source connection not found")

        if not source_connection.sync_id:
            raise HTTPException(status_code=400, detail="Source connection has no associated sync")

        # Trigger the sync run using the sync service
        sync, sync_job, sync_dag = await sync_service.trigger_sync_run(
            db=db, sync_id=source_connection.sync_id, current_user=current_user
        )

        return sync_job

    async def get_source_connection_jobs(
        self,
        db: AsyncSession,
        source_connection_id: UUID,
        current_user: schemas.User,
    ) -> list[schemas.SyncJob]:
        """Get all sync jobs for a source connection.

        Args:
            db: The database session
            source_connection_id: The ID of the source connection
            current_user: The current user

        Returns:
            A list of sync jobs

        Raises:
            HTTPException: If the source connection is not found
        """
        source_connection = await crud.source_connection.get(
            db=db, id=source_connection_id, current_user=current_user
        )
        if not source_connection:
            raise HTTPException(status_code=404, detail="Source connection not found")

        if not source_connection.sync_id:
            return []

        # Get all jobs for the sync
        return await sync_service.list_sync_jobs(
            db=db, current_user=current_user, sync_id=source_connection.sync_id
        )

    async def update_source_connection_status(
        self,
        db: AsyncSession,
        source_connection_id: UUID,
        status: SourceConnectionStatus,
        current_user: schemas.User,
    ) -> schemas.SourceConnection:
        """Update the status of a source connection.

        This also updates the related sync status to match.

        Args:
            db: The database session
            source_connection_id: The ID of the source connection
            status: The new status
            current_user: The current user

        Returns:
            The updated source connection

        Raises:
            HTTPException: If the source connection is not found
        """
        source_connection = await crud.source_connection.get(
            db=db, id=source_connection_id, current_user=current_user
        )
        if not source_connection:
            raise HTTPException(status_code=404, detail="Source connection not found")

        async with UnitOfWork(db) as uow:
            # Update source connection status
            source_connection = await crud.source_connection.update_status(
                db=uow.session,
                id=source_connection_id,
                status=status,
                current_user=current_user,
            )

            # Update sync status if it exists
            if source_connection.sync_id:
                sync = await crud.sync.get(
                    uow.session, id=source_connection.sync_id, current_user=current_user
                )
                if sync:
                    sync_status = (
                        SyncStatus.ACTIVE
                        if status == SourceConnectionStatus.ACTIVE
                        else SyncStatus.INACTIVE
                    )
                    sync_update = schemas.SyncUpdate(status=sync_status)
                    await crud.sync.update(
                        uow.session,
                        db_obj=sync,
                        obj_in=sync_update,
                        current_user=current_user,
                        uow=uow,
                    )

            await uow.commit()
            return source_connection


# Singleton instance
source_connection_service = SourceConnectionService()
