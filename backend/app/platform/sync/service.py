"""Module for data synchronization."""

import asyncio
from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app import crud, schemas
from app.core import credentials
from app.core.exceptions import NotFoundException
from app.core.logging import logger
from app.db.unit_of_work import UnitOfWork
from app.platform.auth.schemas import AuthType
from app.platform.auth.services import oauth2_service
from app.platform.destinations.weaviate import WeaviateDestination
from app.platform.embedding_models.local_text2vec import LocalText2Vec
from app.platform.entities._base import ChunkEntity, FileEntity
from app.platform.locator import resource_locator
from app.platform.sync.context import SyncContext
from app.platform.sync.pubsub import sync_pubsub
from app.platform.sync.router import EntityRouter
from app.platform.transformers.default_file_chunker import file_chunker


class SyncService:
    """Main service for data synchronization."""

    async def create(
        self,
        db: AsyncSession,
        sync: schemas.Sync,
        current_user: schemas.User,
        uow: UnitOfWork,
    ) -> schemas.Sync:
        """Create a new sync."""
        sync = await crud.sync.create(db=db, obj_in=sync, current_user=current_user, uow=uow)
        dag = await crud.sync_dag.
        return sync

    async def run(
        self,
        sync: schemas.Sync,
        sync_job: schemas.SyncJob,
        dag: schemas.SyncDag,
        current_user: schemas.User,
    ) -> schemas.Sync:
        """Run a sync with the new DAG-based routing."""
        async with AsyncSession() as db:
            # Get DAG definition
            dag = await crud.sync_dag_definition.get(
                db=db, id=sync.dag_id, current_user=current_user
            )
            if not dag:
                raise ValueError("No DAG definition found")

            # Initialize router
            router = EntityRouter(
                dag=dag, db=db, sync_id=sync.id, organization_id=sync.organization_id
            )

            # Get source node and initialize source
            source_node = self._get_source_node(dag)
            source = await self._initialize_source(source_node)

            # Initialize progress tracking
            sync_progress = SyncProgress()

            # Stream and process entities
            async for entity in source.generate_entities():
                async for result in router.process_entity(source_node, entity):
                    # Update progress based on action
                    if result.action == "insert":
                        sync_progress.inserted += 1
                        # Create new DB entity
                        db_entity = await crud.entity.create(
                            db=db,
                            obj_in=schemas.EntityCreate(
                                sync_id=sync.id,
                                entity_id=result.entity.entity_id,
                                hash=result.entity.hash,
                            ),
                            organization_id=sync.organization_id,
                        )
                        # Update entity with DB ID
                        result.entity.db_entity_id = db_entity.id

                    elif result.action == "update":
                        sync_progress.updated += 1
                        # Update existing DB entity
                        await crud.entity.update(
                            db=db,
                            db_obj=result.db_entity,
                            obj_in=schemas.EntityUpdate(hash=result.entity.hash),
                        )
                        # Update entity with DB ID
                        result.entity.db_entity_id = result.db_entity.id

                    # Publish progress
                    await sync_pubsub.publish(sync_job.id, sync_progress)

            return sync

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

        if source_model.auth_type == AuthType.none:
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

    async def _process_file(self, file: FileEntity) -> list[FileEntity | ChunkEntity]:
        """Process a single file entity using the file chunker."""
        entities: list[FileEntity | ChunkEntity] = []
        try:
            async for entity in file_chunker(file):
                entities.append(entity)
        except Exception as e:
            logger.error(f"Error processing file {file.name}: {str(e)}")
            return None
        return entities


sync_service = SyncService()
