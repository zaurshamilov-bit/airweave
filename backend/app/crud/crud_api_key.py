"""CRUD operations for the APIKey model."""

import hashlib
import secrets
from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

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


api_key = CRUDAPIKey(APIKey)
