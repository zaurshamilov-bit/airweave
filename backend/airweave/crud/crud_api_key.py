"""CRUD operations for the APIKey model."""

import secrets
from datetime import datetime, timedelta, timezone
from typing import Optional
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from airweave.core import credentials
from airweave.core.exceptions import NotFoundException
from airweave.crud._base_organization import CRUDOrganization
from airweave.db.unit_of_work import UnitOfWork
from airweave.models.api_key import APIKey
from airweave.schemas import APIKeyCreate, APIKeyUpdate, AuthContext, User


class CRUDAPIKey(CRUDOrganization[APIKey, APIKeyCreate, APIKeyUpdate]):
    """CRUD operations for the APIKey model."""

    def __init__(self):
        """Initialize APIKey CRUD with user tracking enabled."""
        super().__init__(APIKey, track_user=True)

    async def create_with_auth_context(
        self,
        db: AsyncSession,
        *,
        obj_in: APIKeyCreate,
        auth_context: AuthContext,
        organization_id: Optional[UUID] = None,
        uow: Optional[UnitOfWork] = None,
    ) -> APIKey:
        """Create a new API key with auth context.

        Args:
        ----
            db (AsyncSession): The database session.
            obj_in (APIKeyCreate): The API key creation data.
            auth_context (AuthContext): The authentication context.
            organization_id (Optional[UUID]): The organization ID to create in.
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

        # Create a new object with the encrypted key and expiration
        api_key_data = APIKeyCreate(encrypted_key=encrypted_key, expiration_date=expiration_date)

        # Use the parent create method which handles organization scoping and user tracking
        return await self.create(
            db=db,
            obj_in=api_key_data,
            auth_context=auth_context,
            organization_id=organization_id,
            uow=uow,
        )

    async def get_all_for_auth_context(
        self,
        db: AsyncSession,
        auth_context: AuthContext,
        organization_id: Optional[UUID] = None,
        *,
        skip: int = 0,
        limit: int = 100,
    ) -> list[APIKey]:
        """Get all API keys for an auth context's organization.

        Args:
        ----
            db (AsyncSession): The database session.
            auth_context (AuthContext): The authentication context.
            organization_id (Optional[UUID]): The organization ID to filter by.
            skip (int): The number of records to skip.
            limit (int): The maximum number of records to return.

        Returns:
        -------
            list[APIKey]: A list of API keys for the organization.
        """
        # Use the parent method which handles organization scoping and access validation
        return await self.get_multi_for_organization(
            db=db,
            auth_context=auth_context,
            organization_id=organization_id,
            skip=skip,
            limit=limit,
        )

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
        # Note: This method doesn't require organization scoping since it's used for authentication
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

    # Backward compatibility methods
    async def create_with_user(
        self,
        db: AsyncSession,
        *,
        obj_in: APIKeyCreate,
        current_user: User,
        organization_id: Optional[UUID] = None,
        uow: Optional[UnitOfWork] = None,
    ) -> APIKey:
        """Create a new API key for a user (backward compatibility).

        Args:
        ----
            db (AsyncSession): The database session.
            obj_in (APIKeyCreate): The API key creation data.
            current_user (User): The current user.
            organization_id (Optional[UUID]): The organization ID to create in.
            uow (Optional[UnitOfWork]): The unit of work to use for the transaction.

        Returns:
        -------
            APIKey: The created API key.
        """
        # Convert user to auth context
        auth_context = AuthContext(
            organization_id=current_user.organization_id, user=current_user, auth_method="auth0"
        )
        return await self.create_with_auth_context(
            db=db,
            obj_in=obj_in,
            auth_context=auth_context,
            organization_id=organization_id,
            uow=uow,
        )

    async def get_all_for_user(
        self,
        db: AsyncSession,
        *,
        skip: int = 0,
        limit: int = 100,
        current_user: User,
        organization_id: Optional[UUID] = None,
    ) -> list[APIKey]:
        """Get all API keys for a user's organization (backward compatibility).

        Args:
        ----
            db (AsyncSession): The database session.
            skip (int): The number of records to skip.
            limit (int): The maximum number of records to return.
            current_user (User): The current user.
            organization_id (Optional[UUID]): The organization ID to filter by.

        Returns:
        -------
            list[APIKey]: A list of API keys for the organization.
        """
        # Convert user to auth context
        auth_context = AuthContext(
            organization_id=current_user.organization_id, user=current_user, auth_method="auth0"
        )
        return await self.get_all_for_auth_context(
            db=db,
            auth_context=auth_context,
            organization_id=organization_id,
            skip=skip,
            limit=limit,
        )


api_key = CRUDAPIKey()
