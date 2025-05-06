"""CRUD operations for source connections."""

from typing import List, Optional
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from airweave.core.shared_models import SourceConnectionStatus
from airweave.models.source_connection import SourceConnection
from airweave.schemas.source_connection import SourceConnectionCreate, SourceConnectionUpdate
from airweave.schemas.user import User

from ._base import CRUDBase


class CRUDSourceConnection(
    CRUDBase[SourceConnection, SourceConnectionCreate, SourceConnectionUpdate]
):
    """CRUD operations for source connections."""

    async def get_all_for_user(
        self, db: AsyncSession, *, current_user: User, skip: int = 0, limit: int = 100
    ) -> List[SourceConnection]:
        """Get all source connections for the current user.

        Args:
            db: The database session
            current_user: The current user
            skip: The number of connections to skip
            limit: The number of connections to return

        Returns:
            A list of source connections
        """
        query = (
            select(self.model)
            .where(self.model.organization_id == current_user.organization_id)
            .offset(skip)
            .limit(limit)
        )
        result = await db.execute(query)
        return list(result.scalars().all())

    async def get_active_for_user(
        self, db: AsyncSession, *, current_user: User, skip: int = 0, limit: int = 100
    ) -> List[SourceConnection]:
        """Get all active source connections for the current user.

        Args:
            db: The database session
            current_user: The current user
            skip: The number of connections to skip
            limit: The number of connections to return

        Returns:
            A list of active source connections
        """
        query = (
            select(self.model)
            .where(
                self.model.organization_id == current_user.organization_id,
                self.model.status == SourceConnectionStatus.ACTIVE,
            )
            .offset(skip)
            .limit(limit)
        )
        result = await db.execute(query)
        return list(result.scalars().all())

    async def get_by_sync_id(
        self, db: AsyncSession, *, sync_id: UUID, current_user: User
    ) -> Optional[SourceConnection]:
        """Get a source connection by sync ID.

        Args:
            db: The database session
            sync_id: The ID of the sync
            current_user: The current user

        Returns:
            The source connection for the sync
        """
        query = select(self.model).where(
            self.model.sync_id == sync_id,
            self.model.organization_id == current_user.organization_id,
        )
        result = await db.execute(query)
        return result.scalar_one_or_none()

    async def get_by_credential_id(
        self, db: AsyncSession, *, credential_id: UUID, current_user: User
    ) -> Optional[SourceConnection]:
        """Get a source connection by integration credential ID.

        Args:
            db: The database session
            credential_id: The ID of the integration credential
            current_user: The current user

        Returns:
            The source connection for the credential
        """
        query = select(self.model).where(
            self.model.integration_credential_id == credential_id,
            self.model.organization_id == current_user.organization_id,
        )
        result = await db.execute(query)
        return result.scalar_one_or_none()

    async def get_with_related(
        self, db: AsyncSession, *, id: UUID, current_user: User
    ) -> Optional[SourceConnection]:
        """Get a source connection with its related objects.

        Args:
            db: The database session
            id: The ID of the source connection
            current_user: The current user

        Returns:
            The source connection with related objects
        """
        query = (
            select(self.model)
            .options(
                joinedload(self.model.sync),
                joinedload(self.model.integration_credential),
                joinedload(self.model.dag),
                joinedload(self.model.collection),
            )
            .where(
                self.model.id == id,
                self.model.organization_id == current_user.organization_id,
            )
        )
        result = await db.execute(query)
        return result.scalar_one_or_none()

    async def update_status(
        self,
        db: AsyncSession,
        *,
        id: UUID,
        status: SourceConnectionStatus,
        current_user: User,
    ) -> Optional[SourceConnection]:
        """Update the status of a source connection.

        Args:
            db: The database session
            id: The ID of the source connection
            status: The new status
            current_user: The current user

        Returns:
            The updated source connection
        """
        source_connection = await self.get(db, id=id, current_user=current_user)
        if not source_connection:
            return None

        update_data = {"status": status}
        return await self.update(
            db, db_obj=source_connection, obj_in=update_data, current_user=current_user
        )


source_connection = CRUDSourceConnection(SourceConnection)
