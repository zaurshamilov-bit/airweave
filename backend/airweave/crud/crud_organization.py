"""CRUD operations for the organization model."""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from airweave.crud._base import CRUDBase
from airweave.models.organization import Organization
from airweave.schemas.organization import OrganizationCreate, OrganizationUpdate


class CRUDOrganization(CRUDBase[Organization, OrganizationCreate, OrganizationUpdate]):
    """CRUD operations for the organization model."""

    async def get_by_name(self, db: AsyncSession, name: str) -> Organization | None:
        """Get an organization by its name."""
        stmt = select(Organization).where(Organization.name == name)
        result = await db.execute(stmt)
        return result.scalar_one_or_none()


organization = CRUDOrganization(Organization)
