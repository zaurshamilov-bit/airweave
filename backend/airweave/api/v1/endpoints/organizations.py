"""API endpoints for organizations."""

from typing import List
from uuid import UUID

from fastapi import Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from airweave import crud, schemas
from airweave.api import deps
from airweave.api.router import TrailingSlashRouter
from airweave.core.auth0_service import auth0_service
from airweave.models.user import User
from airweave.schemas.auth import AuthContext

router = TrailingSlashRouter()


@router.post("/", response_model=schemas.Organization)
async def create_organization(
    organization_data: schemas.OrganizationCreate,
    db: AsyncSession = Depends(deps.get_db),
    user: User = Depends(deps.get_user),
) -> schemas.Organization:
    """Create a new organization with current user as owner.

    Integrates with Auth0 Organizations API when available for enhanced multi-org support.

    Args:
        organization_data: The organization data to create
        db: Database session
        user: The current authenticated user

    Returns:
        The created organization with user's role

    Raises:
        HTTPException: If organization name already exists or creation fails
    """
    # Create the organization with Auth0 integration
    try:
        organization = await auth0_service.create_organization_with_auth0(
            db=db, org_data=organization_data, owner_user=user
        )

        return organization
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to create organization: {str(e)}"
        ) from e


@router.get("/", response_model=List[schemas.OrganizationWithRole])
async def list_user_organizations(
    db: AsyncSession = Depends(deps.get_db),
    user: User = Depends(deps.get_user),
) -> List[schemas.OrganizationWithRole]:
    """Get all organizations the current user belongs to.

    Args:
        db: Database session
        user: The current authenticated user

    Returns:
        List of organizations with user's role in each
    """
    organizations = await crud.organization.get_user_organizations_with_roles(
        db=db, user_id=user.id
    )

    return [
        schemas.OrganizationWithRole(
            id=org.id,
            name=org.name,
            description=org.description or "",
            created_at=org.created_at,
            modified_at=org.modified_at,
            role=org.role,
            is_primary=org.is_primary,
        )
        for org in organizations
    ]


@router.get("/{organization_id}", response_model=schemas.OrganizationWithRole)
async def get_organization(
    organization_id: UUID,
    db: AsyncSession = Depends(deps.get_db),
    auth_context: AuthContext = Depends(deps.get_auth_context),
) -> schemas.OrganizationWithRole:
    """Get a specific organization by ID.

    Args:
        organization_id: The ID of the organization to get
        db: Database session
        auth_context: The current authenticated user

    Returns:
        The organization with user's role

    Raises:
        HTTPException: If organization not found or user doesn't have access
    """
    # Validate access and get user's membership (this now has security built-in)
    user_org = await crud.organization.get_user_membership(
        db=db,
        organization_id=organization_id,
        user_id=auth_context.user.id,
        auth_context=auth_context,
    )

    if not user_org:
        raise HTTPException(
            status_code=404, detail="Organization not found or you don't have access to it"
        )

    # Capture the role and is_primary values early to avoid greenlet exceptions later
    user_role = user_org.role
    user_is_primary = user_org.is_primary

    organization = await crud.organization.get(db=db, id=organization_id, auth_context=auth_context)

    return schemas.OrganizationWithRole(
        id=organization.id,
        name=organization.name,
        description=organization.description or "",
        created_at=organization.created_at,
        modified_at=organization.modified_at,
        role=user_role,
        is_primary=user_is_primary,
    )


@router.put("/{organization_id}", response_model=schemas.OrganizationWithRole)
async def update_organization(
    organization_id: UUID,
    organization_data: schemas.OrganizationCreate,  # Reuse the same schema
    db: AsyncSession = Depends(deps.get_db),
    auth_context: AuthContext = Depends(deps.get_auth_context),
) -> schemas.OrganizationWithRole:
    """Update an organization.

    Only organization owners and admins can update organizations.

    Args:
        organization_id: The ID of the organization to update
        organization_data: The updated organization data
        db: Database session
        auth_context: The current authenticated user

    Returns:
        The updated organization with user's role

    Raises:
        HTTPException: If organization not found, user doesn't have permission,
                      or organization name conflicts
    """
    # Get user's membership and validate admin access
    user_org = await crud.organization.get_user_membership(
        db=db,
        organization_id=organization_id,
        user_id=auth_context.user.id,
        auth_context=auth_context,
    )

    if not user_org:
        raise HTTPException(
            status_code=404, detail="Organization not found or you don't have access to it"
        )

    # Capture the role and is_primary values early to avoid greenlet exceptions later
    user_role = user_org.role
    user_is_primary = user_org.is_primary

    if user_role not in ["owner", "admin"]:
        raise HTTPException(
            status_code=403, detail="Only organization owners and admins can update organizations"
        )

    # Check if the new name conflicts with existing organizations (if name is being changed)
    organization = await crud.organization.get(db=db, id=organization_id, auth_context=auth_context)

    update_data = schemas.OrganizationUpdate(
        name=organization_data.name, description=organization_data.description or ""
    )

    updated_organization = await crud.organization.update(
        db=db, db_obj=organization, obj_in=update_data, auth_context=auth_context
    )

    return schemas.OrganizationWithRole(
        id=updated_organization.id,
        name=updated_organization.name,
        description=updated_organization.description or "",
        created_at=updated_organization.created_at,
        modified_at=updated_organization.modified_at,
        role=user_role,
        is_primary=user_is_primary,
    )


@router.delete("/{organization_id}", response_model=schemas.OrganizationWithRole)
async def delete_organization(
    organization_id: UUID,
    db: AsyncSession = Depends(deps.get_db),
    auth_context: AuthContext = Depends(deps.get_auth_context),
) -> schemas.OrganizationWithRole:
    """Delete an organization.

    Only organization owners can delete organizations.

    Args:
        organization_id: The ID of the organization to delete
        db: Database session
        auth_context: The current authenticated user

    Returns:
        The deleted organization

    Raises:
        HTTPException: If organization not found, user doesn't have permission,
                      or organization cannot be deleted
    """
    # Get user's membership (this now validates access automatically)
    user_org = await crud.organization.get_user_membership(
        db=db,
        organization_id=organization_id,
        user_id=auth_context.user.id,
        auth_context=auth_context,
    )

    if not user_org:
        raise HTTPException(
            status_code=404, detail="Organization not found or you don't have access to it"
        )

    # Capture the role and is_primary values early to avoid greenlet exceptions later
    user_role = user_org.role
    user_is_primary = user_org.is_primary

    if user_role != "owner":
        raise HTTPException(
            status_code=403, detail="Only organization owners can delete organizations"
        )

    # Check if this is the user's only organization
    user_orgs = await crud.organization.get_user_organizations_with_roles(
        db=db, user_id=auth_context.user.id
    )

    if len(user_orgs) <= 1:
        raise HTTPException(
            status_code=400,
            detail="Cannot delete your only organization. Contact support to delete your account.",
        )

    # Delete the organization (CASCADE will handle user_organization relationships)
    deleted_org = await crud.organization.remove(db=db, id=organization_id)

    return schemas.OrganizationWithRole(
        id=deleted_org.id,
        name=deleted_org.name,
        description=deleted_org.description or "",
        created_at=deleted_org.created_at,
        modified_at=deleted_org.modified_at,
        role=user_role,
        is_primary=user_is_primary,
    )


@router.post("/{organization_id}/leave", response_model=dict)
async def leave_organization(
    organization_id: UUID,
    db: AsyncSession = Depends(deps.get_db),
    auth_context: AuthContext = Depends(deps.get_auth_context),
) -> dict:
    """Leave an organization.

    Users cannot leave if they are the only owner or if it's their only organization.

    Args:
        organization_id: The ID of the organization to leave
        db: Database session
        auth_context: The current authenticated user

    Returns:
        Success message

    Raises:
        HTTPException: If user cannot leave the organization
    """
    # Get user's membership (this validates access automatically)
    user_org = await crud.organization.get_user_membership(
        db=db,
        organization_id=organization_id,
        user_id=auth_context.user.id,
        auth_context=auth_context,
    )

    if not user_org:
        raise HTTPException(status_code=404, detail="You are not a member of this organization")

    # Capture the role early to avoid greenlet exceptions later
    user_role = user_org.role

    # Check if this is the user's only organization
    user_orgs = await crud.organization.get_user_organizations_with_roles(
        db=db, user_id=auth_context.user.id
    )

    if len(user_orgs) <= 1:
        raise HTTPException(
            status_code=400,
            detail="Cannot leave your only organization. "
            "Users must belong to at least one organization. Delete the organization instead.",
        )

    # If user is an owner, check if there are other owners
    if user_role == "owner":
        other_owners = await crud.organization.get_organization_owners(
            db=db,
            organization_id=organization_id,
            auth_context=auth_context,
            exclude_user_id=auth_context.user.id,
        )

        if not other_owners:
            raise HTTPException(
                status_code=400,
                detail="Cannot leave organization as the only owner. "
                "Transfer ownership to another member first.",
            )

    # Remove the user from the organization (this validates permissions automatically)
    success = await crud.organization.remove_member(
        db=db,
        organization_id=organization_id,
        user_id=auth_context.user.id,
        auth_context=auth_context,
    )

    if not success:
        raise HTTPException(status_code=500, detail="Failed to leave organization")

    return {"message": "Successfully left the organization"}


@router.post("/{organization_id}/set-primary", response_model=schemas.OrganizationWithRole)
async def set_primary_organization(
    organization_id: UUID,
    db: AsyncSession = Depends(deps.get_db),
    auth_context: AuthContext = Depends(deps.get_auth_context),
) -> schemas.OrganizationWithRole:
    """Set an organization as the user's primary organization.

    Args:
        organization_id: The ID of the organization to set as primary
        db: Database session
        auth_context: The current authenticated user

    Returns:
        The organization with updated primary status

    Raises:
        HTTPException: If organization not found or user doesn't have access
    """
    # Set as primary organization
    success = await crud.organization.set_primary_organization(
        db=db,
        user_id=auth_context.user.id,
        organization_id=organization_id,
        auth_context=auth_context,
    )

    if not success:
        raise HTTPException(
            status_code=404, detail="Organization not found or you don't have access to it"
        )

    # Get the updated organization data
    user_org = await crud.organization.get_user_membership(
        db=db,
        organization_id=organization_id,
        user_id=auth_context.user.id,
        auth_context=auth_context,
    )

    organization = await crud.organization.get(db=db, id=organization_id, auth_context=auth_context)

    if not organization or not user_org:
        raise HTTPException(status_code=404, detail="Organization not found")

    return schemas.OrganizationWithRole(
        id=organization.id,
        name=organization.name,
        description=organization.description or "",
        created_at=organization.created_at,
        modified_at=organization.modified_at,
        role=user_org.role,
        is_primary=user_org.is_primary,
    )
