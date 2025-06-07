"""API endpoints for organizations."""

from typing import List
from uuid import UUID

from fastapi import Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from airweave import crud, schemas
from airweave.api import deps
from airweave.api.router import TrailingSlashRouter
from airweave.models.user import User

router = TrailingSlashRouter()


@router.post("/", response_model=schemas.OrganizationWithRole)
async def create_organization(
    organization_data: schemas.OrganizationCreateRequest,
    db: AsyncSession = Depends(deps.get_db),
    current_user: User = Depends(deps.get_user),
) -> schemas.OrganizationWithRole:
    """Create a new organization with current user as owner.

    Args:
        organization_data: The organization data to create
        db: Database session
        current_user: The current authenticated user

    Returns:
        The created organization with user's role

    Raises:
        HTTPException: If organization name already exists or creation fails
    """
    # Check if organization name already exists
    existing_org = await crud.organization.get_by_name(db, name=organization_data.name)
    if existing_org:
        raise HTTPException(
            status_code=400,
            detail=f"Organization with name '{organization_data.name}' already exists",
        )

    # Create the organization with the user as owner
    try:
        organization = await crud.organization.create_with_owner(
            db=db, obj_in=organization_data, owner_user=current_user
        )

        return schemas.OrganizationWithRole(
            id=organization.id,
            name=organization.name,
            description=organization.description or "",
            created_at=organization.created_at,
            modified_at=organization.modified_at,
            role="owner",
            is_primary=True,  # New organizations are primary by default
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to create organization: {str(e)}")


@router.get("/", response_model=List[schemas.OrganizationWithRole])
async def list_user_organizations(
    db: AsyncSession = Depends(deps.get_db),
    current_user: User = Depends(deps.get_user),
) -> List[schemas.OrganizationWithRole]:
    """Get all organizations the current user belongs to.

    Args:
        db: Database session
        current_user: The current authenticated user

    Returns:
        List of organizations with user's role in each
    """
    organizations = await crud.organization.get_user_organizations_with_roles(
        db=db, user_id=current_user.id
    )

    return [
        schemas.OrganizationWithRole(
            id=org.id,
            name=org.name,
            description=org.description or "",
            created_at=org.created_at,
            modified_at=org.modified_at,
            role=org.user_role,
            is_primary=org.is_primary,
        )
        for org in organizations
    ]


@router.get("/{organization_id}", response_model=schemas.OrganizationWithRole)
async def get_organization(
    organization_id: UUID,
    db: AsyncSession = Depends(deps.get_db),
    current_user: User = Depends(deps.get_user),
) -> schemas.OrganizationWithRole:
    """Get a specific organization by ID.

    Args:
        organization_id: The ID of the organization to get
        db: Database session
        current_user: The current authenticated user

    Returns:
        The organization with user's role

    Raises:
        HTTPException: If organization not found or user doesn't have access
    """
    # Validate access and get user's membership (this now has security built-in)
    user_org = await crud.organization.get_user_membership(
        db=db, organization_id=organization_id, user_id=current_user.id, current_user=current_user
    )

    if not user_org:
        raise HTTPException(
            status_code=404, detail="Organization not found or you don't have access to it"
        )

    organization = await crud.organization.get(db=db, id=organization_id)
    if not organization:
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


@router.put("/{organization_id}", response_model=schemas.OrganizationWithRole)
async def update_organization(
    organization_id: UUID,
    organization_data: schemas.OrganizationCreateRequest,  # Reuse the same schema
    db: AsyncSession = Depends(deps.get_db),
    current_user: User = Depends(deps.get_user),
) -> schemas.OrganizationWithRole:
    """Update an organization.

    Only organization owners and admins can update organizations.

    Args:
        organization_id: The ID of the organization to update
        organization_data: The updated organization data
        db: Database session
        current_user: The current authenticated user

    Returns:
        The updated organization with user's role

    Raises:
        HTTPException: If organization not found, user doesn't have permission,
                      or organization name conflicts
    """
    # Get user's membership and validate admin access
    user_org = await crud.organization.get_user_membership(
        db=db, organization_id=organization_id, user_id=current_user.id, current_user=current_user
    )

    if not user_org:
        raise HTTPException(
            status_code=404, detail="Organization not found or you don't have access to it"
        )

    if user_org.role not in ["owner", "admin"]:
        raise HTTPException(
            status_code=403, detail="Only organization owners and admins can update organizations"
        )

    # Check if the new name conflicts with existing organizations (if name is being changed)
    organization = await crud.organization.get(db=db, id=organization_id)
    if not organization:
        raise HTTPException(status_code=404, detail="Organization not found")

    if organization_data.name != organization.name:
        existing_org = await crud.organization.get_by_name(db, name=organization_data.name)
        if existing_org and existing_org.id != organization_id:
            raise HTTPException(
                status_code=400,
                detail=f"Organization with name '{organization_data.name}' already exists",
            )

    # Update the organization
    try:
        from airweave.schemas.organization import OrganizationUpdate

        update_data = OrganizationUpdate(
            name=organization_data.name, description=organization_data.description or ""
        )

        updated_organization = await crud.organization.update(
            db=db, db_obj=organization, obj_in=update_data
        )

        return schemas.OrganizationWithRole(
            id=updated_organization.id,
            name=updated_organization.name,
            description=updated_organization.description or "",
            created_at=updated_organization.created_at,
            modified_at=updated_organization.modified_at,
            role=user_org.role,
            is_primary=user_org.is_primary,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to update organization: {str(e)}")


@router.delete("/{organization_id}", response_model=schemas.OrganizationWithRole)
async def delete_organization(
    organization_id: UUID,
    db: AsyncSession = Depends(deps.get_db),
    current_user: User = Depends(deps.get_user),
) -> schemas.OrganizationWithRole:
    """Delete an organization.

    Only organization owners can delete organizations.

    Args:
        organization_id: The ID of the organization to delete
        db: Database session
        current_user: The current authenticated user

    Returns:
        The deleted organization

    Raises:
        HTTPException: If organization not found, user doesn't have permission,
                      or organization cannot be deleted
    """
    # Get user's membership (this now validates access automatically)
    user_org = await crud.organization.get_user_membership(
        db=db, organization_id=organization_id, user_id=current_user.id, current_user=current_user
    )

    if not user_org:
        raise HTTPException(
            status_code=404, detail="Organization not found or you don't have access to it"
        )

    if user_org.role != "owner":
        raise HTTPException(
            status_code=403, detail="Only organization owners can delete organizations"
        )

    # Get the organization
    organization = await crud.organization.get(db=db, id=organization_id)
    if not organization:
        raise HTTPException(status_code=404, detail="Organization not found")

    # Check if this is the user's only organization
    user_orgs = await crud.organization.get_user_organizations_with_roles(
        db=db, user_id=current_user.id
    )

    if len(user_orgs) <= 1:
        raise HTTPException(
            status_code=400,
            detail="Cannot delete your only organization. Users must belong to at least one organization.",
        )

    # Delete the organization (CASCADE will handle user_organization relationships)
    deleted_org = await crud.organization.remove(db=db, id=organization_id)

    return schemas.OrganizationWithRole(
        id=deleted_org.id,
        name=deleted_org.name,
        description=deleted_org.description or "",
        created_at=deleted_org.created_at,
        modified_at=deleted_org.modified_at,
        role=user_org.role,
        is_primary=user_org.is_primary,
    )


@router.post("/{organization_id}/leave", response_model=dict)
async def leave_organization(
    organization_id: UUID,
    db: AsyncSession = Depends(deps.get_db),
    current_user: User = Depends(deps.get_user),
) -> dict:
    """Leave an organization.

    Users cannot leave if they are the only owner or if it's their only organization.

    Args:
        organization_id: The ID of the organization to leave
        db: Database session
        current_user: The current authenticated user

    Returns:
        Success message

    Raises:
        HTTPException: If user cannot leave the organization
    """
    # Get user's membership (this validates access automatically)
    user_org = await crud.organization.get_user_membership(
        db=db, organization_id=organization_id, user_id=current_user.id, current_user=current_user
    )

    if not user_org:
        raise HTTPException(status_code=404, detail="You are not a member of this organization")

    # Check if this is the user's only organization
    user_orgs = await crud.organization.get_user_organizations_with_roles(
        db=db, user_id=current_user.id
    )

    if len(user_orgs) <= 1:
        raise HTTPException(
            status_code=400,
            detail="Cannot leave your only organization. Users must belong to at least one organization.",
        )

    # If user is an owner, check if there are other owners
    if user_org.role == "owner":
        other_owners = await crud.organization.get_organization_owners(
            db=db,
            organization_id=organization_id,
            current_user=current_user,
            exclude_user_id=current_user.id,
        )

        if not other_owners:
            raise HTTPException(
                status_code=400,
                detail="Cannot leave organization as the only owner. Transfer ownership to another member first.",
            )

    # Remove the user from the organization (this validates permissions automatically)
    success = await crud.organization.remove_member(
        db=db, organization_id=organization_id, user_id=current_user.id, current_user=current_user
    )

    if not success:
        raise HTTPException(status_code=500, detail="Failed to leave organization")

    return {"message": "Successfully left the organization"}
