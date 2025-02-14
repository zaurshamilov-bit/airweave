"""CRUD operations for the APIKey model."""

import hashlib
import secrets
from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundException
from app.crud._base import CRUDBase
from app.db.unit_of_work import UnitOfWork
from app.models.api_key import APIKey
from app.schemas import APIKeyCreate, APIKeyUpdate, User


class CRUDAPIKey(CRUDBase[APIKey, APIKeyCreate, APIKeyUpdate]):
    """CRUD operations for the APIKey model."""

    async def create_with_user(
        self,
        db: AsyncSession,
        *,
        obj_in: APIKeyCreate,
        current_user: User,
        uow: Optional[UnitOfWork] = None,
    ) -> APIKey:
        """Create a new API key for a user.

        Args:
        ----
            db (AsyncSession): The database session.
            obj_in (APIKeyCreate): The API key creation data.
            current_user (User): The current user.
            uow (Optional[UnitOfWork]): The unit of work to use for the transaction.

        Returns:
        -------
            APIKey: The created API key.

        """
        key = secrets.token_urlsafe(32)
        hashed_key = hashlib.sha256(key.encode()).hexdigest()
        key_prefix = key[:8]

        expiration_date = obj_in.expiration_date or (
            datetime.now(timezone.utc) + timedelta(days=365)
        )

        db_obj = APIKey(
            key=hashed_key,
            key_prefix=key_prefix,
            created_by_email=current_user.email,
            modified_by_email=current_user.email,
            expiration_date=expiration_date,
        )
        db.add(db_obj)
        if not uow:
            await db.commit()

        # Attach the plain key to the object for the response, this is not stored in the db
        db_obj.plain_key = key
        return db_obj

    async def get_by_key(self, db: AsyncSession, *, key: str) -> Optional[APIKey]:
        """Get an API key by its hashed value.

        Args:
        ----
            db (AsyncSession): The database session
            key (str): The plain API key to look up

        Returns:
        -------
            Optional[APIKey]: The API key if found and valid

        Raises:
        ------
            ValueError: If the API key has expired
            NotFoundException: If the API key is not found
        """
        # Hash the provided key for comparison
        hashed_key = hashlib.sha256(key.encode()).hexdigest()

        # Query for the API key
        query = select(self.model).where(self.model.key == hashed_key)
        result = await db.execute(query)
        db_obj = result.unique().scalar_one_or_none()

        if not db_obj:
            raise NotFoundException("API key not found")

        # Check if the key has expired
        if db_obj.expiration_date and db_obj.expiration_date < datetime.now(timezone.utc):
            raise ValueError("API key has expired")

        return db_obj


api_key = CRUDAPIKey(APIKey)
