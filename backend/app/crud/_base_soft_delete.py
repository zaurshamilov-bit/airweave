"""Base CRUD class for soft-deleted tables."""

from datetime import datetime
from typing import Generic, Optional, Type, TypeVar
from uuid import UUID

from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models._base import Base

ModelType = TypeVar("ModelType", bound=Base)
CreateSchemaType = TypeVar("CreateSchemaType", bound=BaseModel)
UpdateSchemaType = TypeVar("UpdateSchemaType", bound=BaseModel)


class CRUDBaseSoftDelete(Generic[ModelType, CreateSchemaType, UpdateSchemaType]):
    """CRUD base class for public, soft-deleted tables."""

    def __init__(self, model: Type[ModelType]):
        """CRUD object with default methods for soft-deleted tables.

        Args:
        ----
            model (Type[ModelType]): The model to be used in the CRUD operations.

        """
        self.model = model

    async def get(self, db: AsyncSession, id: UUID) -> Optional[ModelType]:
        """Get a single object by ID, excluding soft deleted ones.

        Args:
        ----
            db (AsyncSession): The database session.
            id (UUID): The UUID of the object to get.

        Returns:
        -------
            Optional[ModelType]: The object with the given ID.

        """
        result = await db.execute(
            select(self.model).where(self.model.id == id, self.model.deleted_at is None)
        )
        return result.unique().scalar_one_or_none()

    async def get_multi(
        self, db: AsyncSession, *, skip: int = 0, limit: int = 100
    ) -> list[ModelType]:
        """Get multiple objects, excluding soft deleted ones.

        Args:
        ----
            db (AsyncSession): The database session.
            skip (int): The number of objects to skip.
            limit (int): The number of objects to return.

        Returns:
        -------
            List[ModelType]: A list of objects.

        """
        result = await db.execute(
            select(self.model).where(self.model.deleted_at is None).offset(skip).limit(limit)
        )
        return result.scalars().unique().all()

    async def create(self, db: AsyncSession, *, obj_in: CreateSchemaType) -> ModelType:
        """Create a new object.

        Args:
        ----
            db (AsyncSession): The database session.
            obj_in (CreateSchemaType): The object to create.

        Returns:
        -------
            ModelType: The created object.

        """
        if not isinstance(obj_in, dict):
            obj_in = obj_in.model_dump()
        db_obj = self.model(**obj_in)
        db.add(db_obj)
        await db.commit()
        await db.refresh(db_obj)
        return db_obj

    async def remove(self, db: AsyncSession, *, id: UUID) -> Optional[ModelType]:
        """Soft delete an object.

        Args:
        ----
            db (AsyncSession): The database session.
            id (UUID): The UUID of the object to delete.

        Returns:
        -------
            Optional[ModelType]: The soft deleted object.

        """
        result = await db.execute(select(self.model).where(self.model.id == id))
        db_obj = result.unique().scalar_one_or_none()

        if db_obj:
            db_obj.deleted_at = datetime.utcnow()
            db.add(db_obj)
            await db.commit()
            await db.refresh(db_obj)
        return db_obj
