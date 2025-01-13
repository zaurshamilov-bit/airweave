"""Base CRUD class for tables with organization context."""

from typing import Generic, Optional, Type, TypeVar
from uuid import UUID

from pydantic import BaseModel
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundException
from app.db.unit_of_work import UnitOfWork
from app.models._base import Base

ModelType = TypeVar("ModelType", bound=Base)
CreateSchemaType = TypeVar("CreateSchemaType", bound=BaseModel)
UpdateSchemaType = TypeVar("UpdateSchemaType", bound=BaseModel)


class CRUDBaseOrganization(Generic[ModelType, CreateSchemaType, UpdateSchemaType]):
    """Base class for CRUD operations in organization context."""

    def __init__(self, model: Type[ModelType]):
        """Initialize the CRUD object.

        Args:
        ----
            model (Type[ModelType]): The model to be used in the CRUD operations.

        """
        self.model = model

    async def get(self, db: AsyncSession, id: UUID, organization_id: UUID) -> Optional[ModelType]:
        """Get a single object by ID.

        Args:
        ----
            db (AsyncSession): The database session.
            id (UUID): The UUID of the object to get.
            organization_id (UUID): The UUID of the organization.

        Returns:
        -------
            Optional[ModelType]: The object with the given ID.

        """
        result = await db.execute(
            select(self.model).where(
                self.model.id == id, self.model.organization_id == organization_id
            )
        )
        return result.unique().scalar_one_or_none()

    async def get_all_for_organization(
        self, db: AsyncSession, organization_id: UUID, *, skip: int = 0, limit: int = 100
    ) -> list[ModelType]:
        """Get all objects for an organization.

        Args:
        ----
            db (AsyncSession): The database session.
            organization_id (UUID): The UUID of the organization.
            skip (int): The number of objects to skip.
            limit (int): The number of objects to return.
        """
        query = (
            select(self.model)
            .where(self.model.organization_id == organization_id)
            .offset(skip)
            .limit(limit)
        )
        result = await db.execute(query)
        return list(result.unique().scalars().all())

    async def create(
        self,
        db: AsyncSession,
        *,
        obj_in: CreateSchemaType,
        organization_id: UUID,
        uow: Optional[UnitOfWork] = None,
    ) -> ModelType:
        """Create a new object for a given schema type and organization context.

        Args:
        ----
            db (AsyncSession): The database session.
            obj_in (CreateSchemaType): The object to create.
            organization_id (UUID): The UUID of the organization.
            uow (Optional[UnitOfWork]): The unit of work to use for the transaction.

        Returns:
        -------
            ModelType: The created object.

        """
        obj_in_data = obj_in.model_dump()
        obj_in_data["organization_id"] = organization_id
        db_obj = self.model(**obj_in_data)
        db.add(db_obj)
        if not uow:
            await db.commit()
            await db.refresh(db_obj)
        return db_obj

    async def update(
        self,
        db: AsyncSession,
        db_obj: ModelType,
        obj_in: UpdateSchemaType,
        organization_id: UUID,
        uow: Optional[UnitOfWork] = None,
    ) -> ModelType:
        """Update an existing object in db for a given schema type and organization context.

        Args:
        ----
            db (AsyncSession): The database session.
            db_obj (ModelType): The object to update.
            obj_in (UpdateSchemaType): The object to update with.
            organization_id (UUID): The UUID of the organization.
            uow (Optional[UnitOfWork]): The unit of work to use for the transaction.

        Returns:
        -------
            ModelType: The updated object.

        """
        obj_in = obj_in.model_dump(exclude_unset=True)

        for key, value in obj_in.items():
            setattr(db_obj, key, value) if hasattr(db_obj, key) else None

        db.add(db_obj)
        if not uow:
            await db.commit()
            await db.refresh(db_obj)
        return db_obj

    async def remove(
        self, db: AsyncSession, id: UUID, organization_id: UUID, uow: Optional[UnitOfWork] = None
    ) -> None:
        """Delete an object from db for a given schema type and organization context.

        Args:
        ----
            db (AsyncSession): The database session.
            id (UUID): The UUID of the object to delete.
            organization_id (UUID): The UUID of the organization.
            uow (Optional[UnitOfWork]): The unit of work to use for the transaction.
        """
        stmt = (
            delete(self.model)
            .where(self.model.id == id, self.model.organization_id == organization_id)
            .execution_options(synchronize_session=False)
        )
        result = await db.execute(stmt)
        if result.rowcount == 0:
            raise NotFoundException(f"{self.model.__name__} not found")

        if not uow:
            await db.commit()
