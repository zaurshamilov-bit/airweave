"""This module initializes the database with the first superuser."""

from app import crud, schemas
from app.core.config import settings
from sqlalchemy.ext.asyncio import AsyncSession


async def init_db(db: AsyncSession) -> None:
    """Initialize the database with the first superuser.

    Args:
        db (AsyncSession): The database session.
    """
    user = await crud.user.get_by_email(db, email=settings.FIRST_SUPERUSER)
    if not user:
        user_in = schemas.UserCreate(
            email=settings.FIRST_SUPERUSER, password=settings.FIRST_SUPERUSER_PASSWORD
        )
        user = await crud.user.create(db, obj_in=user_in)
