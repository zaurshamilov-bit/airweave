"""Service for managing source connections."""

from typing import Any, Dict, List, Optional, Tuple
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from airweave import crud, schemas
from airweave.core import credentials
from airweave.core.constants.native_connections import NATIVE_QDRANT_UUID, NATIVE_TEXT2VEC_UUID
from airweave.core.logging import logger
from airweave.core.shared_models import ConnectionStatus, SourceConnectionStatus, SyncStatus
from airweave.core.sync_service import sync_service
from airweave.db.unit_of_work import UnitOfWork
from airweave.models.integration_credential import IntegrationType
from airweave.platform.auth.schemas import AuthType
from airweave.platform.locator import resource_locator

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

    async def _validate_auth_fields(
        self, db: AsyncSession, source_short_name: str, auth_fields: Optional[Dict[str, Any]]
    ) -> dict:
        """Validate auth fields based on auth type.

        Only works for config_class auth type.

        Args:
            db: The database session
            source_short_name: The short name of the source
            auth_fields: The auth fields to validate

        Returns:
            The validated auth fields as a dict

        Raises:
            HTTPException: If auth fields are invalid or not supported
        """
        # Get the source info
        source = await crud.source.get_by_short_name(db, short_name=source_short_name)
        if not source:
            raise HTTPException(status_code=404, detail=f"Source '{source_short_name}' not found")

        BASE_ERROR_MESSAGE = (
            f"See https://docs.airweave.ai/docs/connectors/{source.short_name}#authentication "
            f"for more information."
        )

        # This method only supports config_class auth type
        if source.auth_type != AuthType.config_class:
            if auth_fields is not None:
                raise HTTPException(
                    status_code=422,
                    detail=f"Source {source.name} does not support auth fields. "
                    + BASE_ERROR_MESSAGE,
                )
        else:
            if auth_fields is None:
                raise HTTPException(
                    status_code=422,
                    detail=f"Source {source.name} requires auth fields. " + BASE_ERROR_MESSAGE,
                )

        # Create and validate auth config
        try:
            auth_config_class = resource_locator.get_auth_config(source.auth_config_class)
            auth_config = auth_config_class(**auth_fields)
            return auth_config.model_dump()
        except Exception as e:
            source_connection_logger.error(f"Failed to validate auth fields: {e}")

            # Check if it's a Pydantic validation error and format it nicely
            from pydantic import ValidationError

            if isinstance(e, ValidationError):
                # Extract the field names and error messages
                error_messages = []
                for error in e.errors():
                    field = ".".join(str(loc) for loc in error.get("loc", []))
                    msg = error.get("msg", "")
                    error_messages.append(f"Field '{field}': {msg}")

                error_detail = (
                    f"Invalid configuration for {source.auth_config_class}:\n"
                    + "\n".join(error_messages)
                )
                raise HTTPException(
                    status_code=422,
                    detail=f"Invalid auth fields: {error_detail}. " + BASE_ERROR_MESSAGE,
                ) from e
            else:
                # For other types of errors
                raise HTTPException(
                    status_code=422,
                    detail=f"Invalid auth fields: {str(e)}. " + BASE_ERROR_MESSAGE,
                ) from e

    async def create_source_connection(
        self,
        db: AsyncSession,
        source_connection_in: schemas.SourceConnectionCreate,
        current_user: schemas.User,
    ) -> Tuple[schemas.SourceConnection, Optional[schemas.SyncJob]]:
        """Create a new source connection with all related objects.

        This method:
        1. Creates an integration credential with auth fields if provided
        2. Creates the connection to the source (schemas.Connection)
        3. Creates a collection if not provided
        4. Creates a sync configuration and DAG
        5. Creates a sync job if immediate execution is requested
        6. Creates the source connection (schemas.SourceConnection)

        Args:
            db: The database session
            source_connection_in: The source connection to create
            current_user: The current user

        Returns:
            A tuple of (source_connection, sync_job)

        Raises:
            HTTPException: If the source is not found
        """
        # Separate core and auxiliary attributes
        core_attrs, aux_attrs = source_connection_in.map_to_core_and_auxiliary_attributes()

        async with UnitOfWork(db) as uow:
            # Get the source information
            source = await crud.source.get_by_short_name(
                db, short_name=source_connection_in.short_name
            )
            if not source:
                raise HTTPException(status_code=404, detail="Source not found")

            # Validate auth
            auth_fields = await self._validate_auth_fields(
                db, source_connection_in.short_name, aux_attrs["auth_fields"]
            )

            # 1. Create integration credential if auth fields are provided
            integration_credential_id = None
            if aux_attrs["auth_fields"] is not None:
                # Create the integration credential
                integration_cred_in = schemas.IntegrationCredentialCreateEncrypted(
                    name=f"{source.name} - {current_user.email}",
                    description=f"Credentials for {source.name} - {current_user.email}",
                    integration_short_name=source_connection_in.short_name,
                    integration_type=IntegrationType.SOURCE,
                    auth_type=source.auth_type,
                    encrypted_credentials=credentials.encrypt(auth_fields),
                    auth_config_class=source.auth_config_class,
                )

                integration_credential = await crud.integration_credential.create(
                    uow.session, obj_in=integration_cred_in, current_user=current_user, uow=uow
                )

                await uow.session.flush()
                integration_credential_id = integration_credential.id

            # 2. Create the connection object for source (system table)
            connection_create = schemas.ConnectionCreate(
                name=source_connection_in.name,
                integration_type=IntegrationType.SOURCE,
                integration_credential_id=integration_credential_id,
                status=ConnectionStatus.ACTIVE,
                short_name=source_connection_in.short_name,
            )

            connection = await crud.connection.create(
                db=uow.session, obj_in=connection_create, current_user=current_user, uow=uow
            )

            await uow.session.flush()
            connection_id = connection.id

            # 3. Check if we need to create a collection first
            if "collection" not in core_attrs:
                # Create a collection with the same name as the source connection
                collection_in = schemas.CollectionCreate(
                    name=f"Collection for {source_connection_in.name}",
                    description=f"Auto-generated collection for {source_connection_in.name}",
                )
                collection = await crud.collection.create(
                    db=uow.session, obj_in=collection_in, current_user=current_user, uow=uow
                )
                await uow.session.flush()
            else:
                readable_collection_id = core_attrs["collection"]
                collection = await crud.collection.get_by_readable_id(
                    db=uow.session, readable_id=readable_collection_id, current_user=current_user
                )
                if not collection:
                    raise HTTPException(
                        status_code=404, detail=f"Collection '{readable_collection_id}' not found"
                    )

            # 4. Create the sync
            sync_in = schemas.SyncCreate(
                name=f"Sync for {source_connection_in.name}",
                description=f"Auto-generated sync for {source_connection_in.name}",
                source_connection_id=connection_id,  # ID of connection system table
                embedding_model_connection_id=NATIVE_TEXT2VEC_UUID,
                destination_connection_ids=[NATIVE_QDRANT_UUID],
                cron_schedule=aux_attrs["cron_schedule"],
                status=SyncStatus.ACTIVE,
                run_immediately=aux_attrs["sync_immediately"],
            )

            # 5. Use the sync service to create the sync and automatically the DAG
            sync, sync_job = await sync_service.create_and_run_sync(
                db=uow.session, sync_in=sync_in, current_user=current_user, uow=uow
            )

            # 6. Create the source connection from core attributes
            source_connection_create = schemas.SourceConnectionCreateWithRelatedIds(
                **core_attrs,
                connection_id=connection_id,
                readable_collection_id=collection.readable_id,
                sync_id=sync.id,
            )

            source_connection = await crud.source_connection.create(
                db=uow.session, obj_in=source_connection_create, current_user=current_user, uow=uow
            )
            await uow.session.flush()

            # map to schemas and return
            source_connection = schemas.SourceConnection.from_orm_with_collection_mapping(
                source_connection
            )
            sync_job = schemas.SyncJob.model_validate(sync_job, from_attributes=True)

        return source_connection, sync_job

    async def get_source_connection(
        self,
        db: AsyncSession,
        source_connection_id: UUID,
        show_auth_fields: bool = False,
        current_user: schemas.User = None,
    ) -> schemas.SourceConnection:
        """Get a source connection with all related data.

        This method enriches the source connection with data from related objects:
        1. Connection information
        2. Integration credential and decrypted auth fields (if exists)
        3. Sync information and latest sync job status (if exists)
        4. Collection information (if exists)

        Args:
            db: The database session
            source_connection_id: The ID of the source connection
            show_auth_fields: Whether to show the auth fields
            current_user: The current user

        Returns:
            The enriched source connection

        Raises:
            HTTPException: If the source connection is not found
        """
        # Get the source connection from database
        source_connection = await crud.source_connection.get(
            db=db, id=source_connection_id, current_user=current_user
        )

        if not source_connection:
            raise HTTPException(status_code=404, detail="Source connection not found")

        # Convert to schema model to start building the response
        source_connection_schema = schemas.SourceConnection.from_orm_with_collection_mapping(
            source_connection
        )

        # 1. Get the connection and its credentials if they exist
        if source_connection.connection_id:
            connection = await crud.connection.get(
                db=db, id=source_connection.connection_id, current_user=current_user
            )

            if connection and connection.integration_credential_id:
                # Get and decrypt the integration credential
                integration_credential = await crud.integration_credential.get(
                    db=db, id=connection.integration_credential_id, current_user=current_user
                )

                if integration_credential and integration_credential.encrypted_credentials:
                    if show_auth_fields:
                        # Decrypt credentials and attach to source connection
                        decrypted_auth_fields = credentials.decrypt(
                            integration_credential.encrypted_credentials
                        )
                        source_connection_schema.auth_fields = decrypted_auth_fields
                    else:
                        source_connection_schema.auth_fields = "********"

        # 2. Load sync information and latest job status if it exists
        if source_connection.sync_id:
            # Get detailed sync information
            sync = await crud.sync.get(
                db=db, id=source_connection.sync_id, current_user=current_user
            )

            if sync:
                # Get the most recent sync job
                latest_jobs = await sync_service.list_sync_jobs(
                    db=db,
                    current_user=current_user,
                    sync_id=source_connection.sync_id,
                    limit=1,  # Just get the latest job
                )

                if latest_jobs:
                    latest_job = latest_jobs[0]
                    # Add latest job info to the source connectio
                    source_connection_schema.latest_sync_job_status = latest_job.status
                    source_connection_schema.latest_sync_job_id = latest_job.id
                    source_connection_schema.latest_sync_job_started_at = latest_job.started_at
                    source_connection_schema.latest_sync_job_completed_at = latest_job.completed_at

        return source_connection_schema

    async def get_all_source_connections(
        self,
        db: AsyncSession,
        current_user: schemas.User,
        skip: int = 0,
        limit: int = 100,
    ) -> List[schemas.SourceConnectionListItem]:
        """Get all source connections for a user with minimal core attributes.

        This version uses a simplified schema (SourceConnectionListItem) that includes
        only the core attributes directly from the source connection model.

        Args:
            db: The database session
            current_user: The current user
            skip: The number of source connections to skip
            limit: The maximum number of source connections to return

        Returns:
            A list of simplified source connection list items
        """
        # Get all source connections for the user
        source_connections = await crud.source_connection.get_all_for_user(
            db=db, current_user=current_user, skip=skip, limit=limit
        )

        if not source_connections:
            return []

        # Create list items directly from source connections
        list_items = [
            schemas.SourceConnectionListItem(
                id=sc.id,
                name=sc.name,
                description=sc.description,
                short_name=sc.short_name,
                status=sc.status,
                created_at=sc.created_at,
                modified_at=sc.modified_at,
                sync_id=sc.sync_id,
                collection=sc.readable_collection_id,  # map to collection
            )
            for sc in source_connections
        ]

        return list_items

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
            if source_connection_in.auth_fields and source_connection.connection_id:
                # First get the connection to get the credential ID
                connection = await crud.connection.get(
                    uow.session, id=source_connection.connection_id, current_user=current_user
                )

                if connection and connection.integration_credential_id:
                    # Get the credential and update it
                    integration_credential = await crud.integration_credential.get(
                        uow.session,
                        id=connection.integration_credential_id,
                        current_user=current_user,
                    )

                    if integration_credential:
                        auth_fields_dict = source_connection_in.auth_fields.model_dump()
                        validated_auth_fields = await self._validate_auth_fields(
                            uow.session,
                            source_connection.short_name,
                            auth_fields_dict,
                        )
                        credential_update = schemas.IntegrationCredentialUpdate(
                            encrypted_credentials=credentials.encrypt(validated_auth_fields)
                        )
                        await crud.integration_credential.update(
                            uow.session,
                            db_obj=integration_credential,
                            obj_in=credential_update,
                            current_user=current_user,
                            uow=uow,
                        )

            await uow.commit()

            # Get the updated source connection with related data
            return await self.get_source_connection(
                db=uow.session, source_connection_id=source_connection_id, current_user=current_user
            )

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

        # Save a copy of the source_connection for returning
        source_connection_schema = schemas.SourceConnection.from_orm_with_collection_mapping(
            source_connection
        )

        await crud.source_connection.remove(
            db=db, id=source_connection_id, current_user=current_user
        )

        return source_connection_schema

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
    ) -> list[schemas.SourceConnectionJob]:
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
        sync_jobs = await sync_service.list_sync_jobs(
            db=db, current_user=current_user, sync_id=source_connection.sync_id
        )

        # Map SyncJob objects to SourceConnectionJob objects
        source_connection_jobs = []
        for job in sync_jobs:
            # Create a new SourceConnectionJob with data from SyncJob
            sync_job_schema = schemas.SyncJob.model_validate(job, from_attributes=True)
            source_connection_job = sync_job_schema.to_source_connection_job(source_connection_id)
            source_connection_jobs.append(source_connection_job)

        return source_connection_jobs

    async def get_source_connection_job(
        self,
        db: AsyncSession,
        source_connection_id: UUID,
        job_id: UUID,
        current_user: schemas.User,
    ) -> schemas.SourceConnectionJob:
        """Get a specific sync job for a source connection.

        Args:
            db: The database session
            source_connection_id: The ID of the source connection
            job_id: The ID of the sync job
            current_user: The current user

        Returns:
            The sync job

        Raises:
            HTTPException: If the source connection or job is not found
        """
        source_connection = await crud.source_connection.get(
            db=db, id=source_connection_id, current_user=current_user
        )
        if not source_connection:
            raise HTTPException(status_code=404, detail="Source connection not found")

        if not source_connection.sync_id:
            raise HTTPException(status_code=404, detail="Source connection has no associated sync")

        # Get the specific job for the sync
        sync_job = await sync_service.get_sync_job(
            db=db, job_id=job_id, current_user=current_user, sync_id=source_connection.sync_id
        )

        sync_job_schema = schemas.SyncJob.model_validate(sync_job, from_attributes=True)

        # Convert to SourceConnectionJob format
        source_connection_job = sync_job_schema.to_source_connection_job(source_connection_id)

        return source_connection_job

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

            # Update connection status if it exists
            if hasattr(source_connection, "connection_id") and source_connection.connection_id:
                connection = await crud.connection.get(
                    uow.session, id=source_connection.connection_id, current_user=current_user
                )
                if connection:
                    connection_status = (
                        ConnectionStatus.ACTIVE
                        if status == SourceConnectionStatus.ACTIVE
                        else ConnectionStatus.INACTIVE
                    )
                    connection_update = schemas.ConnectionUpdate(status=connection_status)
                    await crud.connection.update(
                        uow.session,
                        db_obj=connection,
                        obj_in=connection_update,
                        current_user=current_user,
                        uow=uow,
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
