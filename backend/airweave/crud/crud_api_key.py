"""CRUD operations for the APIKey model."""

import secrets
from datetime import datetime, timedelta, timezone
from typing import Optional
from uuid import UUID

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from airweave.core import credentials
from airweave.core.exceptions import NotFoundException
from airweave.crud._base import CRUDBase
from airweave.db.unit_of_work import UnitOfWork
from airweave.models.api_key import APIKey
from airweave.schemas import APIKeyCreate, APIKeyUpdate, User


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
        encrypted_key = credentials.encrypt({"key": key})

        expiration_date = obj_in.expiration_date or (
            datetime.now(timezone.utc) + timedelta(days=180)  # Default to 180 days
        )

        db_obj = APIKey(
            encrypted_key=encrypted_key,
            created_by_email=current_user.email,
            modified_by_email=current_user.email,
            expiration_date=expiration_date,
            # Set the organization_id from the current user
            organization_id=current_user.organization_id,
        )
        db.add(db_obj)
        if not uow:
            await db.commit()
            await db.refresh(db_obj)
        return db_obj

    async def get_all_for_user(
        self, db: AsyncSession, *, skip: int = 0, limit: int = 100, current_user: User
    ) -> list[APIKey]:
        """Get all API keys for a user.

        Args:
        ----
            db (AsyncSession): The database session.
            skip (int): The number of records to skip.
            limit (int): The maximum number of records to return.
            current_user (User): The current user.

        Returns:
        -------
            list[APIKey]: A list of API keys for the user.

        """
        # Get API keys by organization ID
        query = (
            select(self.model)
            .where(self.model.organization_id == current_user.organization_id)
            .offset(skip)
            .limit(limit)
        )
        result = await db.execute(query)
        return list(result.scalars().all())

    async def get(self, db: AsyncSession, id: UUID, current_user: User) -> Optional[APIKey]:
        """Get an API key by ID.

        Args:
        ----
            db (AsyncSession): The database session.
            id (str): The ID of the API key to get.
            current_user (User): The current user.

        Returns:
        -------
            Optional[APIKey]: The API key if found.

        """
        # Get API key by ID and organization ID
        query = select(self.model).where(
            self.model.id == id, self.model.organization_id == current_user.organization_id
        )
        result = await db.execute(query)
        return result.scalars().first()

    async def remove(self, db: AsyncSession, *, id: UUID, current_user: User) -> None:
        """Remove an API key.

        Args:
        ----
            db (AsyncSession): The database session.
            id (UUID): The ID of the API key to remove.
            current_user (User): The current user.

        Returns:
        -------
            None
        """
        # Delete API key by ID and organization ID for security
        stmt = delete(self.model).where(
            self.model.id == id, self.model.organization_id == current_user.organization_id
        )
        await db.execute(stmt)
        await db.commit()

    async def get_by_key(self, db: AsyncSession, *, key: str) -> Optional[APIKey]:
        """Get an API key by validating the provided plain key against all stored encrypted keys.

        This method decrypts each stored API key and compares it with the provided key.
        If a match is found and the key hasn't expired, returns the API key object.

        Args:
        ----
            db (AsyncSession): The database session.
            key (str): The plain API key to validate.

        Returns:
        -------
            Optional[APIKey]: The API key if found and valid.

        Raises:
        ------
            NotFoundException: If no matching API key is found.
            ValueError: If the matching API key has expired.

        Note:
        ----
            This method needs to decrypt each stored key for comparison since
            Fernet encryption is non-deterministic (same input produces different
            encrypted outputs). This is less efficient than hash-based lookups
            but necessary for symmetric encryption.
        """
        # Query all API keys (we need to check each one)
        query = select(self.model)
        result = await db.execute(query)
        api_keys = result.scalars().all()

        # Check each key
        for api_key in api_keys:
            try:
                decrypted_data = credentials.decrypt(api_key.encrypted_key)
                if decrypted_data["key"] == key:
                    # Check expiration
                    if api_key.expiration_date < datetime.now(timezone.utc):
                        raise ValueError("API key has expired")
                    return api_key
            except Exception:
                continue

        raise NotFoundException("API key not found")


api_key = CRUDAPIKey(APIKey)
