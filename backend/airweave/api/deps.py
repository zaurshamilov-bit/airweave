"""Dependencies that are used in the API endpoints."""

from typing import Optional

from fastapi import Depends, Header, HTTPException
from fastapi_auth0 import Auth0User
from sqlalchemy.ext.asyncio import AsyncSession

from airweave import crud, schemas
from airweave.api.auth import auth0
from airweave.core.config import settings
from airweave.core.exceptions import NotFoundException
from airweave.core.logging import logger
from airweave.db.session import get_db


async def get_auth_context(
    db: AsyncSession = Depends(get_db),
    x_api_key: Optional[str] = Header(None),
    auth0_user: Optional[Auth0User] = Depends(auth0.get_user),
) -> schemas.AuthContext:
    """Retrieve authentication context for the request.

    Creates a unified AuthContext that works for both Auth0 users and API key authentication.

    Args:
    ----
        db (AsyncSession): Database session.
        x_api_key (Optional[str]): API key provided in the request header.
        auth0_user (Optional[Auth0User]): User details from Auth0.

    Returns:
    -------
        schemas.AuthContext: Unified authentication context.

    Raises:
    ------
        HTTPException: If no valid authentication method is provided.
    """
    # For test environments or when auth is disabled, use the first superuser
    if not settings.AUTH_ENABLED:
        user = await crud.user.get_by_email(db, email=settings.FIRST_SUPERUSER)
        if user:
            # Convert to schema with organizations loaded
            user_schema = schemas.User.model_validate(user)
            return schemas.AuthContext(
                organization_id=user.organization_id,
                user=user_schema,
                auth_method="system",
                auth_metadata={"disabled_auth": True},
            )

    # Auth0 user authentication
    if auth0_user:
        user = await crud.user.get_by_email(db, email=auth0_user.email)
        if user:
            # Convert to schema with organizations loaded
            user_schema = schemas.User.model_validate(user)
            return schemas.AuthContext(
                organization_id=user.organization_id,
                user=user_schema,
                auth_method="auth0",
                auth_metadata={"auth0_id": auth0_user.sub},
            )

    # API key authentication - organization context only
    if x_api_key:
        try:
            api_key_obj = await crud.api_key.get_by_key(db, key=x_api_key)
            return schemas.AuthContext(
                organization_id=api_key_obj.organization_id,
                user=None,  # API key outlives users
                auth_method="api_key",
                auth_metadata={
                    "api_key_id": str(api_key_obj.id),
                    "created_by": api_key_obj.created_by_email,  # Audit only
                },
            )
        except (ValueError, NotFoundException) as e:
            logger.error(f"API key validation failed: {e}")
            if "expired" in str(e):
                raise HTTPException(status_code=403, detail="API key has expired") from e
            raise HTTPException(status_code=403, detail="Invalid or expired API key") from e

    raise HTTPException(status_code=401, detail="No valid authentication provided")


async def get_user(
    db: AsyncSession = Depends(get_db),
    x_api_key: Optional[str] = Header(None),
    auth0_user: Optional[Auth0User] = Depends(auth0.get_user),
) -> schemas.User:
    """Retrieve user from super user from database.

    Legacy dependency for endpoints that expect User.
    Will fail for API key authentication since API keys don't have user context.

    Args:
    ----
        request (Request): The request object.
        db (AsyncSession): Database session.
        x_api_key (Optional[str]): API key provided in the request header.
        auth0_user (Optional[Auth0User]): User details from Auth0.

    Returns:
    -------
        schemas.User: User details from the database with organizations.

    Raises:
    ------
        HTTPException: If the user is not found in the database or if
            no authentication method is provided.

    """
    # Get auth context and extract user
    auth_context = await get_auth_context(db=db, x_api_key=x_api_key, auth0_user=auth0_user)

    if not auth_context.user:
        raise HTTPException(status_code=401, detail="User context required for this endpoint")

    return auth_context.user


async def get_user_from_api_key(db: AsyncSession, api_key: str) -> schemas.User:
    """Retrieve user from database using the API key.

    First validate the API key and then retrieve the user from the database.

    Args:
    ----
        db (AsyncSession): Database session.
        api_key (str): The plain API key to validate.

    Returns:
    -------
        schemas.User: User details from the database with organizations.

    Raises:
    ------
        HTTPException: If the user is not found or the API key is invalid.
    """
    try:
        # This function now handles decryption internally
        api_key_obj = await crud.api_key.get_by_key(db, key=api_key)
    except ValueError as e:
        logger.error(f"Error retrieving API key: {e}", exc_info=True)
        if "expired" in str(e):
            raise HTTPException(status_code=403, detail="API key has expired") from e
        raise HTTPException(status_code=403, detail="Invalid API key") from e
    except NotFoundException as e:
        logger.error(f"API key not found: {e}", exc_info=True)
        raise HTTPException(status_code=403, detail="API key not found") from e

    # Get the user with organizations loaded
    user = await crud.user.get_by_email(db, email=api_key_obj.created_by_email)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    return schemas.User.model_validate(user)


# Add this function to authenticate users with a token directly
async def get_user_from_token(token: str, db: AsyncSession) -> Optional[schemas.User]:
    """Verify the token and return the corresponding user.

    Args:
        token: The authentication token.
        db: The database session.

    Returns:
        The user with organizations if authentication succeeds, None otherwise.
    """
    try:
        # Remove 'Bearer ' prefix if present
        if token.startswith("Bearer "):
            token = token[7:]

        # If auth is disabled, just use the first superuser
        if not settings.AUTH_ENABLED:
            user = await crud.user.get_by_email(db, email=settings.FIRST_SUPERUSER)
            if user:
                return schemas.User.model_validate(user)
            return None

        # Get user ID from the token using the auth module
        from airweave.api.auth import get_user_from_token as auth_get_user

        auth0_user = await auth_get_user(token)
        if not auth0_user:
            return None

        # Get the internal user representation with organizations
        user = await crud.user.get_by_email(db=db, email=auth0_user.email)
        if not user:
            raise HTTPException(status_code=401, detail="User not found")

        return schemas.User.model_validate(user)
    except Exception as e:
        logger.error(f"Error in get_user_from_token: {e}")
        return None
