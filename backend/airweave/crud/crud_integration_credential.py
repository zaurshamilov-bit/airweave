"""CRUD operations for integration credentials."""

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from airweave.crud._base_organization import CRUDBaseOrganization
from airweave.models.integration_credential import IntegrationCredential
from airweave.schemas.integration_credential import (
    IntegrationCredentialCreateEncrypted,
    IntegrationCredentialUpdate,
)


class CRUDIntegrationCredential(
    CRUDBaseOrganization[
        IntegrationCredential, IntegrationCredentialCreateEncrypted, IntegrationCredentialUpdate
    ]
):
    """CRUD operations for integration credentials."""

    async def get_by_short_name_and_sync_id(
        self, db: AsyncSession, integration_short_name: str, sync_id: UUID
    ) -> IntegrationCredential | None:
        """Get credentials by integration short name and sync ID.

        For example: "asana" and a sync ID. This should be unique.

        Args:
            db (AsyncSession): The database session.
            integration_short_name (str): The short name of the integration.
            sync_id (UUID): The ID of the sync.

        Returns:
            IntegrationCredential | None: The credentials for the sync.
        """
        stmt = select(IntegrationCredential).where(
            IntegrationCredential.integration_short_name == integration_short_name,
            IntegrationCredential.sync_id == sync_id,
        )
        db_obj = await db.execute(stmt)

        return db_obj.scalar_one_or_none()


integration_credential = CRUDIntegrationCredential(IntegrationCredential)
