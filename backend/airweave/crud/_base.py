"""Base class for CRUD operations."""

from typing import Any, Generic, Optional, Type, TypeVar, Union
from uuid import UUID

from pydantic import BaseModel
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from airweave.core.exceptions import ImmutableFieldError, NotFoundException, PermissionException
from airweave.db.unit_of_work import UnitOfWork
from airweave.models._base import Base
from airweave.schemas import User

ModelType = TypeVar("ModelType", bound=Base)
CreateSchemaType = TypeVar("CreateSchemaType", bound=BaseModel)
UpdateSchemaType = TypeVar("UpdateSchemaType", bound=BaseModel)


class CRUDBase(Generic[ModelType, CreateSchemaType, UpdateSchemaType]):
    """Base class for CRUD operations.

    Implements methods like Create, Read, Update, Delete (CRUD) in user context.
    """

    def __init__(self, model: Type[ModelType]):
        """Initialize the CRUD object.

        Args:
        ----
            model (Type[ModelType]): The model to be used in the CRUD operations.

        """
        self.model = model

    async def get(self, db: AsyncSession, id: UUID, current_user: User) -> Optional[ModelType]:
        """Get a single object by ID.

        Args:
        ----
            db (AsyncSession): The database session.
            id (UUID): The UUID of the object to get. Doesn't require strict typing.
            current_user (User): The current user.

        Returns:
        -------
            Optional[ModelType]: The object with the given ID.

        """
        query = select(self.model).where(self.model.id == id)
        result = await db.execute(query)
        db_obj = result.unique().scalar_one_or_none()

        if db_obj is None:
            return None

        self._validate_if_user_has_permission(db_obj, current_user)

        return db_obj

    async def get_all_for_user(
        self, db: AsyncSession, current_user: User, *, skip: int = 0, limit: int = 100
    ) -> list[ModelType]:
        """Get multiple objects.

        Args:
        ----
            db (AsyncSession): The database session.
            current_user (User): The current user.
            skip (int): The number of objects to skip.
            limit (int): The number of objects to return.

        Returns:
        -------
            List[ModelType]: A list of objects.

        """
        query = (
            select(self.model)
            .where(
                (self.model.created_by_email == current_user.email)
                | (self.model.modified_by_email == current_user.email)
            )
            .order_by(desc(self.model.created_at))
            .offset(skip)
            .limit(limit)
        )
        result = await db.execute(query)
        return list(result.unique().scalars().all())

    async def get_all_for_organization(
        self, db: AsyncSession, organization_id: UUID, *, skip: int = 0, limit: int = 100
    ) -> list[ModelType]:
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
        current_user: User = None,
        uow: Optional[UnitOfWork] = None,
    ) -> ModelType:
        """Create a new object in db for a given schema type and optional user or assistant context.

        Args:
        ----
            db (AsyncSession): The database session.
            obj_in (CreateSchemaType): The object to create.
            current_user (User): The current user.
            uow (Optional[UnitOfWork]): The unit of work to use for the transaction.

        Returns:
        -------
            ModelType: The created object.

        """
        if not isinstance(obj_in, dict):
            obj_in = obj_in.model_dump(exclude_unset=True)
        db_obj = self.model(**obj_in)  # type: ignore

        if current_user:
            db_obj.created_by_email = current_user.email
            db_obj.modified_by_email = current_user.email
            db_obj.organization_id = current_user.organization_id

        db.add(db_obj)
        if not uow:
            await db.commit()
            await db.refresh(db_obj)
        return db_obj

    async def update(
        self,
        db: AsyncSession,
        *,
        db_obj: ModelType,
        obj_in: Union[UpdateSchemaType, dict[str, Any]],
        current_user: User,
        uow: Optional[UnitOfWork] = None,
    ) -> ModelType:
        """Update an object.

        Args:
        ----
            db (AsyncSession): The database session.
            db_obj (ModelType): The object to update.
            obj_in (Union[UpdateSchemaType, Dict[str, Any]]): The new object data.
            current_user (User): The current user.
            uow (Optional[UnitOfWork]): The unit of work to use for the transaction.

        Returns:
        -------
            ModelType: The updated object

        """
        if not isinstance(obj_in, dict):
            obj_in = obj_in.model_dump(exclude_unset=True)

        self._validate_if_user_has_permission(db_obj, current_user)
        self._validate_no_update_of_immutable_attributes(db_obj, obj_in)

        for key, value in obj_in.items():
            setattr(db_obj, key, value) if hasattr(db_obj, key) else None
        db_obj.modified_by_email = current_user.email

        db.add(db_obj)

        if not uow:
            await db.commit()
            await db.refresh(db_obj)
        return db_obj

    async def remove(
        self,
        db: AsyncSession,
        *,
        id: UUID,
        current_user: User,
        uow: Optional[UnitOfWork] = None,
    ) -> Optional[ModelType]:
        """Delete an object.

        Args:
        ----
            db (AsyncSession): The database session.
            id (UUID): The UUID of the object to delete.
            current_user (User): The current user.
            uow (Optional[UnitOfWork]): The unit of work to use for the transaction.

        Returns:
        -------
            Optional[ModelType]: The deleted object.

        Raises:
        ------
            NotFoundException: If the object is not found.

        """
        query = select(self.model).where(self.model.id == id)
        result = await db.execute(query)
        db_obj = result.unique().scalar_one_or_none()

        if db_obj is None:
            raise NotFoundException(f"{self.model.__name__} not found")

        self._validate_if_user_has_permission(db_obj, current_user)

        await db.delete(db_obj)

        await db.flush()

        if not uow:
            await db.commit()

        return db_obj

    def _validate_if_user_has_permission(self, db_obj: ModelType, current_user: User) -> None:
        """Validate if the user has permission to access the object.

        Args:
        ----
            db_obj (ModelType): The object to check.
            current_user (User): The current user.

        Raises:
        ------
            PermissionException: If the user does not have the right to access the object.

        """
        if (
            db_obj.created_by_email != current_user.email
            and db_obj.modified_by_email != current_user.email
        ):
            raise PermissionException("User does not have the right to access this object")

    def _validate_no_update_of_immutable_attributes(
        self,
        db_obj: ModelType,
        obj_in: UpdateSchemaType | dict,
        extra_immutable_fields: Optional[list[str]] = None,
    ) -> None:
        """Validate that no immutable attributes are being modified.

        Only checks for fields that are already present in the database object.

        Args:
        ----
            db_obj (ModelType): The existing object in the database.
            obj_in (Union[UpdateSchemaType, Dict[str, Any]]): The new data intended for update.
            extra_immutable_fields (Optional[List[str]]): Additional fields that should be treated
                as immutable.

        Raises:
        ------
            ImmutableFieldError: If an immutable field is being modified.

        """
        immutable_fields = ["created_at", "created_by_email"]

        if not isinstance(obj_in, dict):
            obj_in = obj_in.model_dump()

        if extra_immutable_fields:
            immutable_fields.extend(extra_immutable_fields)

        for key in immutable_fields:
            original_value = getattr(db_obj, key, None)
            new_value = obj_in.get(key)

            if original_value is None:
                continue

            if new_value is not None and new_value != original_value:
                raise ImmutableFieldError(key)
