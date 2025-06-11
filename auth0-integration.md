# Airweave Auth0 Organizations Integration - Final Implementation Design

## Current Implementation Status ✅

Based on analysis of the codebase, you have successfully implemented:

- **Backend Infrastructure**: Enhanced `deps.py` with `AuthContext`, updated CRUD layer with `_base_organization.py`
- **Data Models**: `User`, `Organization`, `UserOrganization` with proper Auth0 fields (`auth0_id`, `auth0_org_id`)
- **API Layer**: Organization endpoints with proper access controls
- **Frontend Infrastructure**: Organization store, API client with context headers, settings UI
- **Basic Flows**: Login/callback, organization CRUD, user management

## Remaining Implementation: Auth0 Management API Integration

The final steps require integrating with Auth0's Management API to sync organizations and handle invitations.

---

## Phase 1: Auth0 Management API Client

### New File: `backend/airweave/integrations/auth0_management.py`

```python
from typing import Dict, List, Optional
import httpx
from airweave.core.config import settings
from airweave.core.logging import logger

class Auth0ManagementClient:
    def __init__(self):
        self.domain = settings.AUTH0_DOMAIN
        self.client_id = settings.AUTH0_M2M_CLIENT_ID  # Machine-to-machine app
        self.client_secret = settings.AUTH0_M2M_CLIENT_SECRET
        self.audience = f"https://{self.domain}/api/v2/"
        self._token: Optional[str] = None

    async def _get_management_token(self) -> str:
        """Get Auth0 Management API access token."""
        if self._token:
            return self._token

        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"https://{self.domain}/oauth/token",
                json={
                    "client_id": self.client_id,
                    "client_secret": self.client_secret,
                    "audience": self.audience,
                    "grant_type": "client_credentials"
                }
            )
            response.raise_for_status()
            data = response.json()
            self._token = data["access_token"]
            return self._token

    async def get_user_organizations(self, auth0_user_id: str) -> List[Dict]:
        """Get organizations a user belongs to."""
        token = await self._get_management_token()
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"https://{self.domain}/api/v2/users/{auth0_user_id}/organizations",
                headers={"Authorization": f"Bearer {token}"}
            )
            response.raise_for_status()
            return response.json()

    async def create_organization(self, name: str, display_name: str) -> Dict:
        """Create a new Auth0 organization."""
        token = await self._get_management_token()
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"https://{self.domain}/api/v2/organizations",
                headers={"Authorization": f"Bearer {token}"},
                json={
                    "name": name.lower().replace(" ", "-"),  # Auth0 org names must be lowercase
                    "display_name": display_name
                }
            )
            response.raise_for_status()
            return response.json()

    async def add_user_to_organization(self, org_id: str, user_id: str, roles: List[str] = None) -> None:
        """Add user to Auth0 organization."""
        token = await self._get_management_token()
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"https://{self.domain}/api/v2/organizations/{org_id}/members",
                headers={"Authorization": f"Bearer {token}"},
                json={"users": [user_id]}
            )
            response.raise_for_status()

    async def invite_user_to_organization(self, org_id: str, email: str, role: str = "member") -> Dict:
        """Send Auth0 organization invitation."""
        token = await self._get_management_token()
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"https://{self.domain}/api/v2/organizations/{org_id}/invitations",
                headers={"Authorization": f"Bearer {token}"},
                json={
                    "inviter": {"name": "Airweave Platform"},
                    "invitee": {"email": email},
                    "client_id": settings.AUTH0_CLIENT_ID,
                    "app_metadata": {"role": role}
                }
            )
            response.raise_for_status()
            return response.json()

    async def get_pending_invitations(self, org_id: str) -> List[Dict]:
        """Get pending invitations for organization."""
        token = await self._get_management_token()
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"https://{self.domain}/api/v2/organizations/{org_id}/invitations",
                headers={"Authorization": f"Bearer {token}"}
            )
            response.raise_for_status()
            return response.json()
```

---

## Phase 2: Auth0 Service

### New File: `backend/airweave/core/auth0_service.py`

```python
from typing import Dict, List, Optional, Tuple
from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from airweave import crud, schemas
from airweave.integrations.auth0_management import Auth0ManagementClient
from airweave.models import User, Organization, UserOrganization
from airweave.core.logging import logger
from airweave.db.unit_of_work import UnitOfWork

class Auth0SyncService:
    def __init__(self):
        self.auth0_client = Auth0ManagementClient()


    async def handle_new_user_signup(
        self,
        db: AsyncSession,
        user_data: Dict
    ) -> Tuple[User, Optional[str]]:
        """Handle new user signup - check for Auth0 orgs or create new one."""

        if not user_data.get("auth0_id"):
            # No Auth0 ID, create user with new organization (local-only)
            return await self._create_user_with_new_org(db, user_data)

        try:
            # Check if user has existing Auth0 organizations
            auth0_orgs = await self.auth0_client.get_user_organizations(user_data["auth0_id"])

            if auth0_orgs:
                # User has Auth0 organizations, sync them
                return await self._create_user_with_existing_orgs(db, user_data, auth0_orgs)
            else:
                # No Auth0 orgs, create user with new organization
                return await self._create_user_with_new_org(db, user_data)

        except Exception as e:
            logger.error(f"Failed to check Auth0 organizations for new user: {e}")
            # Fallback to creating local organization
            return await self._create_user_with_new_org(db, user_data)

    async def create_organization_with_auth0(
        self,
        db: AsyncSession,
        org_data: schemas.OrganizationCreate,
        owner_user: User
    ) -> Organization:
        """Create organization and sync with Auth0."""

        try:
            # Create Auth0 organization first
            auth0_org = await self.auth0_client.create_organization(
                name=f"airweave-{org_data.name.lower().replace(' ', '-')}",
                display_name=org_data.name
            )

            # Add user to Auth0 organization
            if owner_user.auth0_id:
                await self.auth0_client.add_user_to_organization(
                    auth0_org["id"], owner_user.auth0_id
                )

            # Create local organization with Auth0 ID
            org_dict = org_data.model_dump()
            org_dict["auth0_org_id"] = auth0_org["id"]

            local_org = await crud.organization.create_with_owner(
                db=db,
                obj_in=schemas.OrganizationCreate(**org_dict),
                owner_user=owner_user
            )

            return local_org

        except Exception as e:
            logger.error(f"Failed to create Auth0 organization: {e}")
            # Fallback to local-only organization
            return await crud.organization.create_with_owner(
                db=db, obj_in=org_data, owner_user=owner_user
            )

    async def invite_user_to_organization(
        self,
        db: AsyncSession,
        organization_id: UUID,
        email: str,
        role: str,
        inviter_user: User
    ) -> Dict:
        """Send organization invitation via Auth0."""

        # Get organization
        org = await crud.organization.get(
            db, id=organization_id,
            auth_context=schemas.AuthContext(
                organization_id=str(organization_id),
                user=inviter_user,
                auth_method="auth0"
            )
        )

        if not org.auth0_org_id:
            raise ValueError("Organization not linked to Auth0")

        try:
            # Send Auth0 invitation
            invitation = await self.auth0_client.invite_user_to_organization(
                org.auth0_org_id, email, role
            )

            # Store invitation record locally for tracking
            # (You may want to create an Invitation model for this)

            return invitation

        except Exception as e:
            logger.error(f"Failed to send Auth0 invitation: {e}")
            raise

    # Private helper methods
    async def _sync_single_organization(
        self, db: AsyncSession, user: User, auth0_org: Dict
    ) -> None:
        """Sync a single Auth0 organization to local database."""

        # Check if local organization exists
        local_org = await crud.organization.get_by_auth0_id(db, auth0_org["id"])

        if not local_org:
            # Create local organization
            local_org = Organization(
                name=auth0_org.get("display_name", auth0_org["name"]),
                description=f"Imported from Auth0: {auth0_org['name']}",
                auth0_org_id=auth0_org["id"]
            )
            db.add(local_org)
            await db.flush()

        # Check if user-organization relationship exists
        existing_relationship = await db.execute(
            select(UserOrganization).where(
                UserOrganization.user_id == user.id,
                UserOrganization.organization_id == local_org.id
            )
        )

        if not existing_relationship.scalar_one_or_none():
            # Create user-organization relationship
            # Determine if this should be primary (first org for user)
            user_org_count = len(user.user_organizations)
            is_primary = user_org_count == 0

            user_org = UserOrganization(
                user_id=user.id,
                organization_id=local_org.id,
                auth0_org_id=auth0_org["id"],
                role="member",  # Default role, could be enhanced
                is_primary=is_primary
            )
            db.add(user_org)

    async def _create_user_with_new_org(
        self, db: AsyncSession, user_data: Dict
    ) -> Tuple[User, str]:
        """Create user with a new organization."""

        user_create = schemas.UserCreate(**user_data)
        user, org = await crud.user.create_with_organization(db, obj_in=user_create)

        return user, "created_new_org"

    async def _create_user_with_existing_orgs(
        self, db: AsyncSession, user_data: Dict, auth0_orgs: List[Dict]
    ) -> Tuple[User, str]:
        """Create user and sync with existing Auth0 organizations."""

        # Create user first
        user_create = schemas.UserCreate(**user_data)
        # Remove organization creation for now
        user = User(**user_create.model_dump())
        db.add(user)
        await db.flush()

        # Sync organizations
        for auth0_org in auth0_orgs:
            await self._sync_single_organization(db, user, auth0_org)

        await db.commit()
        await db.refresh(user)

        return user, "synced_existing_orgs"
```

---

## Phase 3: Enhanced Login/Callback Flow

### Update: `backend/airweave/api/v1/endpoints/users.py`

```python
# Add new endpoint
@router.post("/create_or_update", response_model=schemas.User)
async def create_or_update_user(
    user_data: schemas.UserCreateOrUpdate,
    db: AsyncSession = Depends(deps.get_db),
) -> schemas.User:
    """Create or update user with Auth0 organization sync."""
    from airweave.core.auth0_sync_service import Auth0SyncService

    sync_service = Auth0SyncService()

    # Check if user already exists
    existing_user = await crud.user.get_by_email(db, email=user_data.email)

    if existing_user:
        # Update existing user and sync organizations
        updated_user = await crud.user.update(
            db, db_obj=existing_user, obj_in=user_data
        )
        # Sync Auth0 organizations
        return await sync_service.sync_user_organizations(db, updated_user)
    else:
        # Handle new user signup with Auth0 organization sync
        user, signup_type = await sync_service.handle_new_user_signup(
            db, user_data.model_dump()
        )

        logger.info(f"New user signup: {user.email}, type: {signup_type}")
        return user
```

### Update: `frontend/src/pages/Callback.tsx`

```typescript
// Enhanced callback to handle different signup scenarios
useEffect(() => {
  const syncUser = async () => {
    if (isAuthenticated && user && !isLoading) {
      try {
        const token = await getToken();
        if (!token) {
          console.error("No token available for API call");
          navigate('/');
          return;
        }

        const userData = {
          email: user.email,
          full_name: user.name,
          picture: user.picture,
          auth0_id: user.sub,
          email_verified: user.email_verified,
        };

        // Enhanced user sync with organization handling
        const response = await apiClient.post('/users/create_or_update', userData);

        if (response.ok) {
          const userResponse = await response.json();
          console.log("✅ User synced with organizations:", userResponse);

          // Initialize organizations in store
          const { initializeOrganizations } = useOrganizationStore.getState();
          await initializeOrganizations();
        }

        navigate('/');
      } catch (err) {
        console.error("❌ Error syncing user:", err);
        navigate('/');
      }
    }
  };

  syncUser();
}, [isAuthenticated, user, isLoading, getToken, navigate]);
```

---

## Phase 4: Enhanced Organization Management

### Update: `backend/airweave/api/v1/endpoints/organizations.py`

```python
# Add Auth0 sync to create endpoint
@router.post("/", response_model=schemas.OrganizationWithRole)
async def create_organization(
    organization_data: schemas.OrganizationCreate,
    db: AsyncSession = Depends(deps.get_db),
    auth_context: AuthContext = Depends(deps.get_auth_context),
) -> schemas.OrganizationWithRole:
    """Create organization with Auth0 sync."""
    from airweave.core.auth0_sync_service import Auth0SyncService

    sync_service = Auth0SyncService()

    # Create organization with Auth0 integration
    organization = await sync_service.create_organization_with_auth0(
        db=db,
        org_data=organization_data,
        owner_user=auth_context.user
    )

    return schemas.OrganizationWithRole(
        id=organization.id,
        name=organization.name,
        description=organization.description or "",
        created_at=organization.created_at,
        modified_at=organization.modified_at,
        role="owner",
        is_primary=False,
    )

# Add invitation endpoint
@router.post("/{organization_id}/invite", response_model=dict)
async def invite_user_to_organization(
    organization_id: UUID,
    invitation_data: schemas.InvitationCreate,
    db: AsyncSession = Depends(deps.get_db),
    auth_context: AuthContext = Depends(deps.get_auth_context),
) -> dict:
    """Send organization invitation via Auth0."""
    from airweave.core.auth0_sync_service import Auth0SyncService

    sync_service = Auth0SyncService()

    try:
        invitation = await sync_service.invite_user_to_organization(
            db=db,
            organization_id=organization_id,
            email=invitation_data.email,
            role=invitation_data.role,
            inviter_user=auth_context.user
        )

        return {"message": "Invitation sent successfully", "invitation_id": invitation["id"]}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
```

---

## Phase 5: Frontend Integration

### Update: `frontend/src/components/settings/MembersSettings.tsx`

```typescript
// Replace dummy invite function with real API call
const handleInvite = async () => {
  if (!inviteEmail || emailError) return;

  try {
    setIsInviting(true);

    const response = await apiClient.post(
      `/organizations/${currentOrganization.id}/invite`,
      {
        email: inviteEmail,
        role: inviteRole
      }
    );

    if (!response.ok) {
      const errorData = await response.json().catch(() => ({}));
      throw new Error(errorData.detail || `Failed to send invitation: ${response.status}`);
    }

    const result = await response.json();

    // Add to pending invitations list
    const newInvitation: PendingInvitation = {
      id: result.invitation_id,
      email: inviteEmail,
      role: inviteRole,
      invited_at: new Date().toISOString(),
      status: 'pending',
    };

    setPendingInvitations(prev => [...prev, newInvitation]);
    setInviteEmail('');
    setInviteRole('member');
    toast.success('Invitation sent successfully');

  } catch (error) {
    console.error('Failed to send invitation:', error);
    toast.error('Failed to send invitation');
  } finally {
    setIsInviting(false);
  }
};
```

---

## Configuration Requirements

### Environment Variables

Add to `.env`:

```bash
# Auth0 Management API (Machine-to-Machine Application)
AUTH0_M2M_CLIENT_ID=your_m2m_client_id
AUTH0_M2M_CLIENT_SECRET=your_m2m_client_secret

# Existing Auth0 variables
AUTH0_DOMAIN=your-domain.auth0.com
AUTH0_CLIENT_ID=your_spa_client_id
```

### Auth0 Setup

1. **Create Machine-to-Machine Application** in Auth0 Dashboard
2. **Authorize for Management API** with scopes:
   - `read:organizations`
   - `create:organizations`
   - `update:organizations`
   - `read:organization_members`
   - `create:organization_members`
   - `create:organization_invitations`
   - `read:organization_invitations`

---

## Migration Strategy

For existing organizations without Auth0 IDs:

1. **Lazy Migration**: Sync with Auth0 when user first accesses org features
2. **Graceful Degradation**: Continue working if Auth0 sync fails
3. **Manual Sync**: Admin endpoint to force sync existing organizations

## Error Handling Strategy

- **Auth0 API Failures**: Log errors, continue with local-only operations
- **Token Expiration**: Auto-refresh management API tokens
- **Rate Limiting**: Implement backoff strategies for Auth0 API calls
- **Sync Conflicts**: Prefer Auth0 data over local data when conflicts occur

This design maintains backward compatibility while adding powerful Auth0 Organizations integration for new workflows.
