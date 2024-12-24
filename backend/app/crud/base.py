"""This module contains the base class for CRUD operations."""

from typing import Any, Generic, Optional, Type, TypeVar, Union
from uuid import UUID

from app import models, schemas
from app.core.exceptions import ImmutableFieldError, NotFoundException, PermissionException
from app.db.base_class import Base
from app.schemas import User
from pydantic import BaseModel
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

ModelType = TypeVar("ModelType", bound=Base)
CreateSchemaType = TypeVar("CreateSchemaType", bound=BaseModel)
UpdateSchemaType = TypeVar("UpdateSchemaType", bound=BaseModel)


class CRUDBase(Generic[ModelType, CreateSchemaType, UpdateSchemaType]):
    """This class is the repository object with default methods.

    Implements methods like Create, Read, Update, Delete (CRUD) in user context.
    """

    def __init__(self, model: Type[ModelType]):
        """CRUD object with default methods to Create, Read, Update, Delete (CRUD) in user context.

        Args:
            model (Type[ModelType]): The model to be used in the CRUD operations.
        """
        self.model = model

    async def get(self, db: AsyncSession, id: UUID, current_user: User) -> Optional[ModelType]:
        """Get a single object by ID.

        Args:
            db (AsyncSession): The database session.
            id (UUID): The UUID of the object to get. Doesn't require strict typing.
            current_user (User): The current user.

        Returns:
            Optional[ModelType]: The object with the given ID.
        """
        query = select(self.model).where(self.model.id == id)
        result = await db.execute(query)
        db_obj = result.unique().scalar_one_or_none()

        if db_obj is None:
            return None

        self._validate_if_user_has_permission(db_obj, current_user)

        return db_obj

    async def get_multi(
        self, db: AsyncSession, current_user: User, *, skip: int = 0, limit: int = 100
    ) -> list[ModelType]:
        """Get multiple objects.

        Args:
            db (AsyncSession): The database session.
            current_user (User): The current user.
            skip (int): The number of objects to skip.
            limit (int): The number of objects to return.

        Returns:
            List[ModelType]: A list of objects.
        """
        query = (
            select(self.model)
            .where(
                (self.model.created_by_email == current_user.email)
                | (self.model.modified_by_email == current_user.email)
            )
            .order_by(desc(self.model.created_date))
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
        current_assistant: Optional[schemas.Assistant] = None,
    ) -> ModelType:
        """Create a new object in db for a given schema type and optional user or assistant context.

        Args:
            db (AsyncSession): The database session.
            obj_in (CreateSchemaType): The object to create.
            current_user (User): The current user.
            current_assistant: (schemas.Assistant, optional): The assistant to associate
                with the object.

        Returns:
            ModelType: The created object.
        """
        if not isinstance(obj_in, dict):
            obj_in = obj_in.model_dump()
        db_obj = self.model(**obj_in)  # type: ignore

        if current_user:
            db_obj.created_by_email = current_user.email
            db_obj.modified_by_email = current_user.email

        if current_assistant or self._model_assistant_field(db_obj):
            db_obj = await self._set_assistant_field_if_present(
                db, db_obj, current_user, current_assistant
            )

        db.add(db_obj)
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
        current_assistant: Optional[schemas.Assistant] = None,
    ) -> ModelType:
        """Update an object.

        Args:
            db (AsyncSession): The database session.
            db_obj (ModelType): The object to update.
            obj_in (Union[UpdateSchemaType, Dict[str, Any]]): The new object data.
            current_user (User): The current user.
            current_assistant (Optional[schemas.Assistant]): The assistant to associate with
                the object to be updated.

        Returns:
            ModelType: The updated object
        """
        if not isinstance(obj_in, dict):
            obj_in = obj_in.model_dump(exclude_unset=True)

        self._validate_if_user_has_permission(db_obj, current_user)
        self._validate_no_update_of_immutable_attributes(db_obj, obj_in)
        self._validate_assistant_permission(db_obj, current_assistant)

        for key, value in obj_in.items():
            setattr(db_obj, key, value) if hasattr(db_obj, key) else None
        db_obj.modified_by_email = current_user.email

        db.add(db_obj)
        await db.commit()
        await db.refresh(db_obj)
        return db_obj

    async def remove(
        self, db: AsyncSession, *, id: UUID, current_user: User
    ) -> Optional[ModelType]:
        """Delete an object.

        Args:
            db (AsyncSession): The database session.
            id (UUID): The UUID of the object to delete.
            current_user (User): The current user.

        Returns:
            Optional[ModelType]: The deleted object.

        Raises:
            NotFoundException: If the object is not found.
        """
        query = select(self.model).where(self.model.id == id)
        result = await db.execute(query)
        db_obj = result.unique().scalar_one_or_none()

        if db_obj is None:
            raise NotFoundException(f"{self.model.__name__} not found")

        self._validate_if_user_has_permission(db_obj, current_user)

        await db.delete(db_obj)
        await db.commit()
        return db_obj

    async def _get_default_assistant_for_user(
        self, db: AsyncSession, user: User
    ) -> Optional[schemas.Assistant]:
        """Get the default assistant for the user.

        Args:
            db (AsyncSession): The database session.
            user (User): The user.

        Returns:
            Optional[schemas.Assistant]: The default assistant for the user.
        """
        query = select(models.Assistant).where(
            models.Assistant.created_by_email == user.email,
            models.Assistant.is_default_for_user == True,
        )
        result = await db.execute(query)
        return result.scalar_one_or_none()

    async def _set_assistant_field_if_present(
        self,
        db: AsyncSession,
        db_obj: ModelType,
        current_user: schemas.User,
        current_assistant: Optional[schemas.Assistant] = None,
    ) -> ModelType:
        """Set the assistant field if it is present in the model.

        Args:
            db (AsyncSession): The database session.
            db_obj (ModelType): The object to update.
            current_user (schemas.User): The current user.
            current_assistant (Optional[schemas.Assistant]): The assistant to associate with
                the object.

        Returns:
            ModelType: The updated object.

        Raises:
            NotFoundException: If no default assistant is found for the user.
            ValueError: If the model does not have an assistant field.
        """
        assistant_field = self._model_assistant_field(db_obj)

        if assistant_field:
            assistant_to_use = current_assistant
            if not assistant_to_use:
                assistant_to_use = await self._get_default_assistant_for_user(db, current_user)
                if not assistant_to_use:
                    raise NotFoundException("No default assistant found for the user.")
            setattr(db_obj, assistant_field, assistant_to_use.id)
        elif current_assistant is not None:
            raise ValueError(
                f"Model {self.model.__name__} does not have an 'assistant' or 'assistant_id' field."
            )
        return db_obj

    def _validate_assistant_permission(
        self, db_obj: ModelType, current_assistant: Optional[schemas.Assistant] = None
    ) -> None:
        """Validate that the current assistant has permission to access the object.

        Args:
            db_obj (ModelType): The object to check.
            current_assistant (schemas.Assistant): The current assistant.
        """
        assistant_field = self._model_assistant_field(db_obj)
        if assistant_field and current_assistant:
            self._validate_that_current_assistant_is_the_same_as_db_obj_assistant(
                db_obj, assistant_field, current_assistant
            )

    def _validate_if_user_has_permission(self, db_obj: ModelType, current_user: User) -> None:
        """Validate if the user has permission to access the object.

        Args:
            db_obj (ModelType): The object to check.
            current_user (User): The current user.

        Raises:
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
            db_obj (ModelType): The existing object in the database.
            obj_in (Union[UpdateSchemaType, Dict[str, Any]]): The new data intended for update.
            extra_immutable_fields (Optional[List[str]]): Additional fields that should be treated
                as immutable.

        Raises:
            ImmutableFieldError: If an immutable field is being modified.
        """
        immutable_fields = ["created_date", "created_by_email"]

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

    def _model_assistant_field(self, db_obj: ModelType) -> str | None:
        """Get the assistant field name of the model if it exists.

        Args:
            db_obj (ModelType): The object to check.

        Returns:
            str | None: The assistant field name if it exists, otherwise None.
        """
        assistant_field = None
        if hasattr(db_obj, "assistant"):
            assistant_field = "assistant"
        elif hasattr(db_obj, "assistant_id"):
            assistant_field = "assistant_id"
        return assistant_field

    def _validate_that_current_assistant_is_the_same_as_db_obj_assistant(
        self, db_obj: ModelType, assistant_field: str, current_assistant: schemas.Assistant
    ) -> None:
        """Validate that the current assistant is the same as the db_obj's assistant.

        Args:
            db_obj (ModelType): The object to check.
            assistant_field (str): The assistant field name (can be 'assistant' or 'assistant_id').
            current_assistant (schemas.Assistant): The current assistant.

        Raises:
            PermissionException: If the current assistant is not the same as the db_obj's assistant.
        """
        if getattr(db_obj, assistant_field) != current_assistant.id:
            raise PermissionException("User does not have the right to access this object")
