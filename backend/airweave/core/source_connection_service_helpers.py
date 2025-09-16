"""Helper methods for source connection service v2."""

from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from airweave import crud, schemas
from airweave.api.context import ApiContext
from airweave.core import credentials
from airweave.core.config import settings as core_settings
from airweave.core.constants.reserved_ids import NATIVE_QDRANT_UUID, NATIVE_TEXT2VEC_UUID
from airweave.core.shared_models import (
    ConnectionStatus,
    SourceConnectionStatus,
    SyncJobStatus,
    SyncStatus,
)
from airweave.crud import connection_init_session, redirect_session
from airweave.db.unit_of_work import UnitOfWork
from airweave.models.connection_init_session import ConnectionInitStatus
from airweave.models.integration_credential import IntegrationType
from airweave.models.sync import Sync
from airweave.models.sync_job import SyncJob
from airweave.platform.auth.services import oauth2_service
from airweave.platform.configs.auth import AuthConfig
from airweave.platform.locator import resource_locator
from airweave.platform.temporal.schedule_service import temporal_schedule_service
from airweave.schemas.source_connection import (
    AuthenticationMethod,
    SourceConnectionCreate,
    SourceConnectionJob,
)


class SourceConnectionHelpers:
    """Helper methods for source connection service."""

    def validate_authentication_method(  # noqa: C901
        self, source_class: Any, obj_in: SourceConnectionCreate
    ) -> None:
        """Validate authentication method and required fields.

        Args:
            source_class: The source class with auth metadata
            obj_in: The source connection creation request

        Raises:
            HTTPException: If validation fails
        """
        # Check if auth method is supported
        if not source_class.supports_auth_method(obj_in.authentication_method):
            supported = source_class.get_supported_auth_methods()
            raise HTTPException(
                status_code=400,
                detail=f"Source {obj_in.short_name} does not support "
                f"{obj_in.authentication_method}. "
                f"Supported methods: {[m.value for m in supported]}",
            )

        # Validate OAuth-specific requirements
        if obj_in.authentication_method in [
            AuthenticationMethod.OAUTH_BROWSER,
            AuthenticationMethod.OAUTH_TOKEN,
        ]:
            # Check if source requires BYOC (Bring Your Own Credentials)
            if source_class.requires_byoc():
                # BYOC sources REQUIRE client credentials
                if not obj_in.client_id or not obj_in.client_secret:
                    raise HTTPException(
                        status_code=400,
                        detail=(
                            f"Source {obj_in.short_name} requires you to provide your own "
                            "OAuth application credentials (client_id and client_secret)"
                        ),
                    )
            else:
                # For non-BYOC OAuth sources, client credentials are optional
                # But if one is provided, both must be provided
                if obj_in.client_id or obj_in.client_secret:
                    if not (obj_in.client_id and obj_in.client_secret):
                        raise HTTPException(
                            status_code=400,
                            detail=(
                                "If providing custom OAuth credentials, both client_id "
                                "and client_secret are required"
                            ),
                        )

        # Validate DIRECT auth has required fields
        elif obj_in.authentication_method == AuthenticationMethod.DIRECT:
            if not obj_in.auth_fields:
                raise HTTPException(
                    status_code=400,
                    detail="Direct authentication requires auth_fields",
                )

        # Validate AUTH_PROVIDER has required fields
        elif obj_in.authentication_method == AuthenticationMethod.AUTH_PROVIDER:
            if not obj_in.auth_provider:
                raise HTTPException(
                    status_code=400,
                    detail="Auth provider authentication requires auth_provider ID",
                )

    async def validate_auth_fields(
        self, db: AsyncSession, short_name: str, auth_fields: Any, ctx: ApiContext
    ) -> AuthConfig:
        """Validate authentication fields against source schema."""
        source = await crud.source.get_by_short_name(db, short_name=short_name)
        if not source:
            raise HTTPException(status_code=404, detail=f"Source '{short_name}' not found")

        if not source.auth_config_class:
            raise HTTPException(
                status_code=422, detail=f"Source {source.name} does not support direct auth"
            )

        try:
            auth_config_class = resource_locator.get_auth_config(source.auth_config_class)
            auth_config = auth_config_class(**auth_fields.model_dump())
            return auth_config
        except Exception as e:
            from pydantic import ValidationError

            if isinstance(e, ValidationError):
                errors = "; ".join([f"{err['loc'][0]}: {err['msg']}" for err in e.errors()])
                raise HTTPException(status_code=422, detail=f"Invalid auth fields: {errors}") from e
            raise HTTPException(status_code=422, detail=str(e)) from e

    async def validate_config_fields(
        self, db: AsyncSession, short_name: str, config_fields: Any, ctx: ApiContext
    ) -> Dict[str, Any]:
        """Validate configuration fields against source schema."""
        source = await crud.source.get_by_short_name(db, short_name=short_name)
        if not source:
            raise HTTPException(status_code=404, detail=f"Source '{short_name}' not found")

        if not config_fields:
            return {}

        if not source.config_class:
            return config_fields if isinstance(config_fields, dict) else {}

        try:
            config_class = resource_locator.get_config(source.config_class)
            config = config_class(**config_fields)
            return config.model_dump()
        except Exception as e:
            from pydantic import ValidationError

            if isinstance(e, ValidationError):
                errors = "; ".join([f"{err['loc'][0]}: {err['msg']}" for err in e.errors()])
                raise HTTPException(
                    status_code=422, detail=f"Invalid config fields: {errors}"
                ) from e
            raise HTTPException(status_code=422, detail=str(e)) from e

    async def validate_direct_auth(
        self, db: AsyncSession, source: Any, auth_fields: AuthConfig, ctx: ApiContext
    ) -> Dict[str, Any]:
        """Validate direct authentication credentials."""
        try:
            source_cls = resource_locator.get_source(source)
            source_instance = await source_cls.create(auth_fields, config=None)
            source_instance.set_logger(ctx.logger)

            if hasattr(source_instance, "validate"):
                is_valid = await source_instance.validate()
                if not is_valid:
                    raise HTTPException(
                        status_code=400, detail="Authentication credentials are invalid"
                    )
            else:
                raise HTTPException(
                    status_code=400, detail=f"No validate method found for {source.short_name}"
                )
            return {"valid": True, "source": source.short_name}
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Validation failed: {str(e)}") from e

    async def validate_oauth_token(
        self, db: AsyncSession, source: Any, access_token: str, ctx: ApiContext
    ) -> Dict[str, Any]:
        """Validate OAuth access token."""
        try:
            source_cls = resource_locator.get_source(source)
            source_instance = await source_cls.create(access_token=access_token, config=None)
            source_instance.set_logger(ctx.logger)

            if hasattr(source_instance, "validate"):
                is_valid = await source_instance.validate()
                if not is_valid:
                    raise HTTPException(status_code=400, detail="OAuth token is invalid")
            return {"valid": True, "source": source.short_name}
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Token validation failed: {str(e)}") from e

    async def create_integration_credential(
        self,
        db: AsyncSession,
        source: Any,
        auth_fields: Dict[str, Any],
        ctx: ApiContext,
        uow: Any,
        auth_method: AuthenticationMethod = AuthenticationMethod.DIRECT,
    ) -> Any:
        """Create integration credential.

        Args:
            db: Database session
            source: Source model object
            auth_fields: Authentication fields to encrypt
            ctx: API context
            uow: Unit of work
            auth_method: Authentication method being used
        """
        # Convert Pydantic model to dict if necessary
        if hasattr(auth_fields, "model_dump"):
            auth_fields_dict = auth_fields.model_dump()
        else:
            auth_fields_dict = auth_fields

        encrypted = credentials.encrypt(auth_fields_dict)

        # Get OAuth type from source if it's an OAuth method
        oauth_type = None
        if auth_method in [
            AuthenticationMethod.OAUTH_BROWSER,
            AuthenticationMethod.OAUTH_TOKEN,
            AuthenticationMethod.OAUTH_BYOC,
        ]:
            oauth_type = getattr(source, "oauth_type", None)

        cred_in = schemas.IntegrationCredentialCreateEncrypted(
            name=f"{source.name} - {ctx.organization.id}",
            description=f"Credentials for {source.name}",
            integration_short_name=source.short_name,
            integration_type=IntegrationType.SOURCE,
            authentication_method=auth_method,
            oauth_type=oauth_type,
            encrypted_credentials=encrypted,
            auth_config_class=source.auth_config_class,
        )
        return await crud.integration_credential.create(db, obj_in=cred_in, ctx=ctx, uow=uow)

    async def create_connection(
        self,
        db: AsyncSession,
        name: str,
        source: Any,
        credential_id: Optional[UUID],
        ctx: ApiContext,
        uow: Any,
    ) -> Any:
        """Create connection."""
        conn_in = schemas.ConnectionCreate(
            name=name,
            integration_type=IntegrationType.SOURCE,
            integration_credential_id=credential_id,
            status=ConnectionStatus.ACTIVE,
            short_name=source.short_name,
        )
        return await crud.connection.create(db, obj_in=conn_in, ctx=ctx, uow=uow)

    async def get_collection(self, db: AsyncSession, collection_id: str, ctx: ApiContext) -> Any:
        """Get or validate collection exists."""
        if not collection_id:
            # This should never happen with proper typing, but kept for safety
            raise HTTPException(status_code=400, detail="Collection is required")

        collection = await crud.collection.get_by_readable_id(
            db, readable_id=collection_id, ctx=ctx
        )
        if not collection:
            raise HTTPException(status_code=404, detail=f"Collection '{collection_id}' not found")
        return collection

    async def create_sync(
        self,
        db: AsyncSession,
        name: str,
        connection_id: UUID,
        collection_id: UUID,
        cron_schedule: Optional[str],
        run_immediately: bool,
        ctx: ApiContext,
        uow: Any,
    ) -> Tuple[Any, Optional[Any]]:
        """Create sync and optionally trigger initial run.

        Connection ID here is the model.connection.id, not the model.source_connection.id
        Collection ID is not used directly by sync, but kept for consistency
        """
        from airweave.core.sync_service import sync_service

        sync_in = schemas.SyncCreate(
            name=f"Sync for {name}",
            description=f"Auto-generated sync for {name}",
            source_connection_id=connection_id,
            embedding_model_connection_id=NATIVE_TEXT2VEC_UUID,
            destination_connection_ids=[NATIVE_QDRANT_UUID],
            cron_schedule=cron_schedule,
            status=SyncStatus.ACTIVE,
            run_immediately=run_immediately,
        )
        return await sync_service.create_and_run_sync(db, sync_in=sync_in, ctx=ctx, uow=uow)

    async def create_source_connection(
        self,
        db: AsyncSession,
        obj_in: SourceConnectionCreate,
        connection_id: Optional[UUID],
        collection_id: str,
        sync_id: Optional[UUID],
        config_fields: Optional[Dict[str, Any]],
        is_authenticated: bool,
        ctx: ApiContext,
        uow: Any,
        auth_provider_id: Optional[str] = None,
        auth_provider_config: Optional[Dict[str, Any]] = None,
    ) -> Any:
        """Create source connection record."""
        sc_data = {
            "name": obj_in.name,
            "description": obj_in.description,
            "short_name": obj_in.short_name,
            "config_fields": config_fields,
            "connection_id": connection_id,
            "readable_collection_id": collection_id,
            "sync_id": sync_id,
            "is_authenticated": is_authenticated,
        }

        if auth_provider_id:
            sc_data["readable_auth_provider_id"] = auth_provider_id
            sc_data["auth_provider_config"] = auth_provider_config

        return await crud.source_connection.create(db, obj_in=sc_data, ctx=ctx, uow=uow)

    def determine_auth_method(self, source_conn: Any) -> Optional[AuthenticationMethod]:
        """Determine authentication method from existing database fields.

        Returns None if authentication method cannot be determined.
        """
        # Check auth provider first (safely)
        auth_provider_id = getattr(source_conn, "readable_auth_provider_id", None)
        if auth_provider_id:
            return AuthenticationMethod.AUTH_PROVIDER

        # Check if OAuth flow is in progress (safely)
        has_init_session = (
            hasattr(source_conn, "connection_init_session_id")
            and source_conn.connection_init_session_id
        )
        is_not_authenticated = not getattr(source_conn, "is_authenticated", False)
        if has_init_session and is_not_authenticated:
            return AuthenticationMethod.OAUTH_BROWSER

        # Check if we have a connection with credentials (safely)
        if hasattr(source_conn, "connection_id") and source_conn.connection_id:
            # Could be direct auth or completed OAuth token
            # We'll default to direct since we can't distinguish without more info
            return AuthenticationMethod.DIRECT

        # If we have authentication but no clear method, default to direct
        if getattr(source_conn, "is_authenticated", False):
            return AuthenticationMethod.DIRECT

        # Cannot determine authentication method
        return None

    def compute_status(self, source_conn: Any) -> SourceConnectionStatus:
        """Compute status from current state."""
        from airweave.core.shared_models import SourceConnectionStatus

        if not source_conn.is_authenticated:
            return SourceConnectionStatus.PENDING_AUTH

        # Check if manually disabled
        if hasattr(source_conn, "is_active") and not source_conn.is_active:
            return SourceConnectionStatus.INACTIVE

        # Check if we have sync job info
        if hasattr(source_conn, "_last_sync_job") and source_conn._last_sync_job:
            job = source_conn._last_sync_job
            if job.status == SyncJobStatus.RUNNING:
                return SourceConnectionStatus.SYNCING
            elif job.status == SyncJobStatus.FAILED:
                return SourceConnectionStatus.ERROR

        return SourceConnectionStatus.ACTIVE

    async def build_source_connection_response(  # noqa: C901
        self,
        db: AsyncSession,
        source_conn: schemas.SourceConnection,
        ctx: ApiContext,
    ) -> schemas.SourceConnection:
        """Build complete source connection response object.

        This method owns the logic of constructing the response,
        always including all available data while handling missing fields gracefully.

        Args:
            db: Database session
            source_conn: Source connection object
            ctx: API context
        """
        from airweave.core.sync_service import sync_service

        # Determine authentication method from database state
        auth_method = self.determine_auth_method(source_conn)

        # Base fields (always present)
        response = {
            "id": source_conn.id,
            "name": source_conn.name,
            "description": source_conn.description,
            "short_name": source_conn.short_name,
            "collection": source_conn.readable_collection_id,
            "created_at": source_conn.created_at,
            "modified_at": source_conn.modified_at,
            "is_authenticated": source_conn.is_authenticated,
            "auth_method": auth_method,
        }

        # Config fields (safely check for presence and non-None)
        if hasattr(source_conn, "config_fields") and source_conn.config_fields:
            response["config_fields"] = source_conn.config_fields

        # Schedule info and last sync job (only if sync_id exists)
        if hasattr(source_conn, "sync_id") and source_conn.sync_id:
            try:
                # Get schedule info - handle potential None return
                schedule_info = await crud.source_connection.get_schedule_info(db, source_conn)
                if schedule_info:
                    response["schedule"] = schedule_info
            except Exception as e:
                ctx.logger.warning(f"Failed to get schedule info: {e}")

            try:
                # Get last sync job
                job = await sync_service.get_last_sync_job(db, ctx=ctx, sync_id=source_conn.sync_id)
                if job:
                    # Build LastSyncJob object with safe attribute access
                    last_sync_job_data = {
                        "id": job.id,
                        "status": job.status,
                        "started_at": getattr(job, "started_at", None),
                        "completed_at": getattr(job, "completed_at", None),
                    }

                    # Calculate duration safely
                    if last_sync_job_data["completed_at"] and last_sync_job_data["started_at"]:
                        last_sync_job_data["duration_seconds"] = (
                            last_sync_job_data["completed_at"] - last_sync_job_data["started_at"]
                        ).total_seconds()

                    # Add entity metrics - compute total processed from available fields
                    entities_inserted = getattr(job, "entities_inserted", 0) or 0
                    entities_updated = getattr(job, "entities_updated", 0) or 0
                    entities_deleted = getattr(job, "entities_deleted", 0) or 0
                    entities_kept = getattr(job, "entities_kept", 0) or 0
                    entities_skipped = getattr(job, "entities_skipped", 0) or 0

                    # Calculate total processed and failed
                    entities_processed = (
                        entities_inserted + entities_updated + entities_deleted + entities_kept
                    )
                    # Note: SyncJob doesn't have entities_failed, so we use skipped as a proxy
                    entities_failed = entities_skipped

                    last_sync_job_data.update(
                        {
                            "entities_processed": entities_processed,
                            "entities_inserted": entities_inserted,
                            "entities_updated": entities_updated,
                            "entities_deleted": entities_deleted,
                            "entities_failed": entities_failed,
                            "error": getattr(job, "error", None),
                        }
                    )

                    # Create the LastSyncJob schema object
                    response["last_sync_job"] = schemas.LastSyncJob(**last_sync_job_data)

            except Exception as e:
                ctx.logger.warning(f"Failed to get last sync job: {e}")

        # Compute status based on authentication and last sync job
        last_job_status = None
        if "last_sync_job" in response and response["last_sync_job"]:
            last_job_status = response["last_sync_job"].status

        response["status"] = self.compute_status_from_data(
            is_authenticated=source_conn.is_authenticated,
            is_active=getattr(source_conn, "is_active", True),
            last_job_status=last_job_status,
        )

        # Authentication details (build safely)
        auth_info = {
            "method": auth_method,
            "is_authenticated": source_conn.is_authenticated,
        }

        # Add optional authentication fields if they exist
        if hasattr(source_conn, "created_at"):
            auth_info["authenticated_at"] = source_conn.created_at

        auth_provider_id = getattr(source_conn, "readable_auth_provider_id", None)
        if auth_provider_id:
            auth_info["auth_provider_id"] = auth_provider_id

        # Add OAuth-specific fields if pending
        if hasattr(source_conn, "authentication_url") and source_conn.authentication_url:
            auth_info["authentication_url"] = source_conn.authentication_url
            if hasattr(source_conn, "authentication_url_expiry"):
                auth_info["authentication_url_expiry"] = source_conn.authentication_url_expiry

        # Add redirect URL from connection init session if available
        if (
            hasattr(source_conn, "connection_init_session_id")
            and source_conn.connection_init_session_id
        ):
            # Load the connection init session to get the redirect URL
            init_session = await connection_init_session.get(
                db, id=source_conn.connection_init_session_id, ctx=ctx
            )
            if init_session and init_session.overrides:
                redirect_url = init_session.overrides.get("redirect_url")
                if redirect_url:
                    auth_info["redirect_url"] = redirect_url

        response["authentication"] = schemas.AuthenticationInfo(**auth_info)

        # Entity states - get counts per entity type
        if hasattr(source_conn, "sync_id") and source_conn.sync_id:
            try:
                # Get entity counts per type
                entity_counts = await crud.entity_count.get_counts_per_sync_and_type(
                    db, source_conn.sync_id
                )

                # Convert to EntityState objects
                if entity_counts:
                    entity_states = []
                    for count_data in entity_counts:
                        entity_state = schemas.EntityState(
                            entity_type=count_data.entity_definition_name,
                            total_count=count_data.count,
                            last_updated_at=source_conn.modified_at,
                            sync_status="synced" if source_conn.is_authenticated else "pending",
                        )
                        entity_states.append(entity_state)

                    response["entity_states"] = entity_states
            except Exception as e:
                ctx.logger.warning(f"Failed to get entity states: {e}")

        # Return constructed Pydantic object
        return schemas.SourceConnection(**response)

    def compute_status_from_data(
        self,
        is_authenticated: bool,
        is_active: bool = True,
        last_job_status: Optional[SyncJobStatus] = None,
    ) -> SourceConnectionStatus:
        """Compute status from provided data without accessing ORM object."""
        from airweave.core.shared_models import SourceConnectionStatus

        if not is_authenticated:
            return SourceConnectionStatus.PENDING_AUTH

        # Check if manually disabled
        if not is_active:
            return SourceConnectionStatus.INACTIVE

        # Check last job status
        if last_job_status:
            if last_job_status == SyncJobStatus.RUNNING:
                return SourceConnectionStatus.SYNCING
            elif last_job_status == SyncJobStatus.FAILED:
                return SourceConnectionStatus.ERROR

        return SourceConnectionStatus.ACTIVE

    async def bulk_fetch_last_sync_info(
        self, db: AsyncSession, sync_ids: List[UUID], ctx: ApiContext
    ) -> Dict[UUID, Dict[str, Any]]:
        """Bulk fetch last sync information including job status."""
        # Get last sync jobs with their status
        subq = (
            select(
                SyncJob.sync_id,
                SyncJob.status,
                SyncJob.completed_at,
                func.row_number()
                .over(partition_by=SyncJob.sync_id, order_by=SyncJob.created_at.desc())
                .label("rn"),
            )
            .where(SyncJob.sync_id.in_(sync_ids))
            .subquery()
        )

        query = select(subq).where(subq.c.rn == 1)
        result = await db.execute(query)

        # Get next scheduled runs
        syncs = await db.execute(select(Sync).where(Sync.id.in_(sync_ids)))
        sync_schedules = {s.id: s.next_scheduled_run for s in syncs.scalars()}

        return {
            row.sync_id: {
                "last_sync_at": row.completed_at,
                "next_sync_at": sync_schedules.get(row.sync_id),
                "last_job_status": row.status,
            }
            for row in result
        }

    async def bulk_fetch_entity_counts(
        self, db: AsyncSession, sync_ids: List[UUID], ctx: ApiContext
    ) -> Dict[UUID, int]:
        """Bulk fetch total entity counts from EntityCount table."""
        from airweave.models.entity_count import EntityCount

        query = (
            select(EntityCount.sync_id, func.sum(EntityCount.count).label("total_count"))
            .where(EntityCount.sync_id.in_(sync_ids))
            .group_by(EntityCount.sync_id)
        )
        result = await db.execute(query)
        return {row.sync_id: row.total_count or 0 for row in result}

    async def update_sync_schedule(
        self, db: AsyncSession, sync_id: UUID, cron_schedule: str, ctx: ApiContext, uow: Any
    ) -> None:
        """Update sync schedule."""
        sync = await crud.sync.get(db, id=sync_id, ctx=ctx)
        if sync:
            sync_update = schemas.SyncUpdate(cron_schedule=cron_schedule)
            await crud.sync.update(db, db_obj=sync, obj_in=sync_update, ctx=ctx, uow=uow)

    async def update_auth_fields(
        self, db: AsyncSession, source_conn: Any, auth_fields: Any, ctx: ApiContext, uow: Any
    ) -> None:
        """Update authentication fields."""
        validated_auth = await self.validate_auth_fields(
            db, source_conn.short_name, auth_fields, ctx
        )

        connection = await crud.connection.get(db, id=source_conn.connection_id, ctx=ctx)
        if connection and connection.integration_credential_id:
            credential = await crud.integration_credential.get(
                db, id=connection.integration_credential_id, ctx=ctx
            )
            if credential:
                credential_update = schemas.IntegrationCredentialUpdate(
                    encrypted_credentials=credentials.encrypt(validated_auth)
                )
                await crud.integration_credential.update(
                    db, db_obj=credential, obj_in=credential_update, ctx=ctx, uow=uow
                )

    async def cleanup_destination_data(
        self, db: AsyncSession, source_conn: Any, ctx: ApiContext
    ) -> None:
        """Clean up data in destinations."""
        try:
            collection = await crud.collection.get_by_readable_id(
                db, readable_id=source_conn.readable_collection_id, ctx=ctx
            )
            if collection:
                from airweave.platform.destinations.qdrant import QdrantDestination

                destination = await QdrantDestination.create(collection_id=collection.id)
                await destination.delete_by_sync_id(source_conn.sync_id)
                ctx.logger.info(f"Deleted data for sync {source_conn.sync_id}")
        except Exception as e:
            ctx.logger.error(f"Error cleaning up destination data: {e}")

    async def cleanup_temporal_schedules(
        self, sync_id: UUID, db: AsyncSession, ctx: ApiContext
    ) -> None:
        """Clean up Temporal schedules."""
        try:
            await temporal_schedule_service.delete_all_schedules_for_sync(
                sync_id=sync_id, db=db, ctx=ctx
            )
        except Exception as e:
            ctx.logger.error(f"Failed to delete schedules: {e}")

    def sync_job_to_source_connection_job(
        self, job: Any, source_connection_id: UUID
    ) -> SourceConnectionJob:
        """Convert sync job to source connection job."""
        return SourceConnectionJob(
            id=job.id,
            source_connection_id=source_connection_id,
            status=job.status,
            started_at=job.started_at,
            completed_at=job.completed_at,
            duration_seconds=(
                (job.completed_at - job.started_at).total_seconds()
                if job.completed_at and job.started_at
                else None
            ),
            entities_processed=getattr(job, "entities_processed", 0),
            entities_inserted=getattr(job, "entities_inserted", 0),
            entities_updated=getattr(job, "entities_updated", 0),
            entities_deleted=getattr(job, "entities_deleted", 0),
            entities_failed=getattr(job, "entities_failed", 0),
            error=job.error if hasattr(job, "error") else None,
        )

    async def create_init_session(
        self,
        db: AsyncSession,
        obj_in: SourceConnectionCreate,
        state: str,
        ctx: ApiContext,
        uow: Any,
    ) -> Any:
        """Create connection init session for OAuth flow."""
        payload = obj_in.model_dump(
            exclude={"client_id", "client_secret", "token_inject", "redirect_url", "auth_mode"},
            exclude_none=True,
        )

        overrides = {
            "client_id": obj_in.client_id,
            "client_secret": obj_in.client_secret,
            "redirect_url": obj_in.redirect_url or core_settings.app_url,
            "oauth_redirect_uri": f"{core_settings.api_url}/source-connections/callback",
        }

        expires_at = datetime.now(timezone.utc) + timedelta(minutes=30)

        return await connection_init_session.create(
            db,
            obj_in={
                "organization_id": ctx.organization.id,
                "short_name": obj_in.short_name,
                "payload": payload,
                "overrides": overrides,
                "state": state,
                "status": ConnectionInitStatus.PENDING,
                "expires_at": expires_at,
            },
            ctx=ctx,
            uow=uow,
        )

    async def create_proxy_url(
        self, db: AsyncSession, provider_auth_url: str, ctx: ApiContext, uow: Any = None
    ) -> Tuple[str, datetime]:
        """Create proxy URL for OAuth flow."""
        proxy_ttl = 1440  # 24 hours
        proxy_expires = datetime.now(timezone.utc) + timedelta(minutes=proxy_ttl)
        code8 = await redirect_session.generate_unique_code(db, length=8)

        await redirect_session.create(
            db,
            code=code8,
            final_url=provider_auth_url,
            expires_at=proxy_expires,
            ctx=ctx,
            uow=uow,
        )

        proxy_url = f"{core_settings.api_url}/source-connections/authorize/{code8}"
        return proxy_url, proxy_expires

    async def exchange_oauth_code(
        self,
        db: AsyncSession,
        short_name: str,
        code: str,
        overrides: Dict[str, Any],
        ctx: ApiContext,
    ) -> Any:
        """Exchange OAuth code for token."""
        return await oauth2_service.exchange_authorization_code_for_token_with_redirect(
            ctx=ctx,
            source_short_name=short_name,
            code=code,
            redirect_uri=overrides.get("oauth_redirect_uri"),
            client_id=overrides.get("client_id"),
            client_secret=overrides.get("client_secret"),
        )

    async def _regenerate_oauth_url(
        self,
        db: AsyncSession,
        source_conn: schemas.SourceConnection,
        ctx: ApiContext,
    ) -> Tuple[Optional[str], Optional[datetime]]:
        """Regenerate OAuth authentication URL for an unauthenticated connection.

        Returns:
            Tuple of (auth_url, expiry_datetime) or (None, None) if not applicable
        """
        # Only regenerate for OAuth browser flow connections that are not authenticated
        if source_conn.is_authenticated:
            return None, None

        # Check if this is an OAuth browser flow connection
        if (
            not hasattr(source_conn, "connection_init_session_id")
            or not source_conn.connection_init_session_id
        ):
            return None, None

        # Get the init session to retrieve OAuth settings
        init_session = await connection_init_session.get(
            db, id=source_conn.connection_init_session_id, ctx=ctx
        )
        if not init_session or init_session.status != ConnectionInitStatus.PENDING:
            return None, None

        # Get source to retrieve OAuth settings
        source = await crud.source.get_by_short_name(db, short_name=source_conn.short_name)
        if not source:
            return None, None

        # Generate new OAuth URL

        from airweave.platform.auth.services import oauth2_service
        from airweave.platform.auth.settings import integration_settings

        oauth_settings = await integration_settings.get_by_short_name(source.short_name)
        if not oauth_settings:
            return None, None

        # Use existing state from init session
        state = init_session.state
        api_callback = (
            init_session.overrides.get("oauth_redirect_uri")
            or f"{core_settings.api_url}/source-connections/callback"
        )

        provider_auth_url = await oauth2_service.generate_auth_url_with_redirect(
            oauth_settings,
            redirect_uri=api_callback,
            client_id=init_session.overrides.get("client_id"),
            state=state,
        )

        # Create new proxy URL
        proxy_url, proxy_expiry = await self.create_proxy_url(db, provider_auth_url, ctx)

        return proxy_url, proxy_expiry

    async def complete_oauth_connection(
        self,
        db: AsyncSession,
        source_conn_shell: Any,
        init_session: Any,
        token_response: Any,
        ctx: ApiContext,
    ) -> Any:
        """Complete OAuth connection after callback."""
        source = await crud.source.get_by_short_name(db, short_name=init_session.short_name)
        if not source:
            raise HTTPException(
                status_code=404, detail=f"Source '{init_session.short_name}' not found"
            )

        payload = init_session.payload or {}
        overrides = init_session.overrides or {}

        # Build OAuth credentials from token response
        auth_fields = token_response.model_dump()
        if overrides.get("client_id"):
            auth_fields["client_id"] = overrides["client_id"]
        if overrides.get("client_secret"):
            auth_fields["client_secret"] = overrides["client_secret"]

        # For OAuth, we don't validate against auth_config_class since that's for direct auth
        # The token response is already validated by the OAuth exchange
        validated_auth = auth_fields

        # Validate config fields if provided
        validated_config = await self.validate_config_fields(
            db, init_session.short_name, payload.get("config_fields"), ctx
        )

        async with UnitOfWork(db) as uow:
            # Create credential
            encrypted = credentials.encrypt(validated_auth)
            cred_in = schemas.IntegrationCredentialCreateEncrypted(
                name=f"{source.name} OAuth2 Credential",
                description=f"OAuth2 credentials for {source.name}",
                integration_short_name=init_session.short_name,
                integration_type=IntegrationType.SOURCE,
                authentication_method=AuthenticationMethod.OAUTH_BROWSER,
                oauth_type=getattr(source, "oauth_type", None),
                encrypted_credentials=encrypted,
                auth_config_class=source.auth_config_class,
            )
            credential = await crud.integration_credential.create(
                uow.session, obj_in=cred_in, ctx=ctx, uow=uow
            )

            await uow.session.flush()
            await uow.session.refresh(credential)

            # Create connection
            conn_in = schemas.ConnectionCreate(
                name=payload.get("name", f"Connection to {source.name}"),
                integration_type=IntegrationType.SOURCE,
                status=ConnectionStatus.ACTIVE,
                integration_credential_id=credential.id,
                short_name=init_session.short_name,
            )
            connection = await crud.connection.create(uow.session, obj_in=conn_in, ctx=ctx, uow=uow)

            # Get collection
            collection = await self.get_collection(
                uow.session,
                payload.get("collection") or source_conn_shell.readable_collection_id,
                ctx,
            )

            # Create sync
            from airweave.core.sync_service import sync_service

            await db.flush()
            await db.refresh(connection)

            sync_in = schemas.SyncCreate(
                name=f"Sync for {payload.get('name') or source.name}",
                description="Auto-generated sync",
                source_connection_id=connection.id,
                embedding_model_connection_id=NATIVE_TEXT2VEC_UUID,
                destination_connection_ids=[NATIVE_QDRANT_UUID],
                cron_schedule=payload.get("cron_schedule"),
                status=SyncStatus.ACTIVE,
                run_immediately=True,
            )
            sync, sync_job = await sync_service.create_and_run_sync(
                uow.session, sync_in=sync_in, ctx=ctx, uow=uow
            )

            # Update shell source connection
            sc_update = {
                "config_fields": validated_config,
                "readable_collection_id": collection.readable_id,
                "sync_id": sync.id,
                "connection_id": connection.id,
                "is_authenticated": True,
            }
            source_conn = await crud.source_connection.update(
                uow.session, db_obj=source_conn_shell, obj_in=sc_update, ctx=ctx, uow=uow
            )

            # Mark init session complete
            await connection_init_session.mark_completed(
                uow.session, session_id=init_session.id, final_connection_id=connection.id, ctx=ctx
            )

            await uow.commit()
            await uow.session.refresh(source_conn)

        return source_conn


# Singleton instance
source_connection_helpers = SourceConnectionHelpers()
