"""Initialize the database with the first superuser."""

from sqlalchemy.ext.asyncio import AsyncSession

from app import crud, schemas
from app.core.config import settings


async def init_db(db: AsyncSession) -> None:
    """Initialize the database with the first organization and superuser.

    Args:
    ----
        db (AsyncSession): The database session.
    """
    organization = await crud.organization.get_by_name(db, name=settings.FIRST_SUPERUSER)
    if not organization:
        organization_in = schemas.OrganizationCreate(
            name=settings.FIRST_SUPERUSER,
            description="Superuser organization",
        )
        organization = await crud.organization.create(db, obj_in=organization_in)

    user = await crud.user.get_by_email(db, email=settings.FIRST_SUPERUSER)

    if not user:
        user_in = schemas.UserCreate(
            email=settings.FIRST_SUPERUSER,
            full_name="Superuser",
            password=settings.FIRST_SUPERUSER_PASSWORD,
            organization_id=organization.id,
        )
        user = await crud.user.create(db, obj_in=user_in)

