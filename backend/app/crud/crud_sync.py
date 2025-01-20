"""CRUD operations for syncs."""

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.crud._base import CRUDBase
from app.models.sync import Sync
from app.schemas.sync import SyncCreate, SyncUpdate


class CRUDSync(CRUDBase[Sync, SyncCreate, SyncUpdate]):
    """CRUD operations for syncs."""

    async def get_all_for_white_label(self, db: AsyncSession, white_label_id: UUID) -> list[Sync]:
        """Get sync by white label ID."""
        stmt = select(Sync).where(Sync.white_label_id == white_label_id)
        result = await db.execute(stmt)
        return result.scalars().unique().all()


sync = CRUDSync(Sync)
