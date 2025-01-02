"""CRUD operations for chunks."""

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.crud._base import CRUDBase
from app.models.chunk import Chunk
from app.schemas.chunk import ChunkCreate, ChunkUpdate


class CRUDChunk(CRUDBase[Chunk, ChunkCreate, ChunkUpdate]):
    """CRUD operations for chunks."""

    async def get_by_sync_job(
        self,
        db: AsyncSession,
        sync_job_id: UUID,
    ) -> list[Chunk]:
        """Get all chunks for a specific sync job."""
        stmt = select(Chunk).where(Chunk.sync_job_id == sync_job_id)
        result = await db.execute(stmt)
        return list(result.unique().scalars().all())

    async def anti_get_by_sync_job(
        self,
        db: AsyncSession,
        sync_job_id: UUID,
    ) -> list[Chunk]:
        """Get all chunks for that are not from a specific sync job."""
        stmt = select(Chunk).where(Chunk.sync_job_id != sync_job_id)
        result = await db.execute(stmt)
        return list(result.unique().scalars().all())


chunk = CRUDChunk(Chunk)
