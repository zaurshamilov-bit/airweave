"""Base CRUD class for public tables."""

from typing import Any, Generic, Optional, Type, TypeVar, Union
from uuid import UUID

from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.base_class import Base

ModelType = TypeVar("ModelType", bound=Base)
CreateSchemaType = TypeVar("CreateSchemaType", bound=BaseModel)
UpdateSchemaType = TypeVar("UpdateSchemaType", bound=BaseModel)


class CRUDBaseSystem(Generic[ModelType, CreateSchemaType, UpdateSchemaType]):
    """CRUD base class for system tables.

    Implements CRUD methods without user or organization context.
    """

    def __init__(self, model: Type[ModelType]):
        """CRUD object with default methods for public tables.

        Args:
        ----
            model (Type[ModelType]): The model to be used in the CRUD operations.

        """
        self.model = model

    async def get(self, db: AsyncSession, id: UUID) -> Optional[ModelType]:
        """Get a single object by ID.

        Args:
        ----
            db (AsyncSession): The database session.
            id (UUID): The UUID of the object to get.

        Returns:
        -------
            Optional[ModelType]: The object with the given ID.

        """
        result = await db.execute(select(self.model).where(self.model.id == id))
        return result.unique().scalar_one_or_none()

    async def get_multi(
        self, db: AsyncSession, *, skip: int = 0, limit: int = 100
    ) -> list[ModelType]:
        """Get multiple objects.

        Args:
        ----
            db (AsyncSession): The database session.
            skip (int): The number of objects to skip.
            limit (int): The number of objects to return.

        Returns:
        -------
            List[ModelType]: A list of objects.

        """
        result = await db.execute(select(self.model).offset(skip).limit(limit))
        return list(result.unique().scalars().all())

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

    async def create_many(
        self, db: AsyncSession, objs_in: list[CreateSchemaType]
    ) -> list[ModelType]:
        """Create multiple objects.

        Args:
        ----
            db (AsyncSession): The database session.
            objs_in (list[CreateSchemaType]): The objects to create.

        Returns:
        -------
            list[ModelType]: The created objects.

        """
        db_objs = [self.model(**obj_in.model_dump()) for obj_in in objs_in]
        db.add_all(db_objs)
        await db.commit()
        for db_obj in db_objs:
            await db.refresh(db_obj)
        return db_objs

    async def update(
        self,
        db: AsyncSession,
        *,
        db_obj: ModelType,
        obj_in: Union[UpdateSchemaType, dict[str, Any]],
    ) -> ModelType:
        """Update an object.

        Args:
        ----
            db (AsyncSession): The database session.
            db_obj (ModelType): The object to update.
            obj_in (Union[UpdateSchemaType, Dict[str, Any]]): The new object data.

        Returns:
        -------
            ModelType: The updated object

        """
        if not isinstance(obj_in, dict):
            obj_in = obj_in.model_dump(exclude_unset=True)

        for key, value in obj_in.items():
            setattr(db_obj, key, value) if hasattr(db_obj, key) else None
        db.add(db_obj)
        await db.commit()
        await db.refresh(db_obj)
        return db_obj

    async def remove(self, db: AsyncSession, *, id: UUID) -> Optional[ModelType]:
        """Delete an object.

        Args:
        ----
            db (AsyncSession): The database session.
            id (UUID): The UUID of the object to delete.

        Returns:
        -------
            Optional[ModelType]: The deleted object.

        """
        result = await db.execute(select(self.model).where(self.model.id == id))
        db_obj = result.unique().scalar_one_or_none()
        if db_obj is None:
            return None

        await db.delete(db_obj)
        await db.commit()
        return db_obj
