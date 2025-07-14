"""Auth0 service for managing organization synchronization."""

import uuid
from typing import Dict, List
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from airweave import crud, schemas
from airweave.core.logging import logger
from airweave.db.unit_of_work import UnitOfWork
from airweave.integrations.auth0_management import auth0_management_client
from airweave.models import Organization, User
from airweave.schemas.auth import AuthContext


class OrganizationService:
    """Service for Auth0 organization management and synchronization."""

    def _create_org_name(self, org_data: schemas.OrganizationCreate) -> str:
        """Create a unique organization name for Auth0."""
        small_uuid = str(uuid.uuid4())[:8]
        return f"airweave-{org_data.name.lower().replace(' ', '-')}-{small_uuid}"

    async def create_organization_with_auth0(
        self, db: AsyncSession, org_data: schemas.OrganizationCreate, owner_user: User
    ) -> schemas.Organization:
        """Create organization and sync with Auth0.

        Args:
            db: Database session
            org_data: Organization creation data
            owner_user: User who will own the organization

        Returns:
            Created organization

        Raises:
            Exception: If organization creation fails
        """
        auth0_org_data = None

        logger.info(f"Creating Auth0 organization for: {org_data.name}")
        auth0_org_data = await auth0_management_client.create_organization(
            name=self._create_org_name(org_data),
            display_name=org_data.name,
        )
        auth0_org_id = auth0_org_data["id"]

        # Add user to Auth0 organization as owner
        await auth0_management_client.add_user_to_organization(auth0_org_id, owner_user.auth0_id)

        # Enable default connections for the new organization
        # Define the connections to be enabled by default
        default_connection_names = [
            "Username-Password-Authentication",
            "google-oauth2",
            "github",
        ]

        # Get all available connections from Auth0
        all_connections = await auth0_management_client.get_all_connections()

        # Find the connection IDs for our default connections
        connections_to_enable = [
            conn["id"] for conn in all_connections if conn["name"] in default_connection_names
        ]

        # Enable each connection for the new organization
        for conn_id in connections_to_enable:
            await auth0_management_client.add_enabled_connection_to_organization(
                auth0_org_id, conn_id
            )
            logger.info(f"Enabled connection {conn_id} for organization {auth0_org_id}")

        logger.info(f"Successfully created Auth0 organization: {auth0_org_id}")

        # Create local organization with Auth0 ID if available
        async with UnitOfWork(db) as uow:
            try:
                # Prepare organization data
                org_dict = org_data.model_dump()
                if auth0_org_data:
                    org_dict["auth0_org_id"] = auth0_org_id
                    logger.info(f"Setting auth0_org_id to: {auth0_org_id}")
                else:
                    logger.info("No auth0_org_data - creating organization without auth0_org_id")

                logger.info(f"Creating organization with data: {org_dict}")

                # Create organization using enhanced CRUD method
                local_org = await crud.organization.create_with_owner(
                    db=db,
                    obj_in=schemas.OrganizationCreate(**org_dict),
                    owner_user=owner_user,
                    uow=uow,
                )

                logger.info(f"Created organization with auth0_org_id: {local_org.auth0_org_id}")

                organization = schemas.Organization(
                    **org_dict,
                    role="owner",
                    created_at=local_org.created_at,
                    modified_at=local_org.modified_at,
                    id=local_org.id,
                )

                await uow.commit()
                logger.info("Successfully created local organization.")
                return organization

            except Exception as e:
                await uow.rollback()
                logger.error(f"Failed to create local organization: {e}")

                # If we created an Auth0 org but failed locally, we should clean up
                if auth0_org_data:
                    await auth0_management_client.delete_organization(auth0_org_id)
                raise

    async def handle_new_user_signup(
        self, db: AsyncSession, user_data: Dict, create_org: bool = False
    ) -> User:
        """Handle new user signup - check for Auth0 orgs or create new one.

        Args:
            db: Database session
            user_data: User data from signup
            create_org: Whether to create an organization if none exists (defaults to False)

        Returns:
            Created user
        """
        auth0_id = user_data.get("auth0_id")

        if not auth0_id:
            # No Auth0 ID or Auth0 not enabled
            raise ValueError("No Auth0 ID provided")

        try:
            # Check if user has existing Auth0 organizations
            auth0_orgs = await auth0_management_client.get_user_organizations(auth0_id)

            if auth0_orgs:
                # User has Auth0 organizations, sync them
                logger.info(
                    f"User {user_data.get('email')} has {len(auth0_orgs)} Auth0 organizations"
                )
                return await self._create_user_with_existing_orgs(db, user_data, auth0_orgs)
            else:
                # No Auth0 orgs
                if create_org:
                    logger.info(
                        f"User {user_data.get('email')} has no Auth0 organizations. "
                        "Creating new org."
                    )
                    return await self._create_user_with_new_org(db, user_data)
                else:
                    logger.info(
                        f"User {user_data.get('email')} has no Auth0 organizations. "
                        "Creating user without org."
                    )
                    return await self._create_user_without_org(db, user_data)

        except Exception as e:
            logger.error(f"Failed to check Auth0 organizations for new user: {e}")
            # Fallback behavior
            if create_org:
                return await self._create_user_with_new_org(db, user_data)
            else:
                return await self._create_user_without_org(db, user_data)

    async def sync_user_organizations(self, db: AsyncSession, user: User) -> User:
        """Sync user's Auth0 organizations with local database.

        Args:
            db: Database session
            user: User to sync organizations for

        Returns:
            Updated user with synced organizations
        """
        try:
            # Get user's Auth0 organizations
            auth0_orgs = await auth0_management_client.get_user_organizations(user.auth0_id)

            if not auth0_orgs:
                logger.info(f"User {user.email} has no Auth0 organizations")
                return user

            logger.info(f"Syncing {len(auth0_orgs)} Auth0 organizations for user {user.email}")

            # Sync each organization
            for auth0_org in auth0_orgs:
                await self._sync_single_organization(db, user, auth0_org)

            await db.commit()
            await db.refresh(user)

            logger.info(f"Successfully synced organizations for user {user.email}")
            return user

        except Exception as e:
            logger.error(f"Failed to sync Auth0 organizations for user {user.email}: {e}")
            await db.rollback()
            return user

    # Private helper methods
    async def _sync_single_organization(
        self, db: AsyncSession, user: User, auth0_org: Dict
    ) -> None:
        """Sync a single Auth0 organization to local database."""
        # Check if local organization exists by Auth0 ID
        local_org = await crud.organization.get_by_auth0_id(db, auth0_org["id"])

        if not local_org:
            # Create local organization
            local_org = Organization(
                name=auth0_org.get("display_name", auth0_org["name"]),
                description=f"Imported from Auth0: {auth0_org['name']}",
                auth0_org_id=auth0_org["id"],
            )
            db.add(local_org)
            await db.flush()
            logger.info(f"Created local organization for Auth0 org: {auth0_org['id']}")

        # Check if user-organization relationship exists
        try:
            # Create a temporary auth context for validation (user can access their own orgs)
            temp_auth_context = AuthContext(
                user=user, organization_id=str(local_org.id), auth_method="auth0"
            )

            # Try to get existing membership
            try:
                await crud.organization.get_user_membership(
                    db, local_org.id, user.id, temp_auth_context
                )
                # Membership exists, no need to create
                return
            except Exception:
                # Membership doesn't exist, create it
                pass

            # Determine if this should be primary (first org for user)
            user_orgs = await crud.organization.get_user_organizations_with_roles(
                db=db, user_id=user.id
            )
            is_primary = len(user_orgs) == 0

            # Create user-organization relationship using CRUD method
            await crud.organization.add_member(
                db=db,
                organization_id=local_org.id,
                user_id=user.id,
                role="member",  # Default role, could be enhanced based on Auth0 metadata
                auth_context=temp_auth_context,
                is_primary=is_primary,
            )
            logger.info(
                f"Created user-organization relationship for user {user.id} and org {local_org.id}"
            )

        except Exception as e:
            logger.warning(f"Failed to create user-organization relationship: {e}")
            # Continue processing other organizations

    async def _create_user_with_new_org(self, db: AsyncSession, user_data: Dict) -> User:
        """Create user with a new organization."""
        try:
            # Use the existing CRUD method that creates user with organization
            user_create = schemas.UserCreate(**user_data)
            user, org = await crud.user.create_with_organization(db, obj_in=user_create)

            logger.info(f"Created user {user.email} with new organization {org.name}")
            return user

        except Exception as e:
            logger.error(f"Failed to create user with new organization: {e}")
            raise

    async def _create_user_with_existing_orgs(
        self, db: AsyncSession, user_data: Dict, auth0_orgs: List[Dict]
    ) -> User:
        """Create user and sync with existing Auth0 organizations."""
        async with UnitOfWork(db) as uow:
            try:
                # Create user first without organization
                user_create = schemas.UserCreate(**user_data)
                user = User(**user_create.model_dump())
                db.add(user)
                await db.flush()  # Get the user ID

                # Sync organizations
                for auth0_org in auth0_orgs:
                    await self._sync_single_organization(db, user, auth0_org)

                await uow.commit()
                await db.refresh(user)

                logger.info(f"Created user {user.email} and synced {len(auth0_orgs)} organizations")
                return user

            except Exception as e:
                await uow.rollback()
                logger.error(f"Failed to create user with existing organizations: {e}")
                raise

    async def _create_user_without_org(self, db: AsyncSession, user_data: Dict) -> User:
        """Create user without an organization."""
        try:
            # Use the existing CRUD method that creates user without organization
            user_create = schemas.UserCreate(**user_data)
            user = User(**user_create.model_dump())
            db.add(user)
            await db.flush()  # Get the user ID
            await db.commit()  # Commit the transaction
            await db.refresh(user)  # Refresh to get the latest state

            logger.info(f"Created user {user.email} without an organization")
            return user

        except Exception as e:
            logger.error(f"Failed to create user without an organization: {e}")
            raise

    # Member Management Methods
    async def invite_user_to_organization(
        self,
        db: AsyncSession,
        organization_id: UUID,
        email: str,
        role: str,
        inviter_user: schemas.User,
    ) -> Dict:
        """Send organization invitation via Auth0."""
        # Create auth context for validation
        auth_context = AuthContext(
            user=inviter_user, organization_id=str(organization_id), auth_method="auth0"
        )

        # Get organization using CRUD method (validates access)
        org = await crud.organization.get(db=db, id=organization_id, auth_context=auth_context)

        # Send Auth0 invitation
        invitation = await auth0_management_client.invite_user_to_organization(
            org.auth0_org_id, email, role, inviter_user
        )
        logger.info(f"Successfully sent Auth0 invitation to {email} for organization {org.name}")
        return invitation

    async def delete_organization_with_auth0(
        self, db: AsyncSession, organization_id: UUID, deleting_user: User
    ) -> bool:
        """Delete organization from both local database and Auth0.

        Args:
            db: Database session
            organization_id: ID of the organization to delete
            deleting_user: User performing the deletion

        Returns:
            True if deletion was successful

        Raises:
            Exception: If deletion fails
        """
        # Create auth context for validation
        auth_context = AuthContext(
            user=deleting_user, organization_id=str(organization_id), auth_method="auth0"
        )

        # Get organization using CRUD method (validates access)
        org = await crud.organization.get(db=db, id=organization_id, auth_context=auth_context)

        logger.info(f"Starting deletion of organization {org.name} (ID: {organization_id})")

        try:
            # Delete from Auth0 first if it has an Auth0 org ID
            if org.auth0_org_id and auth0_management_client:
                try:
                    await auth0_management_client.delete_organization(org.auth0_org_id)
                    logger.info(f"Successfully deleted Auth0 organization: {org.auth0_org_id}")
                except Exception as e:
                    logger.warning(f"Failed to delete Auth0 organization {org.auth0_org_id}: {e}")
                    # Continue with local deletion even if Auth0 deletion fails
                    # This prevents the organization from being stuck in a partially deleted state

            # Delete from local database using existing CRUD method
            _ = await crud.organization.remove(db=db, id=organization_id)

            logger.info(f"Successfully deleted local organization: {org.name}")
            return True

        except Exception as e:
            logger.error(f"Failed to delete organization {org.name}: {e}")
            # If we deleted from Auth0 but failed locally, we should log this as a critical issue
            # In a production system, you might want to implement a cleanup/retry mechanism
            if org.auth0_org_id:
                logger.critical(
                    f"Organization {org.name} was deleted from Auth0 but failed to delete locally. "
                    f"Auth0 org ID: {org.auth0_org_id}, Local org ID: {organization_id}"
                )
            raise

    async def remove_pending_invitation(
        self, db: AsyncSession, organization_id: UUID, invitation_id: str, remover_user: User
    ) -> bool:
        """Remove a pending invitation."""
        # Create auth context for validation
        auth_context = AuthContext(
            user=remover_user, organization_id=str(organization_id), auth_method="auth0"
        )

        # Get organization using CRUD method (validates access)
        org = await crud.organization.get(db=db, id=organization_id, auth_context=auth_context)

        await auth0_management_client.delete_invitation(org.auth0_org_id, invitation_id)
        logger.info(f"Successfully removed invitation {invitation_id} from organization {org.name}")
        return True

    async def remove_member_from_organization(
        self, db: AsyncSession, organization_id: UUID, user_id: UUID, remover_user: User
    ) -> bool:
        """Remove a member from organization (both local and Auth0)."""
        # Create auth context for validation
        auth_context = AuthContext(
            user=remover_user, organization_id=str(organization_id), auth_method="auth0"
        )

        # Get the user to be removed using basic query (no org-specific CRUD needed for users)
        user_query = select(User).where(User.id == user_id)
        user_result = await db.execute(user_query)
        user_to_remove = user_result.scalar_one_or_none()

        if not user_to_remove:
            raise ValueError("User not found")

        # Get organization using CRUD method (validates access)
        org = await crud.organization.get(db=db, id=organization_id, auth_context=auth_context)

        # Remove from Auth0 first
        await auth0_management_client.remove_user_from_organization(
            org.auth0_org_id, user_to_remove.auth0_id
        )
        logger.info(f"Removed user {user_to_remove.email} from Auth0 organization {org.name}")

        # Remove from local database using CRUD method
        success = await crud.organization.remove_member(
            db=db,
            organization_id=organization_id,
            user_id=user_id,
            auth_context=auth_context,
        )

        if success:
            logger.info(
                f"Successfully removed user {user_to_remove.email} from organization {org.name}"
            )

        return success

    async def handle_user_leaving_organization(
        self, db: AsyncSession, organization_id: UUID, leaving_user: User
    ) -> bool:
        """Handle user leaving an organization."""
        # Use the existing remove_member_from_organization method
        # but with the user removing themselves
        return await self.remove_member_from_organization(
            db, organization_id, leaving_user.id, leaving_user
        )

    async def get_organization_members(
        self, db: AsyncSession, organization_id: UUID, requesting_user: User
    ) -> List[Dict]:
        """Get all members of an organization."""
        # Create auth context for validation
        auth_context = AuthContext(
            user=requesting_user, organization_id=str(organization_id), auth_method="auth0"
        )

        # Get organization members using CRUD method (validates access)
        members = await crud.organization.get_organization_members(
            db=db, organization_id=organization_id, auth_context=auth_context
        )

        # Format members for API response
        formatted_members = []
        for user_org in members:
            # Get user info from the relationship
            user_query = select(User).where(User.id == user_org.user_id)
            user_result = await db.execute(user_query)
            user = user_result.scalar_one()

            formatted_members.append(
                {
                    "id": str(user.id),
                    "email": user.email,
                    "name": user.full_name or user.email,
                    "role": user_org.role,
                    "status": "active",
                    "is_primary": user_org.is_primary,
                    "auth0_id": user.auth0_id,
                }
            )

        return formatted_members

    async def get_pending_invitations(
        self, db: AsyncSession, organization_id: UUID, requesting_user: User
    ) -> List[Dict]:
        """Get pending invitations for an organization."""
        # Create auth context for validation
        auth_context = AuthContext(
            user=requesting_user, organization_id=str(organization_id), auth_method="auth0"
        )

        # Get organization using CRUD method (validates access)
        org = await crud.organization.get(db=db, id=organization_id, auth_context=auth_context)

        auth0_invitations = await auth0_management_client.get_pending_invitations(org.auth0_org_id)

        # Format invitations
        invitations = []
        for invitation in auth0_invitations:
            invitations.append(
                {
                    "id": invitation.get("id"),
                    "email": invitation.get("invitee", {}).get("email"),
                    "role": invitation.get("app_metadata", {}).get("role", "member"),
                    "invited_at": invitation.get("created_at"),
                    "status": "pending",
                }
            )

        return invitations


organization_service = OrganizationService()
