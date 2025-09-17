"""Refactored source connection service with clean abstractions and explicit auth routing."""

from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from airweave import crud, schemas
from airweave.analytics import business_events
from airweave.api.context import ApiContext
from airweave.core.auth_provider_service import auth_provider_service
from airweave.core.config import settings as core_settings
from airweave.core.shared_models import SourceConnectionStatus, SyncJobStatus
from airweave.core.sync_service import sync_service
from airweave.core.temporal_service import temporal_service
from airweave.crud import connection_init_session
from airweave.db.unit_of_work import UnitOfWork
from airweave.models.connection_init_session import ConnectionInitStatus
from airweave.platform.auth.services import oauth2_service
from airweave.platform.auth.settings import integration_settings
from airweave.schemas.source_connection import AuthenticationMethod


class SourceConnectionService:
    """Refactored service with clean abstractions and singleton pattern.

    Key improvements:
    - Explicit authentication routing based on AuthenticationMethod enum
    - No background tasks or local scheduling (Temporal only)
    - Clean separation of concerns
    - Singleton pattern consistent with CRUD layer
    - Depth-based expansion for responses
    """

    # ===========================
    # Public API Methods
    # ===========================

    async def create(
        self,
        db: AsyncSession,
        *,
        obj_in: schemas.SourceConnectionCreate,
        ctx: ApiContext,
    ) -> schemas.SourceConnection:
        """Create a source connection with explicit auth routing.

        Routes to appropriate handler based on authentication_method.
        Never exposes internal sync/job infrastructure to users.
        """
        # Get source and validate auth method is supported
        source = await self._get_and_validate_source(db, obj_in.short_name)
        source_class = self._get_source_class(source.class_name)

        # Validate authentication method using helper
        self._validate_authentication_method(source_class, obj_in)

        # Route based on authentication method
        handlers = {
            schemas.AuthenticationMethod.DIRECT: self._create_with_direct_auth,
            schemas.AuthenticationMethod.OAUTH_BROWSER: self._create_with_oauth_browser,
            schemas.AuthenticationMethod.OAUTH_TOKEN: self._create_with_oauth_token,
            schemas.AuthenticationMethod.OAUTH_BYOC: self._create_with_oauth_byoc,
            schemas.AuthenticationMethod.AUTH_PROVIDER: self._create_with_auth_provider,
        }

        handler = handlers[obj_in.authentication_method]
        source_connection = await handler(db, obj_in=obj_in, ctx=ctx)

        # Track analytics
        business_events.track_source_connection_created(
            ctx=ctx,
            connection_id=source_connection.id,
            source_short_name=source_connection.short_name,
        )

        return source_connection

    async def get(
        self,
        db: AsyncSession,
        *,
        id: UUID,
        ctx: ApiContext,
    ) -> schemas.SourceConnection:
        """Get a source connection with all available data."""
        source_conn = await crud.source_connection.get(db, id=id, ctx=ctx)
        if not source_conn:
            raise HTTPException(status_code=404, detail="Source connection not found")

        # Build complete response object
        response = await self._build_source_connection_response(db, source_conn, ctx)

        return response

    async def list(
        self,
        db: AsyncSession,
        *,
        ctx: ApiContext,
        collection: Optional[str] = None,
        skip: int = 0,
        limit: int = 100,
    ) -> List[schemas.SourceConnectionListItem]:
        """List source connections with minimal fields."""
        if collection:
            source_conns = await crud.source_connection.get_for_collection(
                db, readable_collection_id=collection, ctx=ctx, skip=skip, limit=limit
            )
        else:
            source_conns = await crud.source_connection.get_multi(
                db, ctx=ctx, skip=skip, limit=limit
            )

        if not source_conns:
            return []

        # Bulk fetch last sync info and entity counts for all connections
        sync_ids = [sc.sync_id for sc in source_conns if sc.sync_id]
        last_sync_info = {}
        entity_counts = {}
        if sync_ids:
            last_sync_info = await self._bulk_fetch_last_sync_info(db, sync_ids, ctx)
            entity_counts = await self._bulk_fetch_entity_counts(db, sync_ids, ctx)

        result = []
        for sc in source_conns:
            # Compute status based on authentication and last sync job
            if not sc.is_authenticated:
                status = SourceConnectionStatus.PENDING_AUTH
            elif sc.sync_id and sc.sync_id in last_sync_info:
                # Check last job status to determine connection status
                job_status = last_sync_info[sc.sync_id].get("last_job_status")
                if job_status == SyncJobStatus.RUNNING:
                    status = SourceConnectionStatus.SYNCING
                elif job_status == SyncJobStatus.FAILED:
                    status = SourceConnectionStatus.ERROR
                else:
                    status = SourceConnectionStatus.ACTIVE
            else:
                status = SourceConnectionStatus.ACTIVE

            result.append(
                schemas.SourceConnectionListItem(
                    id=sc.id,
                    name=sc.name,
                    short_name=sc.short_name,
                    collection=sc.readable_collection_id,
                    status=status,
                    is_authenticated=sc.is_authenticated,
                    created_at=sc.created_at,
                    modified_at=sc.modified_at,
                    last_sync_at=last_sync_info.get(sc.sync_id, {}).get("last_sync_at"),
                    next_sync_at=last_sync_info.get(sc.sync_id, {}).get("next_sync_at"),
                    entities_count=entity_counts.get(sc.sync_id, 0),
                )
            )

        return result

    async def update(
        self,
        db: AsyncSession,
        *,
        id: UUID,
        obj_in: schemas.SourceConnectionUpdate,
        ctx: ApiContext,
    ) -> schemas.SourceConnection:
        """Update a source connection."""
        source_conn = await crud.source_connection.get(db, id=id, ctx=ctx)
        if not source_conn:
            raise HTTPException(status_code=404, detail="Source connection not found")

        async with UnitOfWork(db) as uow:
            # Validate config fields if provided
            if obj_in.config_fields is not None:
                validated_config = await self._validate_config_fields(
                    uow.session, source_conn.short_name, obj_in.config_fields, ctx
                )
                obj_in.config_fields = validated_config

            # Update source connection
            source_conn = await crud.source_connection.update(
                uow.session, db_obj=source_conn, obj_in=obj_in, ctx=ctx, uow=uow
            )

            # Update schedule if provided
            if obj_in.cron_schedule is not None and source_conn.sync_id:
                await self._update_sync_schedule(
                    uow.session, source_conn.sync_id, obj_in.cron_schedule, ctx, uow
                )

            # Update auth fields if provided (direct auth only)
            if obj_in.auth_fields and source_conn.connection_id:
                await self._update_auth_fields(
                    uow.session, source_conn, obj_in.auth_fields, ctx, uow
                )

            await uow.commit()
            await uow.session.refresh(source_conn)

            # Build complete response object INSIDE the UoW
            response = await self._build_source_connection_response(uow.session, source_conn, ctx)

        return response

    async def delete(
        self,
        db: AsyncSession,
        *,
        id: UUID,
        ctx: ApiContext,
    ) -> schemas.SourceConnection:
        """Delete a source connection and all related data."""
        source_conn = await crud.source_connection.get(db, id=id, ctx=ctx)
        if not source_conn:
            raise HTTPException(status_code=404, detail="Source connection not found")

        # Clean up data in destinations
        if source_conn.sync_id and source_conn.readable_collection_id:
            await self._cleanup_destination_data(db, source_conn, ctx)

        # Clean up Temporal schedules
        if source_conn.sync_id:
            await self._cleanup_temporal_schedules(source_conn.sync_id, db, ctx)

        # We need to create the response before deletion
        # Build complete response object while object is still valid and attached
        response = await self._build_source_connection_response(db, source_conn, ctx)

        # Now delete the source connection (cascades to related objects)
        await crud.source_connection.remove(db, id=id, ctx=ctx)

        return response

    async def validate(
        self,
        db: AsyncSession,
        *,
        obj_in: schemas.SourceConnectionValidate,
        ctx: ApiContext,
    ) -> Dict[str, Any]:
        """Validate source connection credentials without creating.

        This is a temporary placeholder until we construct + validate the source connection
        TODO: Replace with source constructor + validate method on source class
        """
        source = await crud.source.get_by_short_name(db, short_name=obj_in.short_name)
        if not source:
            raise HTTPException(status_code=404, detail=f"Source '{obj_in.short_name}' not found")

        # Route validation based on method
        if obj_in.authentication_method == schemas.AuthenticationMethod.DIRECT:
            return await self._validate_direct_auth(db, source, obj_in.auth_fields, ctx)
        elif obj_in.authentication_method in [
            schemas.AuthenticationMethod.OAUTH_TOKEN,
            schemas.AuthenticationMethod.OAUTH_BYOC,
        ]:
            return await self._validate_oauth_token(db, source, obj_in.access_token, ctx)
        else:
            raise HTTPException(
                status_code=400,
                detail=f"Validation not supported for method: {obj_in.authentication_method}",
            )

    async def run(
        self,
        db: AsyncSession,
        *,
        id: UUID,
        ctx: ApiContext,
    ) -> schemas.SourceConnectionJob:
        """Trigger a sync run for a source connection."""
        source_conn = await crud.source_connection.get(db, id=id, ctx=ctx)
        sync_dag = await crud.sync_dag.get_by_sync_id(db, sync_id=source_conn.sync_id, ctx=ctx)
        if not source_conn:
            raise HTTPException(status_code=404, detail="Source connection not found")

        if not source_conn.sync_id:
            raise HTTPException(status_code=400, detail="Source connection has no associated sync")

        # Run through Temporal
        collection = await crud.collection.get_by_readable_id(
            db, readable_id=source_conn.readable_collection_id, ctx=ctx
        )

        collection_schema = schemas.Collection.model_validate(collection, from_attributes=True)
        source_connection_schema = await self._build_source_connection_response(
            db, source_conn, ctx
        )
        sync_dag_schema = schemas.SyncDag.model_validate(sync_dag, from_attributes=True)

        # Trigger sync through Temporal only
        sync, sync_job = await sync_service.trigger_sync_run(
            db, sync_id=source_conn.sync_id, ctx=ctx
        )

        await temporal_service.run_source_connection_workflow(
            sync=sync,
            sync_job=sync_job,
            sync_dag=sync_dag_schema,
            collection=collection_schema,
            source_connection=source_connection_schema,
            ctx=ctx,
        )

        # Convert sync_job to SourceConnectionJob using the built-in conversion method
        sync_job_schema = schemas.SyncJob.model_validate(sync_job, from_attributes=True)
        return sync_job_schema.to_source_connection_job(source_connection_schema.id)

    async def get_jobs(
        self,
        db: AsyncSession,
        *,
        id: UUID,
        ctx: ApiContext,
        limit: int = 100,
    ) -> List[schemas.SourceConnectionJob]:
        """Get sync jobs for a source connection."""
        source_conn = await crud.source_connection.get(db, id=id, ctx=ctx)
        if not source_conn:
            raise HTTPException(status_code=404, detail="Source connection not found")

        if not source_conn.sync_id:
            return []

        sync_jobs = await sync_service.list_sync_jobs(
            db, ctx=ctx, sync_id=source_conn.sync_id, limit=limit
        )

        return [self._sync_job_to_source_connection_job(job, source_conn.id) for job in sync_jobs]

    async def cancel_job(
        self,
        db: AsyncSession,
        *,
        source_connection_id: UUID,
        job_id: UUID,
        ctx: ApiContext,
    ) -> schemas.SourceConnectionJob:
        """Cancel a running sync job for a source connection.

        Updates the job status in the database to CANCELLED and sends
        a cancellation request to the Temporal workflow if it's running.
        """
        # Verify source connection exists and user has access
        source_conn = await crud.source_connection.get(db, id=source_connection_id, ctx=ctx)
        if not source_conn:
            raise HTTPException(status_code=404, detail="Source connection not found")

        if not source_conn.sync_id:
            raise HTTPException(status_code=400, detail="Source connection has no associated sync")

        # Get the sync job and verify it belongs to this source connection
        sync_job = await crud.sync_job.get(db, id=job_id, ctx=ctx)
        if not sync_job:
            raise HTTPException(status_code=404, detail="Sync job not found")

        if sync_job.sync_id != source_conn.sync_id:
            raise HTTPException(
                status_code=400, detail="Sync job does not belong to this source connection"
            )

        # Check if job is in a cancellable state
        if sync_job.status not in [SyncJobStatus.PENDING, SyncJobStatus.RUNNING]:
            raise HTTPException(
                status_code=400, detail=f"Cannot cancel job in {sync_job.status} state"
            )

        # Update job status to CANCELLED in database
        from airweave.core.sync_job_service import sync_job_service

        await sync_job_service.update_status(
            sync_job_id=job_id,
            status=SyncJobStatus.CANCELLED,
            ctx=ctx,
            completed_at=datetime.utcnow(),
        )

        # Cancel the Temporal workflow if it's running
        if sync_job.status == SyncJobStatus.RUNNING:
            try:
                cancelled = await temporal_service.cancel_sync_job_workflow(str(job_id))
                if cancelled:
                    ctx.logger.info(f"Successfully cancelled Temporal workflow for job {job_id}")
                else:
                    ctx.logger.warning(f"No running Temporal workflow found for job {job_id}")
            except Exception as e:
                ctx.logger.error(f"Failed to cancel Temporal workflow for job {job_id}: {e}")
                # Continue even if Temporal cancellation fails - the DB status is already updated

        # Fetch the updated job from database
        await db.refresh(sync_job)

        # Convert to SourceConnectionJob response
        sync_job_schema = schemas.SyncJob.model_validate(sync_job, from_attributes=True)
        return sync_job_schema.to_source_connection_job(source_connection_id)

    async def complete_oauth_callback_no_auth(
        self,
        db: AsyncSession,
        *,
        state: str,
        code: str,
    ) -> schemas.SourceConnection:
        """Complete OAuth flow from callback without requiring authentication.

        This method reconstructs the ApiContext from the stored session data
        since OAuth callbacks come from external providers without platform auth.

        Returns:
            Source connection with authentication details
        """
        # Find init session without auth validation
        init_session = await connection_init_session.get_by_state_no_auth(db, state=state)
        if not init_session:
            raise HTTPException(status_code=404, detail="OAuth session not found or expired")

        # Reconstruct ApiContext from session data
        ctx = await self._reconstruct_context_from_session(db, init_session)

        # Now call the regular complete_oauth_callback with the reconstructed context
        return await self.complete_oauth_callback(db, state=state, code=code, ctx=ctx)

    async def complete_oauth_callback(
        self,
        db: AsyncSession,
        *,
        state: str,
        code: str,
        ctx: ApiContext,
    ) -> schemas.SourceConnection:
        """Complete OAuth flow from callback.

        Returns:
            Source connection
        """
        # Find init session
        init_session = await connection_init_session.get_by_state(db, state=state, ctx=ctx)
        if not init_session:
            raise HTTPException(status_code=404, detail="OAuth session not found or expired")

        if init_session.status != ConnectionInitStatus.PENDING:
            raise HTTPException(
                status_code=400, detail=f"OAuth session already {init_session.status}"
            )

        # Find shell source connection
        source_conn_shell = await crud.source_connection.get_by_query_and_org(
            db, ctx=ctx, connection_init_session_id=init_session.id
        )
        if not source_conn_shell:
            raise HTTPException(status_code=404, detail="Source connection shell not found")

        # Exchange code for token
        token_response = await self._exchange_oauth_code(
            db, init_session.short_name, code, init_session.overrides, ctx
        )

        # Validate token
        await self._validate_oauth_token(
            db,
            await crud.source.get_by_short_name(db, short_name=init_session.short_name),
            token_response.access_token,
            ctx,
        )

        # Complete the connection
        source_conn = await self._complete_oauth_connection(
            db, source_conn_shell, init_session, token_response, ctx
        )

        # Build the proper response model with redirect URL
        source_conn_response = await self._build_source_connection_response(db, source_conn, ctx)

        # Trigger Temporal workflow if a sync was created with run_immediately
        # The OAuth callback always sets run_immediately=True
        if source_conn.sync_id:
            # Get the sync and check if a job was created
            sync = await crud.sync.get(db, id=source_conn.sync_id, ctx=ctx)
            if sync:
                # Get the latest sync job
                jobs = await crud.sync_job.get_all_by_sync_id(db, sync_id=sync.id)
                if jobs and len(jobs) > 0:
                    # Get the most recent job (first in list)
                    sync_job = jobs[0]
                    # Only trigger if the job is pending (not already running)
                    if sync_job.status == SyncJobStatus.PENDING:
                        # Get collection for the workflow
                        collection = await crud.collection.get_by_readable_id(
                            db, readable_id=source_conn.readable_collection_id, ctx=ctx
                        )
                        if collection:
                            collection_schema = schemas.Collection.model_validate(
                                collection, from_attributes=True
                            )
                            sync_job_schema = schemas.SyncJob.model_validate(
                                sync_job, from_attributes=True
                            )
                            sync_schema = schemas.Sync.model_validate(sync, from_attributes=True)
                            await self._trigger_temporal_workflow(
                                db,
                                sync_schema,
                                sync_job_schema,
                                collection_schema,
                                source_conn_response,
                                ctx,
                            )

        return source_conn_response

    async def make_continuous(
        self,
        db: AsyncSession,
        *,
        id: UUID,
        cursor_field: Optional[str],
        ctx: ApiContext,
    ) -> schemas.SourceConnection:
        """Convert source connection to continuous sync mode."""
        source_conn = await crud.source_connection.get(db, id=id, ctx=ctx)
        if not source_conn:
            raise HTTPException(status_code=404, detail="Source connection not found")

        # Validate source supports incremental
        source = await crud.source.get_by_short_name(db, short_name=source_conn.short_name)
        if not source._supports_incremental:
            raise HTTPException(
                status_code=400,
                detail=f"Source {source.short_name} does not support incremental sync",
            )

        # Update sync to continuous mode
        if source_conn.sync_id:
            async with UnitOfWork(db) as uow:
                sync = await crud.sync.get(uow.session, id=source_conn.sync_id, ctx=ctx)
                if sync:
                    sync_update = schemas.SyncUpdate(
                        is_continuous=True,
                        cursor_field=cursor_field or source._default_cursor_field,
                    )
                    await crud.sync.update(
                        uow.session, db_obj=sync, obj_in=sync_update, ctx=ctx, uow=uow
                    )
            await uow.commit()

        return await self.get(db, id=id, ctx=ctx)

    # ===========================
    # Private Creation Handlers
    # ===========================

    async def _create_with_direct_auth(
        self,
        db: AsyncSession,
        obj_in: schemas.SourceConnectionCreate,
        ctx: ApiContext,
    ) -> schemas.SourceConnection:
        """Create connection with direct authentication credentials."""
        # Validate source and auth fields
        source = await self._get_and_validate_source(db, obj_in.short_name)
        validated_auth = await self._validate_auth_fields(
            db, obj_in.short_name, obj_in.auth_fields, ctx
        )
        validated_config = await self._validate_config_fields(
            db, obj_in.short_name, obj_in.config_fields, ctx
        )

        # Validate credentials with source
        await self._validate_direct_auth(db, source, validated_auth, ctx)

        async with UnitOfWork(db) as uow:
            # Get collection first
            collection = await self._get_collection(uow.session, obj_in.collection, ctx)

            # Create credential
            credential = await self._create_integration_credential(
                uow.session, source, validated_auth, ctx, uow, AuthenticationMethod.DIRECT
            )
            await uow.session.flush()

            # Create connection
            connection = await self._create_connection(
                uow.session, obj_in.name, source, credential.id, ctx, uow
            )
            await uow.session.flush()

            # Create sync
            sync, sync_job = await self._create_sync(
                uow.session,
                obj_in.name,
                connection.id,
                collection.id,
                obj_in.cron_schedule,
                obj_in.sync_immediately,
                ctx,
                uow,
            )
            await uow.session.flush()

            # Create source connection
            source_conn = await self._create_source_connection(
                uow.session,
                obj_in,
                connection.id,
                collection.readable_id,
                sync.id,
                validated_config,
                is_authenticated=True,
                ctx=ctx,
                uow=uow,
            )

            sync_job_schema = schemas.SyncJob.model_validate(sync_job, from_attributes=True)
            collection_schema = schemas.Collection.model_validate(collection, from_attributes=True)
            sync_schema = schemas.Sync.model_validate(sync, from_attributes=True)

            await uow.commit()
            await uow.session.refresh(source_conn)

            # Build complete response object
            source_conn_schema = await self._build_source_connection_response(
                uow.session, source_conn, ctx
            )

        # If we created a sync job, trigger Temporal workflow
        if sync_job and obj_in.sync_immediately:
            await self._trigger_temporal_workflow(
                db, sync_schema, sync_job_schema, collection_schema, source_conn_schema, ctx
            )

        return source_conn_schema

    async def _create_with_oauth_browser(
        self,
        db: AsyncSession,
        obj_in: schemas.SourceConnectionCreate,
        ctx: ApiContext,
    ) -> schemas.SourceConnection:
        """Create shell connection and start OAuth browser flow."""
        source = await self._get_and_validate_source(db, obj_in.short_name)

        # 🔧 Normalize/validate config to a plain dict so we can store it as JSON
        normalized_config = await self._validate_config_fields(
            db, obj_in.short_name, obj_in.config_fields, ctx
        )

        # Generate OAuth URL
        oauth_settings = await integration_settings.get_by_short_name(source.short_name)
        if not oauth_settings:
            raise HTTPException(
                status_code=400, detail=f"OAuth not configured for source: {source.short_name}"
            )

        import secrets

        state = secrets.token_urlsafe(24)
        api_callback = f"{core_settings.api_url}/source-connections/callback"

        provider_auth_url = await oauth2_service.generate_auth_url_with_redirect(
            oauth_settings,
            redirect_uri=api_callback,
            client_id=obj_in.client_id or None,
            state=state,
        )

        async with UnitOfWork(db) as uow:
            # Get or validate collection first (required even for shell

            # Create shell source connection with collection
            source_conn = await self._create_source_connection(
                uow.session,
                obj_in,
                connection_id=None,
                collection_id=obj_in.collection,
                sync_id=None,
                config_fields=normalized_config,
                is_authenticated=False,
                ctx=ctx,
                uow=uow,
            )

            # Create init session
            init_session = await self._create_init_session(uow.session, obj_in, state, ctx, uow)

            # Link them
            source_conn.connection_init_session_id = init_session.id
            uow.session.add(source_conn)

            # Generate proxy URL BEFORE committing
            proxy_url, proxy_expiry = await self._create_proxy_url(
                uow.session, provider_auth_url, ctx, uow
            )

            # Add auth URL to response
            source_conn.authentication_url = proxy_url
            source_conn.authentication_url_expiry = proxy_expiry

            # Commit the transaction
            await uow.commit()

            # Refresh the object to ensure it's attached to the session
            await uow.session.refresh(source_conn)

            # Build complete response object AFTER commit and refresh with redirect URL
            response = await self._build_source_connection_response(uow.session, source_conn, ctx)

        return response

    async def _create_with_oauth_token(
        self,
        db: AsyncSession,
        obj_in: schemas.SourceConnectionCreate,
        ctx: ApiContext,
    ) -> schemas.SourceConnection:
        """Create connection with injected OAuth token."""
        source = await self._get_and_validate_source(db, obj_in.short_name)

        # Build OAuth credentials
        oauth_creds = {
            "access_token": obj_in.access_token,
            "refresh_token": obj_in.refresh_token,
            "token_type": "Bearer",
        }
        if obj_in.token_expires_at:
            oauth_creds["expires_at"] = obj_in.token_expires_at.isoformat()

        # Validate token
        await self._validate_oauth_token(db, source, obj_in.access_token, ctx)

        # Validate config fields
        validated_config = await self._validate_config_fields(
            db, obj_in.short_name, obj_in.config_fields, ctx
        )

        # Create connection similar to direct auth but with OAuth credentials
        async with UnitOfWork(db) as uow:
            # Get collection first
            collection = await self._get_collection(uow.session, obj_in.collection, ctx)

            # Create integration credential with OAuth tokens
            credential = await self._create_integration_credential(
                uow.session, source, oauth_creds, ctx, uow, AuthenticationMethod.OAUTH_TOKEN
            )
            await uow.session.flush()

            # Create connection
            connection = await self._create_connection(
                uow.session, obj_in.name, source, credential.id, ctx, uow
            )
            await uow.session.flush()

            # Create sync
            sync, sync_job = await self._create_sync(
                uow.session,
                obj_in.name,
                connection.id,
                collection.id,
                obj_in.cron_schedule,
                obj_in.sync_immediately,
                ctx,
                uow,
            )
            await uow.session.flush()

            # Create source connection
            source_conn = await self._create_source_connection(
                uow.session,
                obj_in,
                connection.id,
                collection.readable_id,
                sync.id,
                validated_config,
                is_authenticated=True,
                ctx=ctx,
                uow=uow,
            )

            await uow.commit()
            await uow.session.refresh(source_conn)

            # Build complete response object
            source_conn_schema = await self._build_source_connection_response(
                uow.session, source_conn, ctx
            )

        # If we created a sync job, trigger Temporal workflow
        if sync_job and obj_in.sync_immediately:
            collection_schema = schemas.Collection.model_validate(collection, from_attributes=True)
            sync_schema = schemas.Sync.model_validate(sync, from_attributes=True)
            sync_job_schema = schemas.SyncJob.model_validate(sync_job, from_attributes=True)
            await self._trigger_temporal_workflow(
                db, sync_schema, sync_job_schema, collection_schema, source_conn_schema, ctx
            )

        return source_conn_schema

    async def _create_with_oauth_byoc(
        self,
        db: AsyncSession,
        obj_in: schemas.SourceConnectionCreate,
        ctx: ApiContext,
    ) -> schemas.SourceConnection:
        """Create connection with bring-your-own-client OAuth."""
        # Start OAuth flow with custom client credentials
        # Store client_id/secret in overrides for callback
        await self._get_and_validate_source(db, obj_in.short_name)

        # Similar to browser flow but with custom client
        # Implementation follows browser pattern with client overrides
        raise NotImplementedError("BYOC OAuth implementation pending")

    async def _create_with_auth_provider(
        self,
        db: AsyncSession,
        obj_in: schemas.SourceConnectionCreate,
        ctx: ApiContext,
    ) -> schemas.SourceConnection:
        """Create connection using external auth provider."""
        source = await self._get_and_validate_source(db, obj_in.short_name)

        # Validate auth provider
        auth_provider_conn = await crud.connection.get_by_readable_id(
            db, readable_id=obj_in.auth_provider, ctx=ctx
        )
        if not auth_provider_conn:
            raise HTTPException(
                status_code=404, detail=f"Auth provider '{obj_in.auth_provider}' not found"
            )

        # Validate auth provider config
        validated_auth_config = await auth_provider_service.validate_auth_provider_config(
            db, auth_provider_conn.short_name, obj_in.auth_provider_config
        )

        # Validate config fields
        validated_config = await self._validate_config_fields(
            db, obj_in.short_name, obj_in.config_fields, ctx
        )

        # Create connection with auth provider reference
        async with UnitOfWork(db) as uow:
            # Get collection first
            collection = await self._get_collection(uow.session, obj_in.collection, ctx)

            # Create connection (no credential needed - auth provider handles it)
            connection = await self._create_connection(
                uow.session, obj_in.name, source, None, ctx, uow
            )
            await uow.session.flush()

            # Create sync
            sync, sync_job = await self._create_sync(
                uow.session,
                obj_in.name,
                connection.id,
                collection.id,
                obj_in.cron_schedule,
                obj_in.sync_immediately,
                ctx,
                uow,
            )
            await uow.session.flush()

            # Create source connection
            source_conn = await self._create_source_connection(
                uow.session,
                obj_in,
                connection.id,
                collection.readable_id,
                sync.id,
                validated_config,
                is_authenticated=True,
                ctx=ctx,
                uow=uow,
                auth_provider_id=obj_in.auth_provider,
                auth_provider_config=validated_auth_config,
            )

            collection_schema = schemas.Collection.model_validate(collection, from_attributes=True)
            sync_schema = schemas.Sync.model_validate(sync, from_attributes=True)
            sync_job_schema = schemas.SyncJob.model_validate(sync_job, from_attributes=True)

            await uow.commit()
            await uow.session.refresh(source_conn)

            # Build complete response object
            source_conn_schema = await self._build_source_connection_response(
                uow.session, source_conn, ctx
            )

        # If we created a sync job, trigger Temporal workflow
        if sync_job and obj_in.sync_immediately:
            await self._trigger_temporal_workflow(
                db, sync_schema, sync_job_schema, collection_schema, source_conn_schema, ctx
            )

        return source_conn_schema

    # ===========================
    # Helper Methods
    # ===========================

    async def _trigger_temporal_workflow(
        self,
        db: AsyncSession,
        sync: schemas.Sync,
        sync_job: schemas.SyncJob,
        collection: schemas.Collection,
        source_conn: schemas.SourceConnection,
        ctx: ApiContext,
    ) -> None:
        """Trigger Temporal workflow for a sync job."""
        # Get the sync DAG
        sync_dag = await crud.sync_dag.get_by_sync_id(db, sync_id=sync.id, ctx=ctx)
        if not sync_dag:
            ctx.logger.error(f"Sync DAG not found for sync {sync.id}, cannot trigger workflow")
            return

        # Convert DAG to schema
        sync_dag_schema = schemas.SyncDag.model_validate(sync_dag, from_attributes=True)

        # Trigger Temporal workflow
        await temporal_service.run_source_connection_workflow(
            sync=sync,
            sync_job=sync_job,
            sync_dag=sync_dag_schema,
            collection=collection,
            source_connection=source_conn,
            ctx=ctx,
        )

    async def _get_and_validate_source(self, db: AsyncSession, short_name: str) -> Any:
        """Get and validate a source exists."""
        source = await crud.source.get_by_short_name(db, short_name=short_name)
        if not source:
            raise HTTPException(status_code=404, detail=f"Source '{short_name}' not found")
        return source

    def _get_source_class(self, class_name: str) -> Any:
        """Get source class by name."""
        # Import the source module dynamically
        module_name = class_name.replace("Source", "").lower()

        # Handle google* and outlook* cases - add underscore if there's additional text
        if module_name.startswith("google") and len(module_name) > 6:
            module_name = "google_" + module_name[6:]
        elif module_name.startswith("outlook") and len(module_name) > 7:
            module_name = "outlook_" + module_name[7:]

        module = __import__(f"airweave.platform.sources.{module_name}", fromlist=[class_name])
        return getattr(module, class_name)

    # Import helper instance and all helper methods
    from airweave.core.source_connection_service_helpers import source_connection_helpers

    _validate_authentication_method = source_connection_helpers.validate_authentication_method
    _validate_auth_fields = source_connection_helpers.validate_auth_fields
    _validate_config_fields = source_connection_helpers.validate_config_fields
    _validate_direct_auth = source_connection_helpers.validate_direct_auth
    _validate_oauth_token = source_connection_helpers.validate_oauth_token
    _create_integration_credential = source_connection_helpers.create_integration_credential
    _create_connection = source_connection_helpers.create_connection
    _get_collection = source_connection_helpers.get_collection
    _create_sync = source_connection_helpers.create_sync
    _create_source_connection = source_connection_helpers.create_source_connection
    _build_source_connection_response = source_connection_helpers.build_source_connection_response
    _bulk_fetch_last_sync_info = source_connection_helpers.bulk_fetch_last_sync_info
    _bulk_fetch_entity_counts = source_connection_helpers.bulk_fetch_entity_counts
    _update_sync_schedule = source_connection_helpers.update_sync_schedule
    _update_auth_fields = source_connection_helpers.update_auth_fields
    _cleanup_destination_data = source_connection_helpers.cleanup_destination_data
    _cleanup_temporal_schedules = source_connection_helpers.cleanup_temporal_schedules
    _sync_job_to_source_connection_job = source_connection_helpers.sync_job_to_source_connection_job
    _create_init_session = source_connection_helpers.create_init_session
    _create_proxy_url = source_connection_helpers.create_proxy_url
    _exchange_oauth_code = source_connection_helpers.exchange_oauth_code
    _complete_oauth_connection = source_connection_helpers.complete_oauth_connection
    _reconstruct_context_from_session = source_connection_helpers.reconstruct_context_from_session


# Singleton instance
source_connection_service = SourceConnectionService()
