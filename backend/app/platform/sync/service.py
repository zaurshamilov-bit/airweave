"""Module for data synchronization."""

from datetime import datetime
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app import crud, schemas
from app.core import credentials
from app.core.exceptions import NotFoundException
from app.core.logging import logger
from app.core.shared_models import SyncJobStatus
from app.db.session import get_db_context
from app.db.unit_of_work import UnitOfWork
from app.platform.auth.schemas import AuthType
from app.platform.auth.services import oauth2_service
from app.platform.auth.settings import integration_settings
from app.platform.destinations.weaviate import WeaviateDestination
from app.platform.embedding_models.local_text2vec import LocalText2Vec
from app.platform.entities._base import BaseEntity
from app.platform.locator import resource_locator
from app.platform.sync.context import SyncContext
from app.platform.sync.pubsub import SyncProgressUpdate, sync_pubsub


class SyncService:
    """Main service for data synchronization."""

    async def create(
        self,
        db: AsyncSession,
        sync: schemas.SyncCreate,
        current_user: schemas.User,
        uow: UnitOfWork,
    ) -> schemas.Sync:
        """Create a new sync."""
        return await crud.sync.create(db=db, obj_in=sync, current_user=current_user, uow=uow)

    async def run(
        self,
        sync: schemas.Sync,
        sync_job: schemas.SyncJob,
        current_user: schemas.User,
    ) -> schemas.Sync:
        """Run a sync.

        This method:
        1. Creates a sync context
        2. Processes entities from the source
        3. Handles updates, inserts, and deletions in both DB and destination
        4. Uses batch processing for efficiency
        """
        try:
            async with get_db_context() as db:
                sync_context = await self.create_sync_context(db, sync, sync_job, current_user)

                logger.info(f"Starting job with id {sync_context.sync_job.id}.")

                # TODO: Implement microbatch processing

                sync_progress_update = SyncProgressUpdate()

                async for entity in sync_context.source.generate_entities():
                    # Enrich entity with sync context information
                    entity = await self._enrich_entity(entity, sync_context)

                    # Calculate hash for deduplication
                    entity_hash = entity.hash()

                    # Check if entity exists in DB
                    db_entity = await crud.entity.get_by_entity_and_sync_id(
                        db, entity_id=entity.entity_id, sync_id=sync.id
                    )

                    if db_entity:
                        if db_entity.hash == entity_hash:
                            # No changes, update sync_job_id
                            await crud.entity.update_job_id(
                                db, db_obj=db_entity, sync_job_id=sync_job.id
                            )
                            sync_progress_update.already_sync += 1
                        else:
                            # Content changed, update both DB and destination
                            entity_update = schemas.EntityUpdate(
                                sync_job_id=sync_job.id,
                                hash=entity_hash,
                            )
                            await crud.entity.update(
                                db,
                                db_obj=db_entity,
                                obj_in=entity_update,
                                organization_id=sync.organization_id,
                            )
                            await sync_context.destination.delete(db_entity.id)
                            await sync_context.destination.insert(entity)
                            sync_progress_update.updated += 1
                    else:
                        # New entity, insert into DB and buffer for destination
                        entity_schema = schemas.EntityCreate(
                            sync_id=sync.id,
                            sync_job_id=sync_job.id,
                            entity_id=entity.entity_id,
                            hash=entity_hash,
                        )
                        db_entity = await crud.entity.create(
                            db,
                            obj_in=entity_schema,
                            organization_id=sync.organization_id,
                        )
                        entity.db_entity_id = db_entity.id
                        await sync_context.destination.insert(entity)

                        sync_progress_update.inserted += 1

                    # Publish partial progress using job_id
                    await sync_pubsub.publish(
                        sync_job.id,
                        sync_progress_update,
                    )

            async with get_db_context() as db:
                # Handle deletions - remove outdated entities
                outdated_entities = await crud.entity.get_all_outdated(
                    db, sync_id=sync.id, sync_job_id=sync_job.id
                )
                if outdated_entities:
                    # Remove from destination
                    for entity in outdated_entities:
                        await sync_context.destination.delete(entity.id)
                        # Remove from database
                        await crud.entity.remove(
                            db, id=entity.id, organization_id=sync.organization_id
                        )
                        sync_progress_update.deleted += 1

                    # Publish partial progress using job_id
                    await sync_pubsub.publish(
                        sync_job.id,
                        sync_progress_update,
                    )

        except Exception as e:
            logger.error(f"An error occurred while syncing: {str(e)}", exc_info=True)
            async with get_db_context() as db:
                sync_job_db = await crud.sync_job.get(db, sync_job.id, current_user)
                sync_job_schema = schemas.SyncJobUpdate.model_validate(sync_job_db)
                sync_job_schema.status = SyncJobStatus.FAILED
                sync_job_schema.failed_at = datetime.now()
                sync_job_schema.error = str(e)

                await crud.sync_job.update(db, sync_job_db, sync_job_schema, current_user)
                sync_progress_update.is_failed = True
                await sync_pubsub.publish(sync_job.id, sync_progress_update)

                return sync

        async with get_db_context() as db:
            sync_job_db = await crud.sync_job.get(db, sync_job.id, current_user)
            sync_job_schema = schemas.SyncJobUpdate.model_validate(
                sync_job_db, from_attributes=True
            )
            sync_job_schema.status = SyncJobStatus.COMPLETED
            sync_job_schema.completed_at = datetime.now()
            try:
                await crud.sync_job.update(
                    db, db_obj=sync_job_db, obj_in=sync_job_schema, current_user=current_user
                )
            except Exception as e:
                logger.error(f"An error occured while updating the sync job: {e}")

            sync_progress_update.is_complete = True
            await sync_pubsub.publish(sync_job.id, sync_progress_update)

            return sync

    async def _enrich_entity(
        self,
        entity: BaseEntity,
        sync_context: SyncContext,
    ) -> BaseEntity:
        """Enrich a entity with information from the sync context."""
        entity.source_name = sync_context.source._name
        entity.sync_id = sync_context.sync.id
        entity.sync_job_id = sync_context.sync_job.id
        entity.sync_metadata = sync_context.sync.sync_metadata
        if sync_context.sync.white_label_id:
            entity.white_label_user_identifier = sync_context.sync.white_label_user_identifier
            entity.white_label_id = sync_context.sync.white_label_id
            entity.white_label_name = sync_context.white_label.name

        return entity

    async def create_sync_context(
        self,
        db: AsyncSession,
        sync: schemas.Sync,
        sync_job: schemas.SyncJob,
        current_user: schemas.User,
    ) -> SyncContext:
        """Create a sync context."""
        source_instance = await self._create_source_instance(db, sync, current_user)

        # Handle embedding model and destination
        embedding_model = self._get_embedding_model(sync)
        destination = await self._get_destination(sync, embedding_model)

        sync_context = SyncContext(source_instance, destination, embedding_model, sync, sync_job)

        if sync.white_label_id:
            white_label = await crud.white_label.get(db, sync.white_label_id, current_user)
            sync_context.white_label = white_label

        return sync_context

    async def _create_source_instance(
        self,
        db: AsyncSession,
        sync: schemas.Sync,
        current_user: schemas.User,
    ):
        """Create and configure the source instance based on authentication type."""
        source_connection = await crud.connection.get(db, sync.source_connection_id, current_user)
        if not source_connection:
            raise NotFoundException("Source connection not found")

        source_model = await crud.source.get_by_short_name(db, source_connection.short_name)
        if not source_model:
            raise NotFoundException("Source not found")

        source_class = resource_locator.get_source(source_model)

        if source_model.auth_type == AuthType.none or source_model.auth_type is None:
            return await source_class.create()

        if source_model.auth_type in [
            AuthType.oauth2_with_refresh,
            AuthType.oauth2_with_refresh_rotating,
        ]:
            return await self._create_oauth2_with_refresh_source(
                db, source_model, source_class, current_user, source_connection
            )

        if source_model.auth_type == AuthType.oauth2:
            return await self._create_oauth2_source(
                db, source_class, current_user, source_connection
            )

        return await self._create_other_auth_source(
            db, source_model, source_class, current_user, source_connection
        )

    async def _create_oauth2_with_refresh_source(
        self,
        db: AsyncSession,
        source_model: schemas.Source,
        source_class,
        current_user: schemas.User,
        source_connection: schemas.Connection,
    ):
        """Create source instance for OAuth2 with refresh token."""
        oauth2_response = await oauth2_service.refresh_access_token(
            db, source_model.short_name, current_user, source_connection.id
        )
        return await source_class.create(oauth2_response.access_token)

    async def _create_oauth2_source(
        self,
        db: AsyncSession,
        source_class,
        current_user: schemas.User,
        source_connection: schemas.Connection,
    ):
        """Create source instance for regular OAuth2."""
        if not source_connection.integration_credential_id:
            raise NotFoundException("Source connection has no integration credential")

        credential = await self._get_integration_credential(db, source_connection, current_user)
        decrypted_credential = credentials.decrypt(credential.encrypted_credentials)
        return await source_class.create(decrypted_credential["access_token"])

    async def _create_other_auth_source(
        self,
        db: AsyncSession,
        source_model: schemas.Source,
        source_class,
        current_user: schemas.User,
        source_connection: schemas.Connection,
    ):
        """Create source instance for other authentication types."""
        if not source_connection.integration_credential_id:
            raise NotFoundException("Source connection has no integration credential")

        credential = await self._get_integration_credential(db, source_connection, current_user)
        decrypted_credential = credentials.decrypt(credential.encrypted_credentials)

        if not source_model.auth_config_class:
            raise ValueError(f"Auth config class required for auth type {source_model.auth_type}")

        auth_config = resource_locator.get_auth_config(source_model.auth_config_class)
        source_credentials = auth_config.model_validate(decrypted_credential)
        return await source_class.create(source_credentials)

    async def _get_integration_credential(
        self,
        db: AsyncSession,
        source_connection: schemas.Connection,
        current_user: schemas.User,
    ):
        """Retrieve and validate integration credential."""
        credential = await crud.integration_credential.get(
            db, source_connection.integration_credential_id, current_user
        )
        if not credential:
            raise NotFoundException("Source integration credential not found")
        return credential

    def _get_embedding_model(self, sync: schemas.Sync):
        """Get the embedding model instance."""
        if not sync.embedding_model_connection_id:
            return LocalText2Vec()
        return LocalText2Vec()  # TODO: Handle other embedding models

    async def _get_destination(self, sync: schemas.Sync, embedding_model):
        """Get the destination instance."""
        if not sync.destination_connection_id:
            return await WeaviateDestination.create(sync.id, embedding_model)
        return await WeaviateDestination.create(
            sync.id, embedding_model
        )  # TODO: Handle other destinations

    async def generate_white_label_auth_url(
        self,
        db: AsyncSession,
        white_label_id: UUID,
        current_user: schemas.User,
    ) -> str:
        """Generate OAuth2 authorization URL for a white label integration."""
        # Get white label config
        white_label = await crud.white_label.get(db, white_label_id, current_user)
        if not white_label:
            raise NotFoundException("White label integration not found")

        # Get source settings
        source = await crud.source.get_by_short_name(db, white_label.source_id)
        if not source:
            raise NotFoundException("Source not found")

        # Get integration settings
        settings = integration_settings.get_integration_settings(source.short_name)
        if not settings:
            raise NotFoundException("Integration settings not found")

        if source.auth_type not in [
            AuthType.oauth2,
            AuthType.oauth2_with_refresh,
            AuthType.oauth2_with_refresh_rotating,
        ]:
            raise ValueError("Source does not support OAuth2")

        # Override OAuth2 settings with white label config
        white_label_settings = settings.model_copy()
        white_label_settings.client_id = white_label.client_id

        # Generate auth URL using the white label client ID
        if white_label.source_id == "trello":
            return oauth2_service.generate_auth_url_for_trello(client_id=white_label.client_id)

        return oauth2_service.generate_auth_url(white_label_settings)


sync_service = SyncService()
