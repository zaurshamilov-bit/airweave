"""Auth0 service for managing organization synchronization."""

import uuid
from typing import Dict, List, Tuple

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from airweave import crud, schemas
from airweave.core.logging import logger
from airweave.db.unit_of_work import UnitOfWork
from airweave.integrations.auth0_management import auth0_management_client
from airweave.models import Organization, User, UserOrganization


class Auth0Service:
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

        try:
            # First, try to create Auth0 organization if enabled
            if auth0_management_client.enabled and owner_user.auth0_id:
                logger.info(f"Creating Auth0 organization for: {org_data.name}")
                auth0_org_data = await auth0_management_client.create_organization(
                    name=self._create_org_name(org_data),
                    display_name=org_data.name,
                )

                # Add user to Auth0 organization as owner
                await auth0_management_client.add_user_to_organization(
                    auth0_org_data["id"], owner_user.auth0_id
                )

                logger.info(f"Successfully created Auth0 organization: {auth0_org_data['id']}")
        except Exception as e:
            logger.warning(f"Failed to create Auth0 organization, continuing with local-only: {e}")
            # Continue with local-only organization creation

        # Create local organization with Auth0 ID if available
        async with UnitOfWork(db) as uow:
            try:
                # Prepare organization data
                org_dict = org_data.model_dump()
                if auth0_org_data:
                    org_dict["auth0_org_id"] = auth0_org_data["id"]

                # Create organization using enhanced CRUD method
                local_org = await crud.organization.create_with_owner(
                    db=db,
                    obj_in=schemas.OrganizationCreate(**org_dict),
                    owner_user=owner_user,
                    uow=uow,
                )

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
                    await auth0_management_client.delete_organization(auth0_org_data["id"])
                raise

    async def handle_new_user_signup(self, db: AsyncSession, user_data: Dict) -> Tuple[User, str]:
        """Handle new user signup - check for Auth0 orgs or create new one.

        Args:
            db: Database session
            user_data: User data from signup

        Returns:
            Tuple of (created_user, signup_type)
        """
        auth0_id = user_data.get("auth0_id")

        if not auth0_id or not auth0_management_client.enabled:
            # No Auth0 ID or Auth0 not enabled, create user with new organization (local-only)
            return await self._create_user_with_new_org(db, user_data)

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
                # No Auth0 orgs, create user with new organization
                logger.info(
                    f"User {user_data.get('email')} has no Auth0 organizations, creating new org"
                )
                return await self._create_user_with_new_org(db, user_data)

        except Exception as e:
            logger.error(f"Failed to check Auth0 organizations for new user: {e}")
            # Fallback to creating local organization
            return await self._create_user_with_new_org(db, user_data)

    async def sync_user_organizations(self, db: AsyncSession, user: User) -> User:
        """Sync user's Auth0 organizations with local database.

        Args:
            db: Database session
            user: User to sync organizations for

        Returns:
            Updated user with synced organizations
        """
        if not user.auth0_id or not auth0_management_client.enabled:
            logger.info(
                f"Skipping Auth0 org sync for user {user.email} - no Auth0 ID or not enabled"
            )
            return user

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
        query = select(Organization).where(Organization.auth0_org_id == auth0_org["id"])
        result = await db.execute(query)
        local_org = result.scalar_one_or_none()

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
        query = select(UserOrganization).where(
            UserOrganization.user_id == user.id, UserOrganization.organization_id == local_org.id
        )
        result = await db.execute(query)
        existing_relationship = result.scalar_one_or_none()

        if not existing_relationship:
            # Determine if this should be primary (first org for user)
            query = select(UserOrganization).where(UserOrganization.user_id == user.id)
            result = await db.execute(query)
            user_org_count = len(result.scalars().all())
            is_primary = user_org_count == 0

            # Create user-organization relationship
            user_org = UserOrganization(
                user_id=user.id,
                organization_id=local_org.id,
                auth0_org_id=auth0_org["id"],
                role="member",  # Default role, could be enhanced based on Auth0 metadata
                is_primary=is_primary,
            )
            db.add(user_org)
            logger.info(
                f"Created user-organization relationship for user {user.id} and org {local_org.id}"
            )

    async def _create_user_with_new_org(
        self, db: AsyncSession, user_data: Dict
    ) -> Tuple[User, str]:
        """Create user with a new organization."""
        try:
            # Use the existing CRUD method that creates user with organization
            user_create = schemas.UserCreate(**user_data)
            user, org = await crud.user.create_with_organization(db, obj_in=user_create)

            logger.info(f"Created user {user.email} with new organization {org.name}")
            return user, "created_new_org"

        except Exception as e:
            logger.error(f"Failed to create user with new organization: {e}")
            raise

    async def _create_user_with_existing_orgs(
        self, db: AsyncSession, user_data: Dict, auth0_orgs: List[Dict]
    ) -> Tuple[User, str]:
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
                return user, "synced_existing_orgs"

            except Exception as e:
                await uow.rollback()
                logger.error(f"Failed to create user with existing organizations: {e}")
                raise


auth0_service = Auth0Service()
