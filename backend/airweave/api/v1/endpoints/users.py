"""The API module that contains the endpoints for users.

Important: this module is co-responsible with the CRUD layer for secure transactions with the
database, as it contains the endpoints for user creation and retrieval.
"""

from typing import List, Optional

from fastapi import Depends, HTTPException
from fastapi_auth0 import Auth0User
from sqlalchemy.ext.asyncio import AsyncSession

from airweave import crud, schemas
from airweave.api import deps
from airweave.api.auth import auth0
from airweave.api.router import TrailingSlashRouter
from airweave.core.exceptions import NotFoundException
from airweave.core.logging import logger
from airweave.db.unit_of_work import UnitOfWork
from airweave.schemas import OrganizationWithRole, User
from airweave.schemas.auth import AuthContext

router = TrailingSlashRouter()


@router.get("/", response_model=User)
async def read_user(
    *,
    current_user: schemas.User = Depends(deps.get_user),
) -> schemas.User:
    """Get current user with all organization relationships.

    Args:
    ----
        current_user (schemas.User): The authenticated user.

    Returns:
    -------
        schemas.User: The user object with all organization data.

    """
    return current_user


@router.get("/me/organizations", response_model=List[OrganizationWithRole])
async def read_user_organizations(
    *,
    current_user: schemas.User = Depends(deps.get_user),
) -> List[OrganizationWithRole]:
    """Get all organizations that the current user is a member of.

    Args:
    ----
        current_user (schemas.User): The authenticated user.

    Returns:
    -------
        List[OrganizationWithRole]: List of organizations with the user's role and primary status.

    """
    organizations = []

    for user_org in current_user.user_organizations:
        org_with_role = OrganizationWithRole(
            id=user_org.organization.id,
            name=user_org.organization.name,
            description=user_org.organization.description or "",
            created_at=user_org.organization.created_at,
            modified_at=user_org.organization.modified_at,
            role=user_org.role,
            is_primary=user_org.is_primary,
            auth0_org_id=user_org.auth0_org_id,
        )
        organizations.append(org_with_role)

    return organizations


@router.post("/create_or_update", response_model=User)
async def create_or_update_user(
    user_data: schemas.UserCreate,
    db: AsyncSession = Depends(deps.get_db),
    auth0_user: Optional[Auth0User] = Depends(auth0.get_user),
) -> schemas.User:
    """Create new user in database if it does not exist, with Auth0 organization sync.

    Can only create user with the same email as the authenticated user.
    Integrates with Auth0 Organizations API to sync user organizations.

    Args:
        user_data (schemas.UserCreate): The user object to be created.
        db (AsyncSession): Database session dependency to handle database operations.
        auth0_user (Auth0User): Authenticated auth0 user.

    Returns:
        schemas.User: The created user object with organization relationships.

    Raises:
        HTTPException: If the user is not authorized to create this user.
    """
    if user_data.email != auth0_user.email:
        logger.error(f"User {user_data.email} is not authorized to create user {auth0_user.email}")
        raise HTTPException(
            status_code=403,
            detail="You are not authorized to create this user.",
        )

    existing_user = None

    # Check if user already exists
    try:
        existing_user = await crud.user.get_by_email(db, email=user_data.email)
    except NotFoundException:
        logger.info(f"User {user_data.email} not found, creating...")

    if existing_user:
        # User exists - sync their Auth0 organizations
        from airweave.core.auth0_service import Auth0Service

        auth0_service = Auth0Service()
        try:
            updated_user = await auth0_service.sync_user_organizations(db, existing_user)
            logger.info(f"Synced Auth0 organizations for existing user: {user_data.email}")
            return schemas.User.model_validate(updated_user)
        except Exception as e:
            logger.warning(f"Failed to sync Auth0 organizations for user {user_data.email}: {e}")
            return schemas.User.model_validate(existing_user)

    # New user - handle signup with Auth0 organization sync
    from airweave.core.auth0_service import Auth0Service

    auth0_service = Auth0Service()

    try:
        # Add auth0_id to user data if available
        user_dict = user_data.model_dump()
        if auth0_user:
            user_dict["auth0_id"] = auth0_user.id

        # Handle new user signup with Auth0 integration
        user, signup_type = await auth0_service.handle_new_user_signup(db, user_dict)

        # Create API key for the user within their organization context
        # Use the first organization if available
        if user.user_organizations:
            first_org = user.user_organizations[0]

            async with UnitOfWork(db) as uow:
                _ = await crud.api_key.create(
                    db,
                    obj_in=schemas.APIKeyCreate(name="Default API Key"),
                    auth_context=AuthContext(
                        user=user,
                        organization_id=str(first_org.organization.id),
                        auth_method="auth0" if user.auth0_id else "system",
                    ),
                    uow=uow,
                )

        logger.info(f"Created new user {user.email} with signup type: {signup_type}")
        return schemas.User.model_validate(user)

    except Exception as e:
        logger.error(f"Failed to create user with Auth0 integration: {e}")
        # Fallback to traditional user creation
        async with UnitOfWork(db) as uow:
            user, organization = await crud.user.create_with_organization(
                db, obj_in=user_data, uow=uow
            )
            _ = await crud.api_key.create(
                db,
                obj_in=schemas.APIKeyCreate(name="Default API Key"),
                auth_context=AuthContext(
                    user=user, organization_id=str(organization.id), auth_method="auth0"
                ),
                uow=uow,
            )
        logger.info(f"Created user {user.email} with fallback method")
        return user
