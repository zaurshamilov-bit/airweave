"""CRUD operations for the organization model."""

from typing import List, Optional
from uuid import UUID

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from airweave.crud._base_organization import CRUDBaseOrganization
from airweave.models.organization import Organization
from airweave.models.user import User
from airweave.models.user_organization import UserOrganization
from airweave.schemas.auth import AuthContext
from airweave.schemas.organization import (
    OrganizationCreate,
    OrganizationCreateRequest,
    OrganizationUpdate,
    OrganizationWithRole,
)


class CRUDOrganization(CRUDBaseOrganization[Organization, OrganizationCreate, OrganizationUpdate]):
    """CRUD operations for the organization model.

    Note: This handles Organization entities themselves, not organization-scoped resources.
    Organizations don't have organization_id (they ARE organizations), so this needs
    special handling beyond the standard CRUDOrganization pattern.
    """

    def __init__(self):
        """Initialize with track_user=True since organizations have creator tracking."""
        super().__init__(Organization, track_user=True)

    async def get_by_name(self, db: AsyncSession, name: str) -> Organization | None:
        """Get an organization by its name."""
        stmt = select(Organization).where(Organization.name == name)
        result = await db.execute(stmt)
        return result.scalar_one_or_none()

    async def create_with_owner(
        self, db: AsyncSession, *, obj_in: OrganizationCreateRequest, owner_user: User
    ) -> Organization:
        """Create organization and assign the user as owner.

        Args:
            db: Database session
            obj_in: Organization creation data
            owner_user: User who will become the owner

        Returns:
            The created organization
        """
        # Convert to OrganizationCreate schema
        org_data = OrganizationCreate(name=obj_in.name, description=obj_in.description or "")

        # Create the organization manually since it doesn't have organization_id
        if not isinstance(org_data, dict):
            org_data_dict = org_data.model_dump(exclude_unset=True)
        else:
            org_data_dict = org_data

        # Add user tracking
        org_data_dict["created_by_email"] = owner_user.email
        org_data_dict["modified_by_email"] = owner_user.email

        organization = Organization(**org_data_dict)
        db.add(organization)
        await db.flush()  # Get the ID

        # Create UserOrganization relationship with owner role
        user_org = UserOrganization(
            user_id=owner_user.id,
            organization_id=organization.id,
            role="owner",
            is_primary=True,  # New organizations are primary by default
        )
        db.add(user_org)

        # Update user's current organization to this new one
        owner_user.current_organization_id = organization.id
        if not owner_user.primary_organization_id:
            owner_user.primary_organization_id = organization.id

        await db.commit()
        await db.refresh(organization)

        return organization

    async def get_user_organizations_with_roles(
        self, db: AsyncSession, user_id: UUID
    ) -> List[OrganizationWithRole]:
        """Get all organizations for a user with their roles.

        Args:
            db: Database session
            user_id: The user's ID

        Returns:
            List of organizations with user's role information
        """
        stmt = (
            select(Organization, UserOrganization.role, UserOrganization.is_primary)
            .join(UserOrganization, Organization.id == UserOrganization.organization_id)
            .where(UserOrganization.user_id == user_id)
            .order_by(UserOrganization.is_primary.desc(), Organization.name)
        )

        result = await db.execute(stmt)
        rows = result.all()

        return [
            OrganizationWithRole(
                id=org.id,
                name=org.name,
                description=org.description or "",
                created_at=org.created_at,
                modified_at=org.modified_at,
                role=role,
                is_primary=is_primary,
            )
            for org, role, is_primary in rows
        ]

    async def _validate_admin_access(
        self, auth_context: AuthContext, organization_id: UUID
    ) -> UserOrganization:
        """Validate user has admin/owner access to organization.

        Args:
            auth_context: The authentication context
            organization_id: Organization ID to validate admin access to

        Returns:
            UserOrganization record for the user

        Raises:
            HTTPException: If user doesn't have admin access
        """
        from fastapi import HTTPException

        user_org = await self._validate_organization_access(auth_context, organization_id)

        if user_org.role not in ["owner", "admin"]:
            raise HTTPException(
                status_code=403, detail="You must be an admin or owner to perform this action"
            )

        return user_org

    async def get_user_membership(
        self, db: AsyncSession, organization_id: UUID, user_id: UUID, auth_context: AuthContext
    ) -> Optional[UserOrganization]:
        """Get user membership in organization with access validation.

        Args:
            db: Database session
            organization_id: The organization's ID
            user_id: The user's ID to check membership for
            auth_context: Current authenticated user

        Returns:
            UserOrganization record if found, None otherwise
        """
        # Validate current user has access to this organization
        await self._validate_organization_access(auth_context, organization_id)

        # Query the membership
        stmt = select(UserOrganization).where(
            UserOrganization.user_id == user_id, UserOrganization.organization_id == organization_id
        )
        result = await db.execute(stmt)
        return result.scalar_one_or_none()

    async def get_organization_owners(
        self,
        db: AsyncSession,
        organization_id: UUID,
        auth_context: AuthContext,
        exclude_user_id: Optional[UUID] = None,
    ) -> List[UserOrganization]:
        """Get all owners of an organization with access validation.

        Args:
            db: Database session
            organization_id: The organization's ID
            auth_context: The auth context
            exclude_user_id: Optional user ID to exclude from results

        Returns:
            List of UserOrganization records with owner role
        """
        # Validate current user has access to this organization
        await self._validate_organization_access(auth_context, organization_id)

        stmt = select(UserOrganization).where(
            UserOrganization.organization_id == organization_id, UserOrganization.role == "owner"
        )

        if exclude_user_id:
            stmt = stmt.where(UserOrganization.user_id != exclude_user_id)

        result = await db.execute(stmt)
        return list(result.scalars().all())

    async def get_organization_members(
        self, db: AsyncSession, organization_id: UUID, auth_context: AuthContext
    ) -> List[UserOrganization]:
        """Get all members of an organization with access validation.

        Args:
            db: Database session
            organization_id: The organization's ID
            auth_context: The auth context

        Returns:
            List of UserOrganization records for the organization
        """
        # Validate current user has access to this organization
        await self._validate_organization_access(auth_context, organization_id)

        stmt = (
            select(UserOrganization)
            .where(UserOrganization.organization_id == organization_id)
            .order_by(UserOrganization.role.desc(), UserOrganization.user_id)
        )

        result = await db.execute(stmt)
        return list(result.scalars().all())

    async def remove_member(
        self, db: AsyncSession, organization_id: UUID, user_id: UUID, current_user: User
    ) -> bool:
        """Remove a user from an organization with proper permission checks.

        Args:
            db: Database session
            organization_id: The organization's ID
            user_id: The user's ID to remove
            current_user: Current authenticated user

        Returns:
            True if the relationship was removed, False if it didn't exist

        Raises:
            HTTPException: If current user doesn't have permission
        """
        from fastapi import HTTPException

        # If user is trying to remove themselves, we allow it with different validation
        if user_id == current_user.id:
            user_org = await self.get_user_membership(db, organization_id, user_id, current_user)

            # If they're an owner, check if there are other owners
            if user_org.role == "owner":
                owners = await self.get_organization_owners(
                    db, organization_id, current_user, exclude_user_id=user_id
                )
                if not owners:
                    raise HTTPException(
                        status_code=400,
                        detail="Cannot remove yourself as the only owner. "
                        "Transfer ownership to another member first.",
                    )
        else:
            # If removing someone else, validate current user has admin access
            await self._validate_admin_access(db, current_user, organization_id)

        stmt = delete(UserOrganization).where(
            UserOrganization.user_id == user_id, UserOrganization.organization_id == organization_id
        )

        result = await db.execute(stmt)
        await db.commit()

        return result.rowcount > 0

    async def add_member(
        self,
        db: AsyncSession,
        organization_id: UUID,
        user_id: UUID,
        role: str,
        auth_context: AuthContext,
        is_primary: bool = False,
    ) -> UserOrganization:
        """Add a user to an organization with proper permission checks.

        Args:
            db: Database session
            organization_id: The organization's ID
            user_id: The user's ID to add
            role: The user's role in the organization
            auth_context: Current authenticated user
            is_primary: Whether this is the user's primary organization

        Returns:
            The created UserOrganization record

        Raises:
            HTTPException: If current user doesn't have permission
        """
        # Validate current user has admin access
        await self._validate_admin_access(auth_context, organization_id)

        user_org = UserOrganization(
            user_id=user_id, organization_id=organization_id, role=role, is_primary=is_primary
        )

        db.add(user_org)
        await db.commit()
        await db.refresh(user_org)

        return user_org

    async def update_member_role(
        self,
        db: AsyncSession,
        organization_id: UUID,
        user_id: UUID,
        new_role: str,
        auth_context: AuthContext,
    ) -> Optional[UserOrganization]:
        """Update a user's role in an organization with proper permission checks.

        Args:
            db: Database session
            organization_id: The organization's ID
            user_id: The user's ID whose role to update
            new_role: The new role for the user
            auth_context: Current authenticated user

        Returns:
            The updated UserOrganization record if found, None otherwise

        Raises:
            HTTPException: If current user doesn't have permission
        """
        # Validate current user has admin access
        await self._validate_admin_access(auth_context, organization_id)

        user_org = await self.get_user_membership(db, organization_id, user_id, auth_context)

        if user_org:
            user_org.role = new_role
            await db.commit()
            await db.refresh(user_org)

        return user_org


# Create the instance with the updated class name
organization = CRUDOrganization()
