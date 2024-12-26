"""The CRUD operations for the User model."""

from typing import Any, Optional
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.crud._base import CRUDBase
from app.models.user import User
from app.schemas.user import UserCreate, UserUpdate


class CRUDUser(CRUDBase[User, UserCreate, UserUpdate]):
    """CRUD operations for the User model."""

    async def get_by_email(self, db: AsyncSession, *, email: str) -> Optional[User]:
        """Get a user by email.

        Important: this method is not part of the regular CRUD operations.
        This is a custom method for getting a user by email, that does not
        require a current user. Use responsibly.

        Args:
        ----
            db (AsyncSession): The database session.
            email (str): The email of the user to get.

        Returns:
        -------
            Optional[User]: The user with the given email.

        """
        stmt = select(User).where(User.email == email)
        result = await db.execute(stmt)
        return result.scalar_one_or_none()

    async def get(self, db: AsyncSession, id: UUID, current_user: User) -> Optional[User]:
        """Get a single object by ID.

        Args:
        ----
            db (AsyncSession): The database session.
            id (UUID): The UUID of the object to get. Doesn't require strict typing.
            current_user (User): The current user.

        Raises:
        ------
            NotImplementedError: This method is not implemented yet.

        """
        raise NotImplementedError("This method is not implemented yet.")

    async def get_multi(self, db: AsyncSession, skip: int = 0, limit: int = 100) -> list[User]:
        """Get multiple objects.

        WARNING: This method is not secure and should not be used in production.
        It is only used for MLOps and testing purposes.

        TODO: Implement proper security measures through admin roles.

        Args:
        ----
            db (AsyncSession): The database session.
            skip (int): The number of objects to skip.
            limit (int): The number of objects to return.

        Returns:
        -------
            list[User]: A list of users.

        """
        raise NotImplementedError("This method is not implemented yet.")

    async def remove(self, db: AsyncSession, *, id: UUID, current_user: User) -> Optional[User]:
        """Remove an object by ID.

        Args:
        ----
            db (AsyncSession): The database session.
            id (UUID): The UUID of the object to remove. Doesn't require strict typing.
            current_user (User): The current user.

        Raises:
        ------
            NotImplementedError: This method is not implemented.

        """
        raise NotImplementedError("This method is not implemented.")

    async def update(
        self,
        db: AsyncSession,
        *,
        db_obj: User,
        obj_in: UserUpdate | dict[str, Any],
        current_user: User
    ) -> User:
        """Update an object.

        Args:
        ----
            db (AsyncSession): The database session.
            db_obj (User): The object to update.
            obj_in (UserUpdate | dict[str, Any]): The updated object.
            current_user (User): The current user.

        Raises:
        ------
            NotImplementedError: This method is not implemented.

        """
        raise NotImplementedError("This method is not implemented.")


user = CRUDUser(User)
