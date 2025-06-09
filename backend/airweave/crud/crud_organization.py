"""CRUD operations for the organization model."""

from typing import Any, List, Optional, Union
from uuid import UUID

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from airweave.core.exceptions import PermissionException
from airweave.db.unit_of_work import UnitOfWork
from airweave.models.organization import Organization
from airweave.models.user import User
from airweave.models.user_organization import UserOrganization
from airweave.schemas.auth import AuthContext
from airweave.schemas.organization import (
    OrganizationCreate,
    OrganizationUpdate,
    OrganizationWithRole,
)


class CRUDOrganization:
    """CRUD operations for the organization model.

    Note: This handles Organization entities themselves, not organization-scoped resources.
    Organizations don't have organization_id (they ARE organizations), so this class
    implements its own validation logic rather than inheriting from CRUDBaseOrganization.
    """

    def __init__(self):
        """Initialize the Organization CRUD."""
        self.model = Organization

    async def get_by_name(self, db: AsyncSession, name: str) -> Organization | None:
        """Get an organization by its name."""
        stmt = select(Organization).where(Organization.name == name)
        result = await db.execute(stmt)
        return result.scalar_one_or_none()

    async def create_with_owner(
        self,
        db: AsyncSession,
        *,
        obj_in: OrganizationCreate,
        owner_user: User,
        uow: Optional[UnitOfWork] = None,
    ) -> Organization:
        """Create organization and assign the user as owner.

        Args:
            db: Database session
            obj_in: Organization creation data
            owner_user: User who will become the owner
            uow: Unit of work

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

        if not owner_user.primary_organization_id:
            owner_user.primary_organization_id = organization.id

        if not uow:
            await db.commit()
            await db.refresh(organization)

        return organization

    async def get(
        self,
        db: AsyncSession,
        id: UUID,
        auth_context: AuthContext,
    ) -> Optional[Organization]:
        """Get organization by ID with access validation.

        Organizations don't have organization_id field, so we override the base method.
        """
        # Check if the user has access to this organization
        if auth_context.has_user_context:
            user_org_ids = [org.organization.id for org in auth_context.user.user_organizations]
            if id not in user_org_ids:
                return None
        else:
            # For API key access, only allow access to the key's organization
            if str(id) != auth_context.organization_id:
                return None

        query = select(self.model).where(self.model.id == id)
        result = await db.execute(query)
        return result.unique().scalar_one_or_none()

    async def get_multi(
        self,
        db: AsyncSession,
        auth_context: AuthContext,
        *,
        skip: int = 0,
        limit: int = 100,
    ) -> list[Organization]:
        """Get all organizations for the authenticated user/API key.

        Organizations don't have organization_id field, so we override the base method.
        """
        if auth_context.has_user_context:
            # Get organizations the user has access to
            user_org_ids = [org.organization.id for org in auth_context.user.user_organizations]
            if not user_org_ids:
                return []

            query = (
                select(self.model).where(self.model.id.in_(user_org_ids)).offset(skip).limit(limit)
            )
        else:
            # For API key access, only return the key's organization
            query = (
                select(self.model)
                .where(self.model.id == auth_context.organization_id)
                .offset(skip)
                .limit(limit)
            )

        result = await db.execute(query)
        return list(result.unique().scalars().all())

    async def update(
        self,
        db: AsyncSession,
        *,
        db_obj: Organization,
        obj_in: Union[OrganizationUpdate, dict[str, Any]],
        auth_context: AuthContext,
        uow: Optional[UnitOfWork] = None,
    ) -> Organization:
        """Update organization with access validation.

        Organizations don't have organization_id field, so we override the base method.
        """
        # Check if the user has access to this organization
        if auth_context.has_user_context:
            user_org_ids = [org.organization.id for org in auth_context.user.user_organizations]
            if db_obj.id not in user_org_ids:
                from airweave.core.exceptions import PermissionException

                raise PermissionException("User does not have access to organization")
        else:
            # For API key access, only allow access to the key's organization
            if str(db_obj.id) != auth_context.organization_id:
                from airweave.core.exceptions import PermissionException

                raise PermissionException("API key does not have access to organization")

        if not isinstance(obj_in, dict):
            obj_in = obj_in.model_dump(exclude_unset=True)

        # Organizations track user modifications
        if auth_context.has_user_context:
            obj_in["modified_by_email"] = auth_context.tracking_email

        for field, value in obj_in.items():
            setattr(db_obj, field, value)

        if not uow:
            await db.commit()
            await db.refresh(db_obj)

        return db_obj

    async def create(db, obj_in, auth_context) -> NotImplementedError:
        """Create organization resource with auth context."""
        raise NotImplementedError("This method is not implemented for organizations.")

    async def _validate_organization_access(
        self, auth_context: AuthContext, organization_id: UUID
    ) -> None:
        """Validate auth context has access to organization.

        Args:
        ----
            auth_context (AuthContext): The authentication context.
            organization_id (UUID): The organization ID to validate access to.

        Raises:
        ------
            PermissionException: If auth context does not have access to organization.
        """
        if auth_context.has_user_context:
            if organization_id not in [
                org.organization.id for org in auth_context.user.user_organizations
            ]:
                raise PermissionException("User does not have access to organization")
        else:
            if str(organization_id) != auth_context.organization_id:
                raise PermissionException("API key does not have access to organization")

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

        # First validate basic organization access
        await self._validate_organization_access(auth_context, organization_id)

        # Then check if user is admin/owner by finding their UserOrganization record
        if not auth_context.has_user_context:
            raise HTTPException(status_code=403, detail="API keys cannot perform admin actions")

        # Find the user's role in this organization
        user_org = None
        for org in auth_context.user.user_organizations:
            if org.organization.id == organization_id:
                user_org = org
                break

        if not user_org or user_org.role not in ["owner", "admin"]:
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
