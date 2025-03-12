"""Dependencies that are used in the API endpoints."""

from typing import Optional

from fastapi import Depends, Header, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from airweave import crud, schemas
from airweave.core.config import settings
from airweave.core.exceptions import NotFoundException
from airweave.core.logging import logger
from airweave.db.session import get_db


async def get_user(
    db: AsyncSession = Depends(get_db),
    x_api_key: Optional[str] = Header(None),
) -> schemas.User:
    """Retrieve user from super user from database.

    Args:
    ----
        request (Request): The request object.
        db (AsyncSession): Database session.
        x_api_key (Optional[str]): API key provided in the request header.
        auth0_user (Optional[Auth0User]): Auth0 user details.

    Returns:
    -------
        schemas.User: User details from the database.

    Raises:
    ------
        HTTPException: If the user is not found in the database or if
            no authentication method is provided.

    """
    user = await crud.user.get_by_email(db, email=settings.FIRST_SUPERUSER)
    return schemas.User.model_validate(user)


async def get_user_from_api_key(db: AsyncSession, api_key: str) -> schemas.User:
    """Retrieve user from database using the API key.

    First validate the API key and then retrieve the user from the database.

    Args:
    ----
        db (AsyncSession): Database session.
        api_key (str): The API key.

    Returns:
    -------
        schemas.User: User details from the database.

    Raises:
    ------
        HTTPException: If the user is not found in the database or the API key is invalid.

    """
    try:
        api_key_obj = await crud.api_key.get_by_key(db, key=api_key)
    except ValueError as e:
        logger.error(f"Error retrieving API key: {e}", exc_info=True)
        if "expired" in str(e):
            raise HTTPException(status_code=403, detail="API key has expired") from e
        raise HTTPException(status_code=403, detail="Invalid API key") from e
    except NotFoundException as e:
        logger.error(f"API key not found: {e}", exc_info=True)
        raise HTTPException(status_code=403, detail="API key not found") from e
    user = api_key_obj.created_by
    return schemas.User.model_validate(user)
