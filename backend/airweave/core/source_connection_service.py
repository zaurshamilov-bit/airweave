"""Service for managing source connections."""

import secrets
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple, Union
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from airweave import crud, schemas
from airweave.api.context import ApiContext
from airweave.core import credentials
from airweave.core.auth_provider_service import auth_provider_service
from airweave.core.collection_service import collection_service
from airweave.core.config import settings as core_settings
from airweave.core.constants.reserved_ids import NATIVE_QDRANT_UUID, NATIVE_TEXT2VEC_UUID
from airweave.core.shared_models import ConnectionStatus, SourceConnectionStatus, SyncStatus
from airweave.core.sync_service import sync_service
from airweave.crud import (
    connection_init_session,
    redirect_session,  # NEW: proxy pre-consent
)
from airweave.db.unit_of_work import UnitOfWork
from airweave.models.connection_init_session import ConnectionInitSession, ConnectionInitStatus
from airweave.models.integration_credential import IntegrationType
from airweave.platform.auth.schemas import AuthType, OAuth2TokenResponse
from airweave.platform.auth.services import oauth2_service
from airweave.platform.auth.settings import integration_settings
from airweave.platform.auth.state import make_state
from airweave.platform.configs.auth import OAuth2AuthConfig, OAuth2BYOCAuthConfig
from airweave.platform.locator import resource_locator
from airweave.platform.temporal.schedule_service import temporal_schedule_service


class SourceConnectionService:
    """Service for managing source connections.

    This service encapsulates the complex transactions required for source connections,
    including:
    - Creating source connections with related objects (integration credential, sync, dag)
    - Updating source connections and keeping related objects in sync
    - Deleting source connections and all related objects
    - Running sync jobs for source connections
    """

    async def _is_non_byoc_oauth_source(self, db: AsyncSession, source_short_name: str) -> bool:
        """Check if a source uses OAuth authentication."""
        source = await crud.source.get_by_short_name(db, short_name=source_short_name)
        if not source or not source.auth_config_class:
            return False

        try:
            auth_config_class = resource_locator.get_auth_config(source.auth_config_class)
            return issubclass(auth_config_class, OAuth2AuthConfig) and not issubclass(
                auth_config_class, OAuth2BYOCAuthConfig
            )
        except Exception:
            return False

    async def _validate_auth_fields(
        self,
        db: AsyncSession,
        source_short_name: str,
        auth_fields: Optional[Dict[str, Any]],
        ctx: ApiContext,
    ) -> dict:
        """Validate auth fields based on auth type.

        Only works for config_class auth type.

        Args:
            db: The database session
            source_short_name: The short name of the source
            auth_fields: The auth fields to validate
            ctx: The current authentication context

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
            f"See https://docs.airweave.ai/{source.short_name}#authentication for more information."
        )

        if not source.auth_config_class:
            raise HTTPException(
                status_code=422,
                detail=f"Source {source.name} does not have an auth configuration defined. "
                + BASE_ERROR_MESSAGE,
            )

        if auth_fields is None:
            raise HTTPException(
                status_code=422,
                detail=f"Source {source.name} requires auth fields. " + BASE_ERROR_MESSAGE,
            )

        try:
            auth_config_class = resource_locator.get_auth_config(source.auth_config_class)
            auth_config = auth_config_class(**auth_fields)
            return auth_config.model_dump()
        except Exception as e:
            ctx.logger.error(f"Failed to validate auth fields: {e}")

            # Check if it's a Pydantic validation error and format it nicely
            from pydantic import ValidationError

            if isinstance(e, ValidationError):
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
                raise HTTPException(
                    status_code=422,
                    detail=f"Invalid auth fields: {str(e)}. " + BASE_ERROR_MESSAGE,
                ) from e

    async def _validate_config_fields(
        self,
        db: AsyncSession,
        source_short_name: str,
        config_fields: Optional[Dict[str, Any]],
        ctx: ApiContext,
    ) -> dict:
        """Validate config fields based on source config class.

        Args:
            db: The database session
            source_short_name: The short name of the source
            config_fields: The config fields to validate
            ctx: The current authentication context

        Returns:
            The validated config fields as a dict

        Raises:
            HTTPException: If config fields are invalid or required but not provided
        """
        # Get the source info
        source = await crud.source.get_by_short_name(db, short_name=source_short_name)
        if not source:
            raise HTTPException(status_code=404, detail=f"Source '{source_short_name}' not found")

        BASE_ERROR_MESSAGE = (
            f"See https://docs.airweave.ai/{source.short_name}#configuration for more information."
        )

        if not hasattr(source, "config_class") or source.config_class is None:
            raise HTTPException(
                status_code=422,
                detail=f"Source {source.name} does not have a configuration class defined. "
                + BASE_ERROR_MESSAGE,
            )

        if config_fields is None:
            try:
                config_class = resource_locator.get_config(source.config_class)
                config = config_class()
                return config.model_dump()
            except Exception:
                raise HTTPException(
                    status_code=422,
                    detail=f"Source {source.name} requires config fields but none were provided. "
                    + BASE_ERROR_MESSAGE,
                ) from None

        try:
            config_class = resource_locator.get_config(source.config_class)
            config = config_class(**config_fields)
            return config.model_dump()
        except Exception as e:
            ctx.logger.error(f"Failed to validate config fields: {e}")

            # Check if it's a Pydantic validation error and format it nicely
            from pydantic import ValidationError

            if isinstance(e, ValidationError):
                error_messages = []
                for error in e.errors():
                    field = ".".join(str(loc) for loc in error.get("loc", []))
                    msg = error.get("msg", "")
                    error_messages.append(f"Field '{field}': {msg}")

                error_detail = f"Invalid configuration for {source.config_class}:\n" + "\n".join(
                    error_messages
                )
                raise HTTPException(
                    status_code=422,
                    detail=f"Invalid config fields: {error_detail}. " + BASE_ERROR_MESSAGE,
                ) from e
            else:
                raise HTTPException(
                    status_code=422,
                    detail=f"Invalid config fields: {str(e)}. " + BASE_ERROR_MESSAGE,
                ) from e

    async def _handle_oauth_validation(
        self, db: AsyncSession, source: Any, source_connection_in: Any, aux_attrs: Dict[str, Any]
    ) -> None:
        """Validate OAuth sources cannot be created with auth_fields through API."""
        if aux_attrs.get("auth_fields") and await self._is_non_byoc_oauth_source(
            db, source_connection_in.short_name
        ):
            raise HTTPException(
                status_code=422,
                detail=(
                    f"Source '{source.name}' requires OAuth authentication and cannot be "
                    f"created through the API. Please use the UI to authenticate through "
                    f"the OAuth consent screen. Visit https://app.airweave.ai "
                    f"to connect this source."
                ),
            )

    async def _validate_auth_provider_and_config(
        self,
        db: AsyncSession,
        auth_provider_readable_id: str,
        auth_provider_config: Optional[Dict[str, Any]],
        ctx: ApiContext,
    ) -> Dict[str, Any]:
        """Validate auth provider exists and config fields are valid."""
        auth_provider_config_dict = None
        if auth_provider_config is not None:
            if hasattr(auth_provider_config, "model_dump"):
                auth_provider_config_dict = auth_provider_config.model_dump()
            else:
                auth_provider_config_dict = auth_provider_config

        auth_provider_connection = await crud.connection.get_by_readable_id(
            db, readable_id=auth_provider_readable_id, ctx=ctx
        )
        if not auth_provider_connection:
            raise HTTPException(
                status_code=404,
                detail=f"Auth provider connection with readable_id '{auth_provider_readable_id}' "
                "not found. To see which auth providers are supported and learn more about how to "
                "use them, check [this page](https://docs.airweave.ai/docs/auth-providers).",
            )

        validated_config = await auth_provider_service.validate_auth_provider_config(
            db, auth_provider_connection.short_name, auth_provider_config_dict
        )

        return validated_config

    async def _get_or_create_collection(
        self,
        uow: Any,
        core_attrs: Dict[str, Any],
        source_connection_in: Any,
        ctx: ApiContext,
    ) -> Any:
        """Get existing collection or create new one."""
        if "collection" not in core_attrs:
            collection_create = schemas.CollectionCreate(
                name=f"Collection for {source_connection_in.name}",
                description=f"Auto-generated collection for {source_connection_in.name}",
            )
            return await collection_service.create(
                db=uow.session,
                collection_in=collection_create,
                ctx=ctx,
                uow=uow,
            )
        else:
            readable_collection_id = core_attrs["collection"]
            if "collection" in core_attrs:
                del core_attrs["collection"]
            collection = await crud.collection.get_by_readable_id(
                db=uow.session, readable_id=readable_collection_id, ctx=ctx
            )
            if not collection:
                raise HTTPException(
                    status_code=404, detail=f"Collection '{readable_collection_id}' not found"
                )
            return collection

    async def create_source_connection(
        self,
        db: AsyncSession,
        source_connection_in: Union[
            schemas.SourceConnectionCreate,
            schemas.SourceConnectionCreateWithCredential,
        ],
        ctx: ApiContext,
    ) -> Tuple[Optional[UUID], Optional[str], schemas.SourceConnection, Optional[schemas.SyncJob]]:
        """Create a new source connection with all related objects.

        Returns:
            Tuple of (init_id, auth_url, source_connection, sync_job)
            - For OAuth flows without token: returns auth_url and shell connection
            - For all other flows: returns fully authenticated connection
        """
        # Route based on auth_mode for unified schema
        if (
            hasattr(source_connection_in, "auth_mode")
            and source_connection_in.auth_mode == "oauth2"
        ):
            if source_connection_in.token_inject:
                return await self._create_with_token_inject(
                    db=db, ctx=ctx, source_connection_in=source_connection_in
                )
            else:
                return await self._start_browser_oauth_flow(
                    db=db, ctx=ctx, source_connection_in=source_connection_in
                )

        # All other auth modes and legacy flows use direct creation
        core_attrs, aux_attrs = source_connection_in.map_to_core_and_auxiliary_attributes()

        async with UnitOfWork(db) as uow:
            source = await crud.source.get_by_short_name(
                db, short_name=source_connection_in.short_name
            )
            if not source:
                raise HTTPException(
                    status_code=404, detail=f"Source not found: {source_connection_in.short_name}"
                )

            integration_credential_id = None

            if core_attrs.get("auth_provider"):
                validated_auth_provider_config = await self._validate_auth_provider_and_config(
                    db=uow.session,
                    auth_provider_readable_id=core_attrs.get("auth_provider"),
                    auth_provider_config=core_attrs.get("auth_provider_config"),
                    ctx=ctx,
                )
                core_attrs["auth_provider_config"] = validated_auth_provider_config
            elif aux_attrs.get("credential_id"):
                integration_credential = await crud.integration_credential.get(
                    uow.session, id=aux_attrs["credential_id"], ctx=ctx
                )
                if not integration_credential:
                    raise HTTPException(status_code=404, detail="Integration credential not found")

                if (
                    integration_credential.integration_short_name != source_connection_in.short_name
                    or integration_credential.integration_type != IntegrationType.SOURCE
                ):
                    raise HTTPException(
                        status_code=400, detail="Credential doesn't match the source type"
                    )
                integration_credential_id = integration_credential.id
            elif aux_attrs.get("auth_fields"):
                await self._handle_oauth_validation(db, source, source_connection_in, aux_attrs)

                auth_fields = await self._validate_auth_fields(
                    uow.session, source_connection_in.short_name, aux_attrs["auth_fields"], ctx
                )

                integration_cred_in = schemas.IntegrationCredentialCreateEncrypted(
                    name=f"{source.name} - {ctx.organization.id}",
                    description=f"Credentials for {source.name} - {ctx.organization.id}",
                    integration_short_name=source_connection_in.short_name,
                    integration_type=IntegrationType.SOURCE,
                    auth_type=source.auth_type,
                    encrypted_credentials=credentials.encrypt(auth_fields),
                    auth_config_class=source.auth_config_class,
                )

                integration_credential = await crud.integration_credential.create(
                    uow.session, obj_in=integration_cred_in, ctx=ctx, uow=uow
                )
                await uow.session.flush()
                integration_credential_id = integration_credential.id
            else:
                raise HTTPException(
                    status_code=400,
                    detail="Either auth_provider, auth_fields or credential_id must be "
                    "provided to create a source connection",
                )

            config_fields = await self._validate_config_fields(
                db, source_connection_in.short_name, core_attrs.get("config_fields"), ctx
            )
            core_attrs["config_fields"] = config_fields

            connection_create = schemas.ConnectionCreate(
                name=source_connection_in.name,
                integration_type=IntegrationType.SOURCE,
                integration_credential_id=integration_credential_id,
                status=ConnectionStatus.ACTIVE,
                short_name=source_connection_in.short_name,
            )

            connection = await crud.connection.create(
                db=uow.session, obj_in=connection_create, ctx=ctx, uow=uow
            )
            await uow.session.flush()
            connection_id = connection.id

            collection = await self._get_or_create_collection(
                uow, core_attrs, source_connection_in, ctx
            )

            sync_in = schemas.SyncCreate(
                name=f"Sync for {source_connection_in.name}",
                description=f"Auto-generated sync for {source_connection_in.name}",
                source_connection_id=connection_id,
                embedding_model_connection_id=NATIVE_TEXT2VEC_UUID,
                destination_connection_ids=[NATIVE_QDRANT_UUID],
                cron_schedule=aux_attrs["cron_schedule"],
                status=SyncStatus.ACTIVE,
                run_immediately=aux_attrs.get(
                    "sync_immediately", True
                ),  # Use sync_immediately from request
            )

            sync, sync_job = await sync_service.create_and_run_sync(
                db=uow.session, sync_in=sync_in, ctx=ctx, uow=uow
            )

            core_attrs_for_db = {k: v for k, v in core_attrs.items() if k != "auth_provider"}

            source_connection_create = {
                **core_attrs_for_db,
                "connection_id": connection_id,
                "readable_collection_id": collection.readable_id,
                "sync_id": sync.id,
                "readable_auth_provider_id": core_attrs.get("auth_provider"),
                "auth_provider_config": core_attrs.get("auth_provider_config"),
                "is_authenticated": True,
            }

            source_connection = await crud.source_connection.create(
                db=uow.session, obj_in=source_connection_create, ctx=ctx, uow=uow
            )
            await uow.session.flush()

            source_connection = schemas.SourceConnection.from_orm_with_collection_mapping(
                source_connection
            )

            if sync_job is not None:
                sync_job = schemas.SyncJob.model_validate(sync_job, from_attributes=True)
                source_connection.status = SourceConnectionStatus.IN_PROGRESS
                source_connection.last_sync_job_status = sync_job.status
                source_connection.last_sync_job_id = sync_job.id
                source_connection.last_sync_job_started_at = sync_job.started_at
                source_connection.last_sync_job_completed_at = sync_job.completed_at
                source_connection.last_sync_job_error = sync_job.error if sync_job.error else None
            else:
                source_connection.status = SourceConnectionStatus.ACTIVE
                source_connection.last_sync_job_status = None
                source_connection.last_sync_job_id = None
                source_connection.last_sync_job_started_at = None
                source_connection.last_sync_job_completed_at = None

            source_connection.auth_fields = "********"

        # Track source connection creation after transaction commits
        from airweave.analytics import business_events

        business_events.track_source_connection_created(
            ctx=ctx,
            connection_id=source_connection.id,
            source_short_name=source_connection_in.short_name,
        )

        return None, None, source_connection, sync_job

    async def _validate_token_with_source(
        self, db: AsyncSession, source_short_name: str, access_token: str, ctx: ApiContext
    ) -> bool:
        """Instantiate the source with the access_token and call validate()."""
        import time

        _log = ctx.logger.with_context(source=source_short_name, op="oauth_validate")

        try:
            source_obj = await crud.source.get_by_short_name(db, short_name=source_short_name)
            if not source_obj:
                _log.warning(f"Skipping token validation: source '{source_short_name}' not found.")
                return False
            source_cls = resource_locator.get_source(source_obj)
        except Exception as e:
            _log.warning(
                f"Skipping token validation: couldn't resolve source class for "
                f"'{source_short_name}': {e}"
            )
            return False

        start = time.perf_counter()
        try:
            try:
                source_instance = await source_cls.create(access_token=access_token, config=None)
            except TypeError:
                source_instance = await source_cls.create(
                    credentials={"access_token": access_token}, config=None
                )

            source_instance.set_logger(_log)

            if not hasattr(source_instance, "validate"):
                _log.info("Source has no validate(); skipping live token check.")
                return False

            is_valid = await source_instance.validate()
            elapsed_ms = (time.perf_counter() - start) * 1000

            if is_valid:
                _log.info(
                    f"OAuth2 token validation succeeded for '{source_short_name}' "
                    f"via {source_cls.__name__} in {elapsed_ms:.0f} ms"
                )
                return True

            _log.error(
                "OAuth2 token validation FAILED for "
                f"'{source_short_name}' via {source_cls.__name__}"
            )
            raise HTTPException(
                status_code=400,
                detail=(
                    f"OAuth2 token failed validation for '{source_short_name}'. "
                    f"Please re-authorize with the required scopes."
                ),
            )
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(
                status_code=400,
                detail=f"Failed to validate OAuth2 token for '{source_short_name}': {e}",
            ) from e

    def validate_source_for_auth_provider(self, source_short_name: str, auth_mode: str) -> None:
        """Validate if a source can use auth providers.

        Temporary restriction for certain sources.
        """
        SOURCES_BLOCKED_FROM_AUTH_PROVIDERS = [
            "confluence",
            "jira",
            "bitbucket",
            "github",
            "ctti",
            "monday",
            "postgresql",
        ]

        if (
            auth_mode == "external_provider"
            and source_short_name in SOURCES_BLOCKED_FROM_AUTH_PROVIDERS
        ):
            raise HTTPException(
                status_code=422,
                detail=(
                    f"The {source_short_name.title()} source cannot currently be "
                    f"created using auth providers. Use auth_mode='direct_auth' with auth_fields."
                ),
            )

    async def run_sync_job_workflow(
        self,
        sync: schemas.Sync,
        sync_job: schemas.SyncJob,
        sync_dag: schemas.SyncDag,
        collection: schemas.Collection,
        source_connection: schemas.SourceConnection,
        ctx: ApiContext,
        background_tasks: Any = None,
        access_token: Optional[str] = None,
    ) -> None:
        """Run a sync job either via Temporal or background tasks.

        This centralizes the logic for executing sync jobs to avoid duplication
        across endpoints.
        """
        from airweave.core.temporal_service import temporal_service

        if await temporal_service.is_temporal_enabled():
            await temporal_service.run_source_connection_workflow(
                sync=sync,
                sync_job=sync_job,
                sync_dag=sync_dag,
                collection=collection,
                source_connection=source_connection,
                ctx=ctx,
                access_token=access_token,
            )
        else:
            if background_tasks is None:
                raise ValueError("background_tasks required when Temporal is disabled")
            from airweave.core.sync_service import sync_service

            background_tasks.add_task(
                sync_service.run,
                sync,
                sync_job,
                sync_dag,
                collection,
                source_connection,
                ctx,
                access_token=access_token,
            )

    async def _generate_authentication_url_for_connection(
        self,
        db: AsyncSession,
        source_connection: Any,
        ctx: ApiContext,
    ) -> Tuple[Optional[str], Optional[datetime]]:
        """Generate authentication URL for an unauthenticated source connection.

        Returns:
            Tuple of (authentication_url, expiry_datetime)
        """
        # Only generate for unauthenticated connections
        if source_connection.is_authenticated:
            return None, None

        # Check if there's an existing init session we can reuse
        if source_connection.connection_init_session_id:
            init_session = await connection_init_session.get(
                db, id=source_connection.connection_init_session_id, ctx=ctx
            )
            if init_session and init_session.status == ConnectionInitStatus.PENDING:
                # Regenerate the proxy URL for this session
                proxy_ttl = int(getattr(core_settings, "REDIRECT_SESSION_TTL_MINUTES", 1440))
                proxy_expires = datetime.now(timezone.utc) + timedelta(minutes=proxy_ttl)
                code8 = await redirect_session.generate_unique_code(db, length=8)

                # Get the OAuth URL
                source = await crud.source.get_by_short_name(
                    db, short_name=source_connection.short_name
                )
                if not source:
                    return None, None

                oauth2_settings = await integration_settings.get_by_short_name(source.short_name)
                if not oauth2_settings:
                    return None, None

                api_callback = f"{core_settings.api_url}/source-connections/callback"

                provider_auth_url = await oauth2_service.generate_auth_url_with_redirect(
                    oauth2_settings,
                    redirect_uri=api_callback,
                    client_id=None,  # Will use default
                    state=init_session.state,  # Reuse the existing state
                )

                # Create redirect session
                await redirect_session.create(
                    db,
                    code=code8,
                    final_url=provider_auth_url,
                    expires_at=proxy_expires,
                    ctx=ctx,
                )

                proxy_url = f"{core_settings.api_url}/source-connections/authorize/{code8}"
                return proxy_url, proxy_expires

        # For connections without init session, we can't generate OAuth URL
        # This might be the case for direct auth connections that failed
        return None, None

    async def get_source_connection(
        self,
        db: AsyncSession,
        source_connection_id: UUID,
        ctx: ApiContext,
        show_auth_fields: bool = False,
    ) -> schemas.SourceConnection:
        """Get a source connection with all related data."""
        source_connection = await crud.source_connection.get(
            db=db, id=source_connection_id, ctx=ctx
        )

        if not source_connection:
            raise HTTPException(status_code=404, detail="Source connection not found")

        source_connection_schema = schemas.SourceConnection.from_orm_with_collection_mapping(
            source_connection
        )

        if source_connection.connection_id:
            connection = await crud.connection.get(
                db=db, id=source_connection.connection_id, ctx=ctx
            )

        if source_connection.connection_id:
            connection = await crud.connection.get(
                db=db, id=source_connection.connection_id, ctx=ctx
            )

            if connection and connection.integration_credential_id:
                integration_credential = await crud.integration_credential.get(
                    db=db, id=connection.integration_credential_id, ctx=ctx
                )

                if integration_credential and integration_credential.encrypted_credentials:
                    if show_auth_fields:
                        decrypted_auth_fields = credentials.decrypt(
                            integration_credential.encrypted_credentials
                        )
                        source_connection_schema.auth_fields = decrypted_auth_fields
                    else:
                        source_connection_schema.auth_fields = "********"

        if source_connection.sync_id:
            sync = await crud.sync.get(db=db, id=source_connection.sync_id, ctx=ctx)
            if sync:
                source_connection_schema.cron_schedule = sync.cron_schedule
                source_connection_schema.next_scheduled_run = sync.next_scheduled_run

                # Log the sync schedule information for debugging
                ctx.logger.info(
                    f"Adding sync schedule to source connection: "
                    f"cron_schedule={sync.cron_schedule}, "
                    f"next_scheduled_run={sync.next_scheduled_run}"
                )

        # Generate authentication URL for unauthenticated connections
        auth_url, auth_expiry = await self._generate_authentication_url_for_connection(
            db, source_connection, ctx
        )
        if auth_url:
            source_connection_schema.authentication_url = auth_url
            source_connection_schema.authentication_url_expiry = auth_expiry

        return source_connection_schema

    async def get_all_source_connections(
        self,
        db: AsyncSession,
        ctx: ApiContext,
        skip: int = 0,
        limit: int = 100,
    ) -> List[schemas.SourceConnectionListItem]:
        """Get all source connections for a user with minimal core attributes."""
        source_connections = await crud.source_connection.get_multi(
            db=db, ctx=ctx, skip=skip, limit=limit
        )

        if not source_connections:
            return []

        list_items = [
            schemas.SourceConnectionListItem(
                id=sc.id,
                name=sc.name,
                description=sc.description,
                short_name=sc.short_name,
                created_at=sc.created_at,
                modified_at=sc.modified_at,
                sync_id=sc.sync_id,
                collection=sc.readable_collection_id,
                is_authenticated=sc.is_authenticated,
            )
            for sc in source_connections
        ]

        return list_items

    async def get_source_connections_by_collection(
        self,
        db: AsyncSession,
        collection: str,
        ctx: ApiContext,
        skip: int = 0,
        limit: int = 100,
    ) -> List[schemas.SourceConnectionListItem]:
        """Get all source connections for a user by collection."""
        source_connections = await crud.source_connection.get_for_collection(
            db=db,
            readable_collection_id=collection,
            ctx=ctx,
            skip=skip,
            limit=limit,
        )

        if not source_connections:
            return []

        list_items = [
            schemas.SourceConnectionListItem(
                id=sc.id,
                name=sc.name,
                description=sc.description,
                short_name=sc.short_name,
                created_at=sc.created_at,
                modified_at=sc.modified_at,
                sync_id=sc.sync_id,
                status=sc.status,
                collection=sc.readable_collection_id,
                is_authenticated=sc.is_authenticated,
            )
            for sc in source_connections
        ]

        return list_items

    async def update_source_connection(
        self,
        db: AsyncSession,
        source_connection_id: UUID,
        source_connection_in: schemas.SourceConnectionUpdate,
        ctx: ApiContext,
    ) -> schemas.SourceConnection:
        """Update a source connection and related objects."""
        source_connection = await crud.source_connection.get(
            db=db, id=source_connection_id, ctx=ctx
        )
        if not source_connection:
            raise HTTPException(status_code=404, detail="Source connection not found")

        async with UnitOfWork(db) as uow:
            if source_connection_in.config_fields is not None:
                validated_config_fields = await self._validate_config_fields(
                    uow.session,
                    source_connection.short_name,
                    (
                        source_connection_in.config_fields.model_dump()
                        if hasattr(source_connection_in.config_fields, "model_dump")
                        else source_connection_in.config_fields
                    ),
                    ctx,
                )
                source_connection_in.config_fields = validated_config_fields

            source_connection = await crud.source_connection.update(
                db=uow.session,
                db_obj=source_connection,
                obj_in=source_connection_in,
                ctx=ctx,
                uow=uow,
            )

            if source_connection_in.cron_schedule is not None and source_connection.sync_id:
                sync = await crud.sync.get(
                    uow.session,
                    id=source_connection.sync_id,
                    ctx=ctx,
                    with_connections=False,
                )
                if sync:
                    sync_update = schemas.SyncUpdate(
                        cron_schedule=source_connection_in.cron_schedule
                    )
                    await crud.sync.update(
                        uow.session,
                        db_obj=sync,
                        obj_in=sync_update,
                        ctx=ctx,
                        uow=uow,
                    )

            if source_connection_in.auth_fields and source_connection.connection_id:
                connection = await crud.connection.get(
                    uow.session, id=source_connection.connection_id, ctx=ctx
                )

                if connection and connection.integration_credential_id:
                    integration_credential = await crud.integration_credential.get(
                        uow.session,
                        id=connection.integration_credential_id,
                        ctx=ctx,
                    )

                    if integration_credential:
                        auth_fields_dict = source_connection_in.auth_fields.model_dump()
                        validated_auth_fields = await self._validate_auth_fields(
                            uow.session,
                            source_connection.short_name,
                            auth_fields_dict,
                            ctx,
                        )
                        credential_update = schemas.IntegrationCredentialUpdate(
                            encrypted_credentials=credentials.encrypt(validated_auth_fields)
                        )
                        await crud.integration_credential.update(
                            uow.session,
                            db_obj=integration_credential,
                            obj_in=credential_update,
                            ctx=ctx,
                            uow=uow,
                        )

            await uow.commit()

            return await self.get_source_connection(
                db=uow.session,
                source_connection_id=source_connection_id,
                ctx=ctx,
            )

    async def delete_source_connection(
        self,
        db: AsyncSession,
        source_connection_id: UUID,
        ctx: ApiContext,
    ) -> schemas.SourceConnection:
        """Delete a source connection and all related components."""
        source_connection = await crud.source_connection.get(
            db=db, id=source_connection_id, ctx=ctx
        )
        if not source_connection:
            raise HTTPException(status_code=404, detail="Source connection not found")

        source_connection_schema = schemas.SourceConnection.from_orm_with_collection_mapping(
            source_connection
        )

        if source_connection.sync_id and source_connection.readable_collection_id:
            try:
                ctx.logger.info(
                    f"Deleting data for source connection {source_connection_id} "
                    f"(sync_id: {source_connection.sync_id}) from destinations"
                )

                collection = await crud.collection.get_by_readable_id(
                    db=db,
                    readable_id=source_connection.readable_collection_id,
                    ctx=ctx,
                )

                if collection:
                    from airweave.platform.destinations.qdrant import QdrantDestination

                    destination = await QdrantDestination.create(collection_id=collection.id)
                    await destination.delete_by_sync_id(source_connection.sync_id)

                    ctx.logger.info(
                        f"Successfully deleted data for sync_id {source_connection.sync_id} "
                        f"from Qdrant collection {collection.id}"
                    )
                else:
                    ctx.logger.warning(
                        f"Collection {source_connection.readable_collection_id} not found, "
                        f"skipping data deletion"
                    )
            except Exception as e:
                ctx.logger.error(
                    f"Error deleting data from destinations: {str(e)}. "
                    f"Continuing with source connection deletion."
                )

        # Cleanup Temporal schedules first (if any)
        if source_connection.sync_id:
            try:
                await temporal_schedule_service.delete_all_schedules_for_sync(
                    sync_id=source_connection.sync_id, db=db, ctx=ctx
                )
            except Exception as e:
                ctx.logger.error(
                    f"Failed to delete schedules for sync {source_connection.sync_id}: {e}"
                )

        await crud.source_connection.remove(db=db, id=source_connection_id, ctx=ctx)

        return source_connection_schema

    async def run_source_connection(
        self,
        db: AsyncSession,
        source_connection_id: UUID,
        ctx: ApiContext,
        access_token: Optional[str] = None,
    ) -> schemas.SyncJob:
        """Trigger a sync run for a source connection."""
        source_connection = await crud.source_connection.get(
            db=db, id=source_connection_id, ctx=ctx
        )
        if not source_connection:
            raise HTTPException(status_code=404, detail="Source connection not found")

        if not source_connection.sync_id:
            raise HTTPException(status_code=400, detail="Source connection has no associated sync")

        sync, sync_job, sync_dag = await sync_service.trigger_sync_run(
            db=db, sync_id=source_connection.sync_id, ctx=ctx
        )

        if access_token:
            sync_job.access_token = access_token

        return sync_job

    async def get_source_connection_jobs(
        self,
        db: AsyncSession,
        source_connection_id: UUID,
        ctx: ApiContext,
    ) -> list[schemas.SourceConnectionJob]:
        """Get all sync jobs for a source connection."""
        source_connection = await crud.source_connection.get(
            db=db, id=source_connection_id, ctx=ctx
        )
        if not source_connection:
            raise HTTPException(status_code=404, detail="Source connection not found")

        if not source_connection.sync_id:
            return []

        sync_jobs = await sync_service.list_sync_jobs(
            db=db, ctx=ctx, sync_id=source_connection.sync_id
        )

        source_connection_jobs = []
        for job in sync_jobs:
            sync_job_schema = schemas.SyncJob.model_validate(job, from_attributes=True)
            source_connection_job = sync_job_schema.to_source_connection_job(source_connection_id)
            source_connection_jobs.append(source_connection_job)

        return source_connection_jobs

    async def get_source_connection_job(
        self,
        db: AsyncSession,
        source_connection_id: UUID,
        job_id: UUID,
        ctx: ApiContext,
    ) -> schemas.SourceConnectionJob:
        """Get a specific sync job for a source connection."""
        source_connection = await crud.source_connection.get(
            db=db, id=source_connection_id, ctx=ctx
        )
        if not source_connection:
            raise HTTPException(status_code=404, detail="Source connection not found")

        if not source_connection.sync_id:
            raise HTTPException(status_code=404, detail="Source connection has no associated sync")

        sync_job = await sync_service.get_sync_job(
            db=db, job_id=job_id, ctx=ctx, sync_id=source_connection.sync_id
        )

        sync_job_schema = schemas.SyncJob.model_validate(sync_job, from_attributes=True)
        source_connection_job = sync_job_schema.to_source_connection_job(source_connection_id)

        return source_connection_job

    async def update_source_connection_status(
        self,
        db: AsyncSession,
        source_connection_id: UUID,
        status: SourceConnectionStatus,
        ctx: ApiContext,
    ) -> schemas.SourceConnection:
        """Update the status of a source connection."""
        source_connection = await crud.source_connection.get(
            db=db, id=source_connection_id, ctx=ctx
        )
        if not source_connection:
            raise HTTPException(status_code=404, detail="Source connection not found")

        async with UnitOfWork(db) as uow:
            source_connection = await crud.source_connection.update_status(
                db=uow.session,
                id=source_connection_id,
                status=status,
                ctx=ctx,
            )

            if hasattr(source_connection, "connection_id") and source_connection.connection_id:
                connection = await crud.connection.get(
                    uow.session, id=source_connection.connection_id, ctx=ctx
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
                        ctx=ctx,
                        uow=uow,
                    )

            if source_connection.sync_id:
                sync = await crud.sync.get(uow.session, id=source_connection.sync_id, ctx=ctx)
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
                        ctx=ctx,
                        uow=uow,
                    )

            await uow.commit()
            return source_connection

    async def get_oauth2_authorization_url(
        self,
        source_short_name: str,
        client_id: Optional[str] = None,
    ) -> schemas.OAuth2AuthUrl:
        """Get the OAuth2 authorization URL for a source."""
        oauth2_settings = await integration_settings.get_by_short_name(source_short_name)
        if not oauth2_settings:
            raise HTTPException(
                status_code=404, detail=f"Settings not found for source: {source_short_name}"
            )

        if oauth2_settings.auth_type not in [
            AuthType.oauth2,
            AuthType.oauth2_with_refresh,
            AuthType.oauth2_with_refresh_rotating,
        ]:
            raise HTTPException(
                status_code=400,
                detail=f"Source {source_short_name} does not support OAuth2 authentication",
            )

        state = make_state({"short_name": source_short_name})
        auth_url = await oauth2_service.generate_auth_url(oauth2_settings, client_id, state)
        return schemas.OAuth2AuthUrl(url=auth_url)

    async def create_credential_from_oauth2_code(
        self,
        db: AsyncSession,
        source_short_name: str,
        code: str,
        ctx: ApiContext,
        credential_name: Optional[str] = None,
        credential_description: Optional[str] = None,
        client_id: Optional[str] = None,
        client_secret: Optional[str] = None,
    ) -> schemas.IntegrationCredentialInDB:
        """Exchange OAuth2 code for token and create integration credentials."""
        try:
            source = await crud.source.get_by_short_name(db, short_name=source_short_name)
            if not source:
                raise HTTPException(
                    status_code=404, detail=f"Source not found: {source_short_name}"
                )

            if not source.auth_type or not source.auth_type.startswith("oauth2"):
                raise HTTPException(
                    status_code=400,
                    detail=f"Source {source_short_name} does not support OAuth2 authentication",
                )

            token_response = await self._exchange_authorization_code_for_token(
                ctx,
                source_short_name=source_short_name,
                code=code,
                client_id=client_id,
                client_secret=client_secret,
            )

            if token_response.access_token:
                await self._validate_token_with_source(
                    db=db,
                    source_short_name=source_short_name,
                    access_token=token_response.access_token,
                )

            auth_fields = token_response.model_dump()
            if client_id:
                auth_fields["client_id"] = client_id
            if client_secret:
                auth_fields["client_secret"] = client_secret

            validated_auth_fields = await self._validate_auth_fields(
                db=db, source_short_name=source_short_name, auth_fields=auth_fields, ctx=ctx
            )

            async with UnitOfWork(db) as uow:
                encrypted_credentials = credentials.encrypt(validated_auth_fields)
                name = credential_name or f"{source.name} OAuth2 Credential"
                description = credential_description or f"OAuth2 credentials for {source.name}"

                integration_cred_in = schemas.IntegrationCredentialCreateEncrypted(
                    name=name,
                    description=description,
                    integration_short_name=source_short_name,
                    integration_type=IntegrationType.SOURCE,
                    auth_type=source.auth_type,
                    encrypted_credentials=encrypted_credentials,
                    auth_config_class=source.auth_config_class,
                )

                integration_credential = await crud.integration_credential.create(
                    uow.session, obj_in=integration_cred_in, ctx=ctx, uow=uow
                )

                await uow.commit()
                await uow.session.refresh(integration_credential)

                return schemas.IntegrationCredentialInDB.model_validate(
                    integration_credential, from_attributes=True
                )

        except Exception as e:
            ctx.logger.error(f"Failed to create credential from OAuth2 code: {e}")
            if isinstance(e, HTTPException):
                raise
            raise HTTPException(
                status_code=400, detail=f"Failed to create credential from OAuth2 code: {str(e)}"
            ) from e

    async def _exchange_authorization_code_for_token(
        self,
        ctx: ApiContext,
        source_short_name: str,
        code: str,
        client_id: Optional[str] = None,
        client_secret: Optional[str] = None,
    ) -> OAuth2TokenResponse:
        """Exchange an OAuth2 authorization code for a token."""
        try:
            return await oauth2_service.exchange_authorization_code_for_token(
                ctx=ctx,
                source_short_name=source_short_name,
                code=code,
                client_id=client_id,
                client_secret=client_secret,
            )
        except Exception as e:
            raise HTTPException(
                status_code=400, detail="Failed to exchange authorization code for token"
            ) from e

    def _build_oauth_credentials(
        self,
        token_inject: Any,
        client_id: Optional[str],
        client_secret: Optional[str],
    ) -> Dict[str, Any]:
        """Build OAuth credentials dictionary from token injection."""
        creds: Dict[str, Any] = {"access_token": token_inject.access_token}
        if token_inject.refresh_token:
            creds["refresh_token"] = token_inject.refresh_token
        if client_id:
            creds["client_id"] = client_id
        if client_secret:
            creds["client_secret"] = client_secret
        if token_inject.token_type:
            creds["token_type"] = token_inject.token_type
        if token_inject.expires_at:
            creds["expires_at"] = (
                token_inject.expires_at.isoformat()
                if hasattr(token_inject.expires_at, "isoformat")
                else token_inject.expires_at
            )
        if token_inject.extra:
            creds.update({f"extra.{k}": v for k, v in token_inject.extra.items()})
        return creds

    async def _create_with_token_inject(
        self,
        db: AsyncSession,
        *,
        ctx: ApiContext,
        source_connection_in: schemas.SourceConnectionCreate,
    ) -> Tuple[Optional[UUID], Optional[str], schemas.SourceConnection, Optional[schemas.SyncJob]]:
        """Create connection immediately using injected OAuth tokens."""
        # Get source info
        source = await crud.source.get_by_short_name(db, short_name=source_connection_in.short_name)
        if not source:
            raise HTTPException(
                status_code=404, detail=f"Source not found: {source_connection_in.short_name}"
            )

        cfg = source_connection_in.config_fields
        config_fields = await self._validate_config_fields(
            db=db,
            source_short_name=source_connection_in.short_name,
            config_fields=(cfg.model_dump() if hasattr(cfg, "model_dump") else cfg),
            ctx=ctx,
        )

        # Build credentials from token injection
        creds = self._build_oauth_credentials(
            source_connection_in.token_inject,
            source_connection_in.client_id,
            source_connection_in.client_secret,
        )
        encrypted = credentials.encrypt(creds)

        async with UnitOfWork(db) as uow:
            integration_cred_in = schemas.IntegrationCredentialCreateEncrypted(
                name=f"{source.name} - {ctx.organization.id}",
                description=f"Credentials for {source.name} - {ctx.organization.id}",
                integration_short_name=source.short_name,
                integration_type=IntegrationType.SOURCE,
                auth_type=source.auth_type,
                encrypted_credentials=encrypted,
                auth_config_class=source.auth_config_class,
            )
            integration_credential = await crud.integration_credential.create(
                uow.session, obj_in=integration_cred_in, ctx=ctx, uow=uow
            )
            await uow.session.flush()

            connection_create = schemas.ConnectionCreate(
                name=source_connection_in.name,
                integration_type=IntegrationType.SOURCE,
                integration_credential_id=integration_credential.id,
                status=ConnectionStatus.ACTIVE,
                short_name=source.short_name,
            )
            connection = await crud.connection.create(
                db=uow.session, obj_in=connection_create, ctx=ctx, uow=uow
            )
            await uow.session.flush()
            connection_id = connection.id

            if source_connection_in.collection:
                collection = await crud.collection.get_by_readable_id(
                    db=uow.session, readable_id=source_connection_in.collection, ctx=ctx
                )
                if not collection:
                    raise HTTPException(
                        status_code=404,
                        detail=f"Collection '{source_connection_in.collection}' not found",
                    )
            else:
                collection_create = schemas.CollectionCreate(
                    name=f"Collection for {source_connection_in.name}",
                    description=f"Auto-generated collection for {source_connection_in.name}",
                )
                collection = await collection_service.create(
                    db=uow.session, collection_in=collection_create, ctx=ctx, uow=uow
                )

            sync_in = schemas.SyncCreate(
                name=f"Sync for {source_connection_in.name}",
                description=f"Auto-generated sync for {source_connection_in.name}",
                source_connection_id=connection_id,
                embedding_model_connection_id=NATIVE_TEXT2VEC_UUID,
                destination_connection_ids=[NATIVE_QDRANT_UUID],
                cron_schedule=source_connection_in.cron_schedule,
                status=SyncStatus.ACTIVE,
                run_immediately=True,  # Always run immediately after authentication
            )
            sync, sync_job = await sync_service.create_and_run_sync(
                db=uow.session, sync_in=sync_in, ctx=ctx, uow=uow
            )

            source_connection_create = {
                "name": source_connection_in.name,
                "description": source_connection_in.description,
                "short_name": source.short_name,
                "config_fields": config_fields,
                "connection_id": connection_id,
                "readable_collection_id": collection.readable_id,
                "sync_id": sync.id,
                "readable_auth_provider_id": None,
                "auth_provider_config": None,
                "is_authenticated": True,
            }
            sc_row = await crud.source_connection.create(
                db=uow.session, obj_in=source_connection_create, ctx=ctx, uow=uow
            )
            await uow.session.flush()

            source_connection = schemas.SourceConnection.from_orm_with_collection_mapping(sc_row)
            if sync_job is not None:
                sync_job = schemas.SyncJob.model_validate(sync_job, from_attributes=True)
                source_connection.status = SourceConnectionStatus.IN_PROGRESS
                source_connection.last_sync_job_status = sync_job.status
                source_connection.last_sync_job_id = sync_job.id
                source_connection.last_sync_job_started_at = sync_job.started_at
                source_connection.last_sync_job_completed_at = sync_job.completed_at
            else:
                source_connection.status = SourceConnectionStatus.ACTIVE

            source_connection.auth_fields = "********"

            await uow.commit()

        return None, None, source_connection, sync_job

    async def _start_browser_oauth_flow(
        self,
        db: AsyncSession,
        *,
        ctx: ApiContext,
        source_connection_in: schemas.SourceConnectionCreate,
    ) -> Tuple[Optional[UUID], Optional[str], schemas.SourceConnection, Optional[schemas.SyncJob]]:
        """Start a short-lived init session and return a proxy URL for provider consent."""
        # Get source info
        source = await crud.source.get_by_short_name(db, short_name=source_connection_in.short_name)
        if not source:
            raise HTTPException(
                status_code=404, detail=f"Source not found: {source_connection_in.short_name}"
            )

        api_callback = f"{core_settings.api_url}/source-connections/callback"
        state = secrets.token_urlsafe(24)

        oauth2_settings = await integration_settings.get_by_short_name(source.short_name)
        if not oauth2_settings:
            raise HTTPException(
                status_code=404, detail=f"Settings not found for source: {source.short_name}"
            )

        provider_auth_url = await oauth2_service.generate_auth_url_with_redirect(
            oauth2_settings,
            redirect_uri=api_callback,
            client_id=source_connection_in.client_id,
            state=state,
        )

        payload = source_connection_in.model_dump(
            exclude={
                "client_id",
                "client_secret",
                "token_inject",
                "redirect_url",
                "auth_mode",
                "access_token",
                "refresh_token",
            },
            exclude_none=True,
        )
        overrides = {
            "client_id": source_connection_in.client_id,
            "client_secret": source_connection_in.client_secret,
            "redirect_url": source_connection_in.redirect_url,
            "oauth_redirect_uri": api_callback,
        }

        ttl_minutes = getattr(core_settings, "CONNECTION_INIT_TTL_MINUTES", 30)
        expires_at = ConnectionInitSession.default_expires_at(minutes=ttl_minutes)

        async with UnitOfWork(db) as uow:
            # 1. Create the shell SourceConnection first
            shell_create = {
                "name": source_connection_in.name,
                "description": source_connection_in.description,
                "short_name": source.short_name,
                "is_authenticated": False,
                "readable_collection_id": source_connection_in.collection,
            }
            sc_shell_obj = await crud.source_connection.create(
                uow.session, obj_in=shell_create, ctx=ctx, uow=uow
            )

            await uow.session.flush()
            await uow.session.refresh(sc_shell_obj)

            # 2. Create the ConnectionInitSession, linking it to the shell
            init_obj = await connection_init_session.create(
                uow.session,
                obj_in={
                    "organization_id": ctx.organization.id,
                    "short_name": source.short_name,
                    "payload": payload,
                    "overrides": overrides,
                    "state": state,
                    "status": ConnectionInitStatus.PENDING,
                    "expires_at": expires_at,
                    # No back-ref needed, the shell points to the session
                },
                ctx=ctx,
                uow=uow,
            )

            init_id = init_obj.id
            await uow.session.flush()

            # 3. Update shell with the session ID
            sc_shell_obj.connection_init_session_id = init_id
            uow.session.add(sc_shell_obj)

            await uow.commit()
            await uow.session.refresh(sc_shell_obj)

        sc_shell_schema = schemas.SourceConnection.from_orm_with_collection_mapping(sc_shell_obj)

        # PRE-CONSENT PROXY: generate 8-char code that redirects to provider OAuth URL
        proxy_ttl = int(getattr(core_settings, "REDIRECT_SESSION_TTL_MINUTES", 1440))  # 1 day
        proxy_expires = datetime.now(timezone.utc) + timedelta(minutes=proxy_ttl)
        code8 = await redirect_session.generate_unique_code(db, length=8)
        await redirect_session.create(
            db,
            code=code8,
            final_url=provider_auth_url,  # store provider URL here
            expires_at=proxy_expires,
            ctx=ctx,
        )

        proxy_url = f"{core_settings.api_url}/source-connections/authorize/{code8}"

        # Add authentication URL and expiry to the schema
        sc_shell_schema.authentication_url = proxy_url
        sc_shell_schema.authentication_url_expiry = proxy_expires

        return init_id, proxy_url, sc_shell_schema, None

    async def complete_connection_from_oauth_callback(  # noqa: C901
        self,
        db: AsyncSession,
        *,
        state: str,
        code: str,
        ctx: ApiContext,
    ) -> Tuple[schemas.SourceConnection, str, Optional[schemas.SyncJob], Dict[str, Any]]:
        """Handle OAuth redirect callback.

        Steps:
        - Look up init session by state.
        - Exchange the code for a token.
        - Create IntegrationCredential + Connection + SourceConnection (+ Sync/Job).
        - Return (source_connection, final_redirect_url, sync_job, meta).
        """
        session_obj = await connection_init_session.get_by_state(db, state=state, ctx=ctx)
        if not session_obj:
            raise HTTPException(status_code=404, detail="Init session not found or expired")
        if session_obj.status != ConnectionInitStatus.PENDING:
            raise HTTPException(status_code=400, detail=f"Session status is {session_obj.status}")

        # Find the associated source connection shell using the new CRUD method
        source_connection_shell = await crud.source_connection.get_by_query_and_org(
            db,
            ctx=ctx,
            connection_init_session_id=session_obj.id,
        )
        if not source_connection_shell:
            raise HTTPException(status_code=404, detail="Source connection shell not found")
        source_short_name = session_obj.short_name
        payload = session_obj.payload or {}
        overrides = session_obj.overrides or {}

        oauth_redirect_uri = overrides.get("oauth_redirect_uri")
        final_redirect_url = overrides.get("redirect_url") or core_settings.app_url

        sc_source = await crud.source.get_by_short_name(db, short_name=source_short_name)
        if not sc_source:
            raise HTTPException(status_code=404, detail=f"Source not found: {source_short_name}")

        token_response = await oauth2_service.exchange_authorization_code_for_token_with_redirect(
            ctx=ctx,
            source_short_name=source_short_name,
            code=code,
            redirect_uri=oauth_redirect_uri,
            client_id=overrides.get("client_id"),
            client_secret=overrides.get("client_secret"),
        )
        if token_response.access_token:
            await self._validate_token_with_source(
                db=db,
                source_short_name=source_short_name,
                access_token=token_response.access_token,
                ctx=ctx,
            )

        auth_fields = token_response.model_dump()
        if overrides.get("client_id"):
            auth_fields["client_id"] = overrides["client_id"]
        if overrides.get("client_secret"):
            auth_fields["client_secret"] = overrides["client_secret"]

        validated_auth = await self._validate_auth_fields(
            db=db, source_short_name=source_short_name, auth_fields=auth_fields, ctx=ctx
        )

        raw_config = payload.get("config_fields")
        config_fields = await self._validate_config_fields(
            db=db,
            source_short_name=source_short_name,
            config_fields=(
                raw_config.model_dump() if hasattr(raw_config, "model_dump") else raw_config
            ),
            ctx=ctx,
        )

        sync_job = None
        created_new_collection = False

        async with UnitOfWork(db) as uow:
            encrypted = credentials.encrypt(validated_auth)
            cred_in = schemas.IntegrationCredentialCreateEncrypted(
                name=f"{sc_source.name} OAuth2 Credential",
                description=f"OAuth2 credentials for {sc_source.name}",
                integration_short_name=source_short_name,
                integration_type=IntegrationType.SOURCE,
                auth_type=sc_source.auth_type,
                encrypted_credentials=encrypted,
                auth_config_class=sc_source.auth_config_class,
            )
            integration_cred = await crud.integration_credential.create(
                uow.session, obj_in=cred_in, ctx=ctx, uow=uow
            )
            await uow.session.flush()

            conn_in = schemas.ConnectionCreate(
                name=payload.get("name", f"Connection to {sc_source.name}"),
                integration_type=IntegrationType.SOURCE,
                status=ConnectionStatus.ACTIVE,
                integration_credential_id=integration_cred.id,
                short_name=source_short_name,
            )
            connection = await crud.connection.create(uow.session, obj_in=conn_in, ctx=ctx, uow=uow)
            await uow.session.flush()

            # Collection (create if absent)
            collection_id_readable = payload.get("collection")
            if collection_id_readable:
                collection = await crud.collection.get_by_readable_id(
                    db=uow.session, readable_id=collection_id_readable, ctx=ctx
                )
                if not collection:
                    raise HTTPException(
                        status_code=404, detail=f"Collection '{collection_id_readable}' not found"
                    )
            else:
                collection = await collection_service.create(
                    db=uow.session,
                    collection_in=schemas.CollectionCreate(
                        name=f"Collection for {payload.get('name') or sc_source.name}",
                        description=f"""Auto-generated collection for {
                            payload.get("name") or sc_source.name
                        }""",
                    ),
                    ctx=ctx,
                    uow=uow,
                )
                created_new_collection = True

            sync_in = schemas.SyncCreate(
                name=f"Sync for {payload.get('name') or sc_source.name}",
                description=f"Auto-generated sync for {payload.get('name') or sc_source.name}",
                source_connection_id=connection.id,
                embedding_model_connection_id=NATIVE_TEXT2VEC_UUID,
                destination_connection_ids=[NATIVE_QDRANT_UUID],
                cron_schedule=payload.get("cron_schedule"),
                status=SyncStatus.ACTIVE,
                run_immediately=True,  # Always run immediately after authentication
            )
            sync, sync_job_obj = await sync_service.create_and_run_sync(
                db=uow.session, sync_in=sync_in, ctx=ctx, uow=uow
            )
            sync_job = (
                schemas.SyncJob.model_validate(sync_job_obj, from_attributes=True)
                if sync_job_obj
                else None
            )

            # Update the existing shell instead of creating a new record
            sc_update_data = {
                "name": payload.get("name"),
                "description": payload.get("description"),
                "config_fields": config_fields,
                "connection_id": connection.id,
                "readable_collection_id": collection.readable_id,
                "sync_id": sync.id,
                "is_authenticated": True,
            }
            sc_row = await crud.source_connection.update(
                db=uow.session,
                db_obj=source_connection_shell,
                obj_in=sc_update_data,
                ctx=ctx,
                uow=uow,
            )
            await uow.session.flush()

            sc_schema = schemas.SourceConnection.from_orm_with_collection_mapping(sc_row)
            if sync_job:
                sc_schema.status = SourceConnectionStatus.IN_PROGRESS
                sc_schema.last_sync_job_status = sync_job.status
                sc_schema.last_sync_job_id = sync_job.id
                sc_schema.last_sync_job_started_at = sync_job.started_at
                sc_schema.last_sync_job_completed_at = sync_job.completed_at
            else:
                sc_schema.status = SourceConnectionStatus.ACTIVE

            sc_schema.auth_fields = "********"

            await connection_init_session.mark_completed(
                uow.session, session_id=session_obj.id, final_connection_id=connection.id, ctx=ctx
            )
            await uow.commit()

        meta = {
            "sync_immediately": True,  # Always true after authentication
            "creating_new_collection": created_new_collection,
        }
        return sc_schema, final_redirect_url, sync_job, meta


# Singleton instance
source_connection_service = SourceConnectionService()
