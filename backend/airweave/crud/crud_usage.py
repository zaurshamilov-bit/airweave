"""CRUD operations for Usage model."""

from typing import Optional
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from airweave.crud._base_organization import CRUDBaseOrganization
from airweave.models.usage import Usage
from airweave.schemas.usage import UsageCreate, UsageUpdate


class CRUDUsage(CRUDBaseOrganization[Usage, UsageCreate, UsageUpdate]):
    """CRUD operations for Usage model."""

    async def get_by_organization_id(
        self,
        db: AsyncSession,
        *,
        organization_id: UUID,
    ) -> Optional[Usage]:
        """Get usage record by organization ID.

        Args:
        ----
            db: Database session
            organization_id: The organization ID to get usage for

        Returns:
        -------
            Optional[Usage]: The usage record for the organization, or None if not found
        """
        query = select(self.model).where(self.model.organization_id == organization_id)
        result = await db.execute(query)
        return result.unique().scalar_one_or_none()


# Create singleton instance with track_user=False since Usage doesn't have UserMixin
usage = CRUDUsage(Usage, track_user=False)
