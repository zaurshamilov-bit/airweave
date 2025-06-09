# Airweave Organization Scoping: Comprehensive Implementation Design

## Executive Summary

This document provides a comprehensive plan for transitioning Airweave from its current auto-organization model to a full Auth0 Organizations integration supporting invitation flows, multi-organization users, and proper organization scoping. The design leverages existing organizational infrastructure while adding Auth0 Management API integration.

---

## Current Architecture Analysis

### Authentication Flow
**Current State**:
- Frontend: Auth0Provider → React Auth Context → Callback page
- Backend: Auth0 JWT validation + API key fallback in `deps.get_user()`
- User sync: Callback page calls `/users/create_or_update` endpoint

**Key Files**:
- `frontend/src/lib/auth0-provider.tsx` - Auth0 React integration
- `frontend/src/pages/Callback.tsx` - User sync after auth
- `backend/airweave/api/deps.py` - User authentication dependency
- `backend/airweave/api/auth.py` - Auth0 JWT validation

### Data Model (Current)
**Organization Scoping Infrastructure**:
```python
# Already implemented patterns:
class OrganizationBase(Base):  # base.py
    organization_id = Column(UUID, ForeignKey("organization.id"), nullable=False)

class User(OrganizationBase):  # user.py
    auth0_id: Mapped[str] = mapped_column(String, unique=True, nullable=True)
    organization: Mapped["Organization"] = relationship("Organization")

class Organization(Base):  # organization.py
    users: Mapped[List["User"]] = relationship("User", back_populates="organization")
```

**CRUD Patterns**:
- `CRUDBase`: User permissions + org scoping (`current_user.organization_id`)
- `CRUDBaseOrganization`: Pure organization scoping (`organization_id` parameter)

### API Layer (Current)
**Organization Enforcement Pattern**:
```python
# Every endpoint uses this pattern:
async def endpoint(
    auth_context: AuthContext = Depends(deps.get_auth_context),
    db: AsyncSession = Depends(deps.get_db)
):
    # Auto-scoped by current_user.organization_id
    return await crud.entity.get_multi(
        db, organization_id=current_user.organization_id
    )
```

---

## Target Architecture: Auth0 Organizations Integration

### Core Objectives
1. **Seamless Migration**: Existing single-org users continue working
2. **Invitation Flows**: Auth0-managed organization invitations
3. **Multi-Organization Support**: Users can belong to multiple organizations
4. **Permission Enforcement**: Organization-scoped API access
5. **Frontend UX**: Organization context switching

---

## Frontend State Management & Organization Context - IMPLEMENTED

### State Management Summary

The frontend now uses Zustand stores for clean state management:

**Auth Store (`frontend/src/stores/auth-store.ts`)**:
- Manages user authentication state (without storing tokens - Auth0 handles that)
- Persists user information across sessions
- Integrates with existing Auth0 provider

**Organization Store (`frontend/src/stores/organization-store.ts`)**:
- Manages list of user's organizations and current context
- Handles organization switching logic
- Persists current organization selection

### Enhanced API Client - IMPLEMENTED

**API Client (`frontend/src/lib/api.ts`)**:
- Automatically includes `X-Organization-ID` header in requests
- Provides `switchOrganization()` method for context switching
- Integrates with organization store for seamless context management

### Organization Context Hook - IMPLEMENTED

**Organization Hook (`frontend/src/hooks/use-organization-context.tsx`)**:
- Fetches user organizations on authentication
- Provides actions: `switchOrganization`, `inviteUser`, `leaveOrganization`
- Manages loading states and error handling

**Organization Provider (`frontend/src/providers/OrganizationProvider.tsx`)**:
- Provides organization context to entire application
- Wraps the organization hook for dependency injection

### Enhanced UserProfileDropdown - IMPLEMENTED

**Key Features (`frontend/src/components/UserProfileDropdown.tsx`)**:
- Shows current organization name and user role badge
- Organization switcher submenu for multi-org users
- Role-based icons (Crown for owners, Shield for admins, Users for members)
- Quick access to organization management (Invite Members, Organization Settings)
- Maintains all existing external links and account settings

### Organization Management Pages - IMPLEMENTED

**Organization Settings (`frontend/src/pages/organization/OrganizationSettings.tsx`)**:
- Edit organization name and description
- Display organization ID with copy functionality
- Role-based permissions (only owners/admins can edit)
- Danger zone for organization deletion (owners only)

**Organization Members (`frontend/src/pages/organization/OrganizationMembers.tsx`)**:
- Invite new members with role selection (member/admin)
- View current members with role badges and status
- Pending invitations table with status tracking
- Member management actions (for future implementation)

---

## Implementation Plan

## CRUD Layer Practical Refactoring Strategy

### Current Model Patterns Analysis

Based on the actual model inheritance patterns in the codebase:

**Model Inheritance Patterns**:
- **Base only**: System-wide resources (some with nullable organization_id)
- **OrganizationBase**: Has `organization_id` (required organization scoping)
- **UserMixin**: Has `created_by_email` and `modified_by_email` (user tracking)
- **OrganizationBase + UserMixin**: User-owned resources within organization context

### Proposed CRUD Architecture

**1. CRUDUser**: Pure user-level data
- **Models**: User, future UserPreferences
- **Pattern**: User-specific data, checks on user identity
- **Example**: User profile, preferences, user-organization relationships

**2. CRUDBaseOrganization**: Organization-scoped resources (unified pattern)
- **Models**: All OrganizationBase models (Collection, SourceConnection, Entity, APIKey, etc.)
- **Configuration Flags**:
  - `track_user: bool` - Whether model has UserMixin (created_by_email, modified_by_email)
- **Access Patterns**:
  - All organization members can access resources within their organization scope
  - User tracking for auditing purposes only (no ownership restrictions)
- **API Pattern**: Unified organization-scoped endpoints

**3. CRUDPublic**: System-wide resources
- **Models**: Source, Destination, EntityDefinition, Transformer (Base with no organization_id)
- **Pattern**: Available to all authenticated users, optionally organization-specific
- **Access**: No organization filtering (or filtered by nullable organization_id)

### Implementation Strategy

**Enhanced File**: `backend/airweave/crud/_base_organization.py`
```python
from typing import Generic, Optional, Type, TypeVar
from uuid import UUID
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from airweave.core.exceptions import PermissionException
from airweave.models._base import Base
from airweave.schemas import User

ModelType = TypeVar("ModelType", bound=Base)
CreateSchemaType = TypeVar("CreateSchemaType", bound=BaseModel)
UpdateSchemaType = TypeVar("UpdateSchemaType", bound=BaseModel)

class CRUDBaseOrganization(Generic[ModelType, CreateSchemaType, UpdateSchemaType]):
    """Unified CRUD for all organization-scoped resources."""

    def __init__(self, model: Type[ModelType], track_user: bool = True):
        self.model = model
        self.track_user = track_user  # Whether model has UserMixin

    async def get(
        self,
        db: AsyncSession,
        id: UUID,
        current_user: User,
        organization_id: Optional[UUID] = None
    ) -> Optional[ModelType]:
        """Get organization resource."""
        effective_org_id = organization_id or current_user.current_organization_id

        # Validate user has org access
        await self._validate_organization_access(db, current_user, effective_org_id)

        query = select(self.model).where(
            self.model.id == id,
            self.model.organization_id == effective_org_id
        )

        result = await db.execute(query)
        return result.unique().scalar_one_or_none()

    async def get_multi(
        self,
        db: AsyncSession,
        current_user: User,
        organization_id: Optional[UUID] = None,
        *,
        skip: int = 0,
        limit: int = 100
    ) -> list[ModelType]:
        """Get all resources for organization."""
        effective_org_id = organization_id or current_user.current_organization_id

        # Validate user has org access
        await self._validate_organization_access(db, current_user, effective_org_id)

        query = select(self.model).where(
            self.model.organization_id == effective_org_id
        ).offset(skip).limit(limit)

        result = await db.execute(query)
        return list(result.unique().scalars().all())

    async def create(
        self,
        db: AsyncSession,
        *,
        obj_in: CreateSchemaType,
        current_user: User,
        organization_id: Optional[UUID] = None
    ) -> ModelType:
        """Create organization resource."""
        effective_org_id = organization_id or current_user.current_organization_id

        # Validate user has org access
        await self._validate_organization_access(db, current_user, effective_org_id)

        if not isinstance(obj_in, dict):
            obj_in = obj_in.model_dump(exclude_unset=True)

        obj_in['organization_id'] = effective_org_id

        if self.track_user:
            obj_in['created_by_email'] = current_user.email
            obj_in['modified_by_email'] = current_user.email

        db_obj = self.model(**obj_in)
        db.add(db_obj)
        await db.commit()
        await db.refresh(db_obj)
        return db_obj

    async def update(
        self,
        db: AsyncSession,
        *,
        db_obj: ModelType,
        obj_in: UpdateSchemaType,
        current_user: User
    ) -> ModelType:
        """Update organization resource."""
        if not isinstance(obj_in, dict):
            obj_in = obj_in.model_dump(exclude_unset=True)

        if self.track_user:
            obj_in['modified_by_email'] = current_user.email

        for field, value in obj_in.items():
            setattr(db_obj, field, value)

        await db.commit()
        await db.refresh(db_obj)
        return db_obj

    async def _validate_organization_access(
        self,
        db: AsyncSession,
        user: User,
        organization_id: UUID
    ) -> None:
        """Validate user has access to organization."""
        # This will query UserOrganization table in final implementation
        # For now, just check primary organization
        if organization_id != user.organization_id:
            raise PermissionException(f"User does not have access to organization {organization_id}")
```

**New File**: `backend/airweave/crud/_base_user.py`
```python
from typing import Generic, Optional, Type, TypeVar
from uuid import UUID
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from airweave.core.exceptions import PermissionException
from airweave.models._base import Base
from airweave.schemas import User

ModelType = TypeVar("ModelType", bound=Base)
CreateSchemaType = TypeVar("CreateSchemaType", bound=BaseModel)
UpdateSchemaType = TypeVar("UpdateSchemaType", bound=BaseModel)

class CRUDUser(Generic[ModelType, CreateSchemaType, UpdateSchemaType]):
    """CRUD for pure user-level data."""

    def __init__(self, model: Type[ModelType]):
        self.model = model

    async def get(self, db: AsyncSession, id: UUID, current_user: User) -> Optional[ModelType]:
        """Get user data - must be same user."""
        if id != current_user.id:
            raise PermissionException("Cannot access other user's data")

        result = await db.execute(select(self.model).where(self.model.id == id))
        return result.unique().scalar_one_or_none()
```

**New File**: `backend/airweave/crud/_base_public.py`
```python
class CRUDPublic(Generic[ModelType, CreateSchemaType, UpdateSchemaType]):
    """CRUD for system-wide public resources."""

    def __init__(self, model: Type[ModelType]):
        self.model = model

    async def get(self, db: AsyncSession, id: UUID) -> Optional[ModelType]:
        """Get public resource - no access control."""
        result = await db.execute(select(self.model).where(self.model.id == id))
        return result.unique().scalar_one_or_none()

    async def get_multi(
        self,
        db: AsyncSession,
        organization_id: Optional[UUID] = None,
        *, skip: int = 0, limit: int = 100
    ) -> list[ModelType]:
        """Get public resources, optionally filtered by organization."""
        query = select(self.model)

        # If model has organization_id, filter by it
        if hasattr(self.model, 'organization_id') and organization_id:
            query = query.where(
                (self.model.organization_id == organization_id) |
                (self.model.organization_id.is_(None))  # Include system-wide
            )

        query = query.offset(skip).limit(limit)
        result = await db.execute(query)
        return list(result.unique().scalars().all())
```

### Migration Plan for Existing CRUD Classes

**Step 1: Update Existing Classes with Unified Pattern**
```python
# Resources with user tracking
class CRUDCollection(CRUDBaseOrganization[Collection, CollectionCreate, CollectionUpdate]):
    def __init__(self):
        super().__init__(Collection, track_user=True)

class CRUDSourceConnection(CRUDBaseOrganization[SourceConnection, SourceConnectionCreate, SourceConnectionUpdate]):
    def __init__(self):
        super().__init__(SourceConnection, track_user=True)

class CRUDWhiteLabel(CRUDBaseOrganization[WhiteLabel, WhiteLabelCreate, WhiteLabelUpdate]):
    def __init__(self):
        super().__init__(WhiteLabel, track_user=True)

class CRUDAPIKey(CRUDBaseOrganization[APIKey, APIKeyCreate, APIKeyUpdate]):
    def __init__(self):
        super().__init__(APIKey, track_user=True)

class CRUDIntegrationCredential(CRUDBaseOrganization[IntegrationCredential, IntegrationCredentialCreate, IntegrationCredentialUpdate]):
    def __init__(self):
        super().__init__(IntegrationCredential, track_user=True)

# Resources without user tracking
class CRUDEntity(CRUDBaseOrganization[Entity, EntityCreate, EntityUpdate]):
    def __init__(self):
        super().__init__(Entity, track_user=False)

class CRUDSync(CRUDBaseOrganization[Sync, SyncCreate, SyncUpdate]):
    def __init__(self):
        super().__init__(Sync, track_user=False)

class CRUDSyncJob(CRUDBaseOrganization[SyncJob, SyncJobCreate, SyncJobUpdate]):
    def __init__(self):
        super().__init__(SyncJob, track_user=False)

# Public resources (unchanged)
class CRUDSource(CRUDPublic[Source, SourceCreate, SourceUpdate]):
    def __init__(self):
        super().__init__(Source)
```

**Step 2: API Layer Updates with Simplified Endpoints**
```python
# All organization-scoped resources use the same pattern
@router.get("/collections/", response_model=List[schemas.Collection])
async def list_collections(
    auth_context: AuthContext = Depends(deps.get_auth_context),
    db: AsyncSession = Depends(deps.get_db),
):
    """List all collections in current organization."""
    return await crud.collection.get_multi(db, current_user)

@router.get("/entities/", response_model=List[schemas.Entity])
async def list_entities(
    auth_context: AuthContext = Depends(deps.get_auth_context),
    db: AsyncSession = Depends(deps.get_db),
):
    """List all entities in current organization."""
    return await crud.entity.get_multi(db, current_user)

@router.get("/api-keys/", response_model=List[schemas.APIKey])
async def list_api_keys(
    auth_context: AuthContext = Depends(deps.get_auth_context),
    db: AsyncSession = Depends(deps.get_db),
):
    """List all API keys in current organization."""
    return await crud.api_key.get_multi(db, current_user)
```

### Model Classification Summary

**CRUDUser**:
- User (self-management only)
- Future: UserPreferences

**CRUDBaseOrganization** (unified with track_user flag):
- **With user tracking** (`track_user=True`): Collection, SourceConnection, WhiteLabel, APIKey, IntegrationCredential
- **Without user tracking** (`track_user=False`): Entity, Sync, SyncJob, DAG, Connection

**CRUDPublic** (Base, optional nullable organization_id):
- Source, Destination
- EntityDefinition
- Transformer, EmbeddingModel

This approach provides clean organization scoping without complex ownership logic, while maintaining user tracking for auditing purposes where needed.

---

## API Key Context Management via Dependency Injection

### Problem Statement
API keys need organization-scoped access without user-level ownership conflicts. The challenge is maintaining audit trails while allowing organization members to access API-key-created resources.

### Solution: Unified AuthContext for All Authentication Methods

**AuthContext Schema**:
```python
# backend/airweave/schemas/auth.py
class AuthContext(BaseModel):
    """Unified authentication context for all auth methods."""
    organization_id: UUID
    user: Optional[User] = None
    auth_method: str  # "auth0", "api_key", "system"

    # Auth method specific metadata
    auth_metadata: Optional[Dict[str, Any]] = None

    @property
    def has_user_context(self) -> bool:
        """Whether this context has user info for tracking."""
        return self.user is not None

    @property
    def tracking_email(self) -> Optional[str]:
        """Email to use for UserMixin tracking."""
        return self.user.email if self.user else None
```

**Updated Authentication Dependencies**:
```python
# backend/airweave/api/deps.py
async def get_auth_context(
    db: AsyncSession = Depends(get_db),
    x_api_key: Optional[str] = Header(None),
    auth0_user: Optional[Auth0User] = Depends(auth0.get_user),
) -> AuthContext:

    if auth0_user:
        # Human user via Auth0
        user = await crud.user.get_by_email(db, email=auth0_user.email)
        return AuthContext(
            organization_id=user.organization_id,
            user=user,
            auth_method="auth0",
            auth_metadata={"auth0_id": auth0_user.id}
        )

    elif x_api_key:
        # API key authentication - organization context only
        api_key_obj = await crud.api_key.get_by_key(db, key=x_api_key)
        return AuthContext(
            organization_id=api_key_obj.organization_id,
            user=None,  # API key outlives users
            auth_method="api_key",
            auth_metadata={
                "api_key_id": str(api_key_obj.id),
                "created_by": api_key_obj.created_by_email  # Audit only
            }
        )

    raise HTTPException(status_code=401, detail="No valid authentication")

# Backward compatibility wrapper
async def get_user(
    auth_context: AuthContext = Depends(get_auth_context)
) -> User:
    """Legacy dependency for endpoints that expect User."""
    if not auth_context.user:
        raise HTTPException(status_code=401, detail="User context required")
    return auth_context.user
```

**CRUD Layer Mapping to AuthContext**:

| CRUD Class | Model Mixins | AuthContext Needs | Behavior |
|------------|--------------|-------------------|----------|
| `CRUDBaseOrganization(track_user=True)` | OrganizationBase + UserMixin | `organization_id` + `tracking_email` | Org scoping + user tracking |
| `CRUDBaseOrganization(track_user=False)` | OrganizationBase only | `organization_id` only | Org scoping only |
| `CRUDUser` | Base + UserMixin | `user` required | User-level access |
| `CRUDPublic` | Base only | None (open access) | System-wide resources |

**Updated CRUD Organization**:
```python
# backend/airweave/crud/_base_organization.py
class CRUDBaseOrganization(Generic[ModelType, CreateSchemaType, UpdateSchemaType]):

    def __init__(self, model: Type[ModelType], track_user: bool = True):
        self.model = model
        self.track_user = track_user

    async def create(
        self,
        db: AsyncSession,
        *,
        obj_in: CreateSchemaType,
        auth_context: AuthContext,
        organization_id: Optional[UUID] = None
    ) -> ModelType:
        """Create organization resource with auth context."""
        effective_org_id = organization_id or auth_context.organization_id

        # Validate org access
        await self._validate_organization_access(auth_context, effective_org_id)

        if not isinstance(obj_in, dict):
            obj_in = obj_in.model_dump(exclude_unset=True)

        obj_in["organization_id"] = effective_org_id

        if self.track_user:
            if auth_context.has_user_context:
                # Human user: track directly
                obj_in["created_by_email"] = auth_context.tracking_email
                obj_in["modified_by_email"] = auth_context.tracking_email
            else:
                # API key/system: nullable tracking
                obj_in["created_by_email"] = None
                obj_in["modified_by_email"] = None

        db_obj = self.model(**obj_in)
        db.add(db_obj)
        await db.commit()
        await db.refresh(db_obj)
        return db_obj

    async def _validate_organization_access(
        self,
        auth_context: AuthContext,
        organization_id: UUID
    ) -> None:
        """Validate auth context has access to organization."""
        if organization_id != auth_context.organization_id:
            raise PermissionException(
                f"Auth context does not have access to organization {organization_id}"
            )
```

**Updated Model Mixins**:
```python
# backend/airweave/models/_base.py
class UserMixin:
    """Mixin for adding nullable user tracking to a model."""

    @declared_attr
    def created_by_email(cls):
        return Column(String, nullable=True)  # ← Made nullable

    @declared_attr
    def modified_by_email(cls):
        return Column(String, nullable=True)  # ← Made nullable
```

### API Endpoint Patterns

**Option 1: New AuthContext Pattern (Recommended)**:
```python
@router.post("/collections/")
async def create_collection(
    collection_data: CollectionCreate,
    auth_context: AuthContext = Depends(get_auth_context),
    db: AsyncSession = Depends(get_db),
):
    return await crud.collection.create(db, obj_in=collection_data, auth_context=auth_context)
```

**Option 2: Backward Compatible Pattern**:
```python
@router.post("/collections/")
async def create_collection(
    collection_data: CollectionCreate,
    current_user: User = Depends(get_user),  # Fails for API keys
    db: AsyncSession = Depends(get_db),
):
    # Convert user to auth context internally
    auth_context = AuthContext(
        organization_id=current_user.organization_id,
        user=current_user,
        auth_method="auth0"
    )
    return await crud.collection.create(db, obj_in=collection_data, auth_context=auth_context)
```

### Key Benefits
1. **Unified Context**: Single pattern for all auth methods
2. **Flexible Tracking**: UserMixin works when context available, nullable when not
3. **Organization Scoping**: Always enforced regardless of auth method
4. **API Key Resilience**: Works even when original user is deleted
5. **Clear Separation**: Auth layer provides context, CRUD layer consumes it
6. **Future Proof**: Easy to add service accounts, multi-org, etc.

### Implementation Strategy
1. Make `UserMixin` fields nullable
2. Update `CRUDBaseOrganization` to accept `AuthContext`
3. Gradually migrate endpoints from `get_user` to `get_auth_context`
4. Remove user-level ownership permission checks
5. Keep backward compatibility during transition

---

## Phase 1: Auth0 Management API Infrastructure

### 1.1 Backend: Auth0 Management API Client
**New File**: `backend/airweave/integrations/auth0_management.py`

```python
from auth0.management import Auth0

class Auth0ManagementClient:
    def __init__(self):
        self.client = Auth0(domain, client_id, client_secret)

    async def get_user_organizations(self, auth0_user_id: str) -> List[Dict]:
        """GET /api/v2/users/{id}/organizations"""

    async def create_organization(self, name: str, display_name: str) -> Dict:
        """POST /api/v2/organizations"""

    async def add_user_to_organization(self, org_id: str, user_id: str) -> None:
        """POST /api/v2/organizations/{id}/members"""

    async def invite_user_to_organization(self, org_id: str, email: str) -> Dict:
        """POST /api/v2/organizations/{id}/invitations"""

    async def get_pending_invitations(self, org_id: str) -> List[Dict]:
        """GET /api/v2/organizations/{id}/invitations"""
```

### 1.2 Backend: Enhanced User Model
**Update**: `backend/airweave/models/user.py`

```python
class User(OrganizationBase):  # Keep extending OrganizationBase for primary org
    # Add new fields:
    auth0_organizations: Mapped[List[str]] = mapped_column(JSON, default=list)  # Auth0 org IDs
    primary_organization_id: Mapped[UUID] = mapped_column(UUID, ForeignKey("organization.id"))

    # Keep existing organization relationship for backward compatibility
    organization: Mapped["Organization"] = relationship("Organization", foreign_keys=[organization_id])
    primary_organization: Mapped["Organization"] = relationship("Organization", foreign_keys=[primary_organization_id])
```

**New Model**: `backend/airweave/models/user_organization.py`
```python
class UserOrganization(Base):
    """Many-to-many relationship with roles"""
    __tablename__ = "user_organization"

    user_id: Mapped[UUID] = mapped_column(ForeignKey("user.id"))
    organization_id: Mapped[UUID] = mapped_column(ForeignKey("organization.id"))
    auth0_org_id: Mapped[str] = mapped_column(String)  # Auth0 organization ID
    role: Mapped[str] = mapped_column(String, default="member")  # owner, admin, member
    is_primary: Mapped[bool] = mapped_column(Boolean, default=False)

    user: Mapped["User"] = relationship("User")
    organization: Mapped["Organization"] = relationship("Organization")
```

### 1.3 Backend: Organization Sync Service
**New File**: `backend/airweave/core/organization_sync_service.py`

```python
class OrganizationSyncService:
    def __init__(self, auth0_client: Auth0ManagementClient):
        self.auth0_client = auth0_client

    async def sync_user_organizations(self, db: AsyncSession, user: User) -> User:
        """Sync user's Auth0 organizations with local DB"""
        auth0_orgs = await self.auth0_client.get_user_organizations(user.auth0_id)

        for auth0_org in auth0_orgs:
            # Create or update local organization
            local_org = await self._ensure_local_organization(db, auth0_org)
            # Create or update user-organization relationship
            await self._ensure_user_organization_relationship(db, user, local_org, auth0_org)

        return user

    async def handle_new_user_signup(self, db: AsyncSession, user_data: Dict) -> User:
        """Handle new user signup - check for invites or create new org"""
        auth0_orgs = await self.auth0_client.get_user_organizations(user_data["auth0_id"])

        if auth0_orgs:
            # User was invited - sync organizations
            user = await self._create_user_with_existing_orgs(db, user_data, auth0_orgs)
        else:
            # New user - create personal organization
            user = await self._create_user_with_new_org(db, user_data)

        return user
```

---

## Detailed User Flow Scenarios & Module Impact

### Scenario 1: Self-Serve Signup (No Org Context)

**Flow Overview**:
1. User completes signup via Auth0
2. Callback to backend after login
3. Backend checks: Does user have org membership in Auth0?
4. No → Backend creates new org via Auth0 API, assigns user as owner
5. Mirrors org and user-org in backend DB
6. Sets current org context in frontend

**Modules Touched**:

**Frontend**:
- `frontend/src/pages/Callback.tsx`
  - Calls `/users/create_or_update` endpoint
  - Triggers organization sync process
  - Redirects to dashboard with org context

- `frontend/src/lib/auth-context.tsx` / `frontend/src/stores/auth-store.ts`
  - Stores user authentication state
  - Triggers organization fetch after auth

- `frontend/src/stores/organization-store.ts`
  - Receives and stores new organization data
  - Sets as current organization

**Backend**:
- `backend/airweave/api/v1/endpoints/users.py:create_or_update_user()`
  - Entry point for user sync
  - Delegates to organization sync service

- `backend/airweave/core/organization_sync_service.py:handle_new_user_signup()`
  - Checks Auth0 for existing organizations
  - Creates new organization if none found

- `backend/airweave/integrations/auth0_management.py`
  - `create_organization()` - Creates Auth0 organization
  - `add_user_to_organization()` - Assigns user as owner

- `backend/airweave/crud/crud_organization.py`
  - Creates local organization record
  - Links to Auth0 organization ID

- `backend/airweave/crud/crud_user.py:create()`
  - Enhanced to work with organization sync service
  - Creates UserOrganization relationship

- `backend/airweave/models/user_organization.py`
  - Stores user-org relationship with role='owner'

**Database Tables**:
- `organization` - New organization record
- `user_organization` - User-org relationship with owner role
- `user` - Updated with primary_organization_id

---

### Scenario 2: Signup via Org Invite

**Flow Overview**:
1. Org admin invites user (backend calls Auth0 to create invitation)
2. User receives email, clicks link
3. Auth0 renders signup, pre-fills org context
4. On completion, user is assigned to org by Auth0
5. Callback to backend: backend fetches user's org membership from Auth0, syncs to DB
6. User lands in correct org dashboard

**Modules Touched**:

**Frontend**:
- `frontend/src/pages/organization/OrganizationMembers.tsx`
  - Admin UI for sending invitations
  - Calls invitation API endpoint

- `frontend/src/hooks/use-organization-context.tsx:inviteUser()`
  - Wrapper function for invitation API
  - Updates UI state after invitation sent

- `frontend/src/pages/Callback.tsx`
  - Same as Scenario 1, but user already has org membership
  - Syncs existing Auth0 organization data

**Backend**:
- `backend/airweave/api/v1/endpoints/invitations.py:create_invitation()`
  - Validates admin permissions
  - Creates Auth0 invitation
  - Stores local invitation record

- `backend/airweave/integrations/auth0_management.py:invite_user_to_organization()`
  - Sends Auth0 organization invitation
  - Returns invitation details

- `backend/airweave/core/organization_sync_service.py:sync_user_organizations()`
  - Called during callback
  - Fetches user's Auth0 organizations
  - Creates local UserOrganization relationships

- `backend/airweave/crud/crud_invitation.py`
  - Tracks invitation status locally
  - Updates status when accepted

**Database Tables**:
- `invitation` - Tracks invitation details and status
- `user_organization` - Created when invitation accepted
- `user` - Updated organization relationships

**Auth0**:
- Organization invitation created
- User assigned to organization on signup completion

---

### Scenario 3: Existing User Gets Invited to a New Org

**Flow Overview**:
1. Admin invites user's email via Auth0 API
2. User receives invite, logs in via magic link
3. Auth0 adds org membership to user
4. Callback to backend after login; backend fetches latest org memberships, syncs to DB
5. User sees new org in org switcher

**Modules Touched**:

**Frontend**:
- `frontend/src/components/UserProfileDropdown.tsx`
  - Shows organization switcher with new organization
  - Allows switching between organizations

- `frontend/src/stores/organization-store.ts:addOrganization()`
  - Adds new organization to user's list
  - Updates UI state

- `frontend/src/hooks/use-organization-context.tsx`
  - Fetches updated organization list on login
  - Detects new organization membership

**Backend**:
- `backend/airweave/api/deps.py:get_user()`
  - Enhanced to sync organizations on every request (with caching)
  - Updates user's organization context

- `backend/airweave/core/organization_sync_service.py:sync_user_organizations()`
  - Fetches current Auth0 organizations
  - Creates missing UserOrganization relationships
  - Updates existing relationships

- `backend/airweave/integrations/auth0_management.py:get_user_organizations()`
  - Retrieves user's current Auth0 organization memberships
  - Returns role information

**Database Tables**:
- `user_organization` - New relationship for added organization
- `organization` - May create local org if not exists

**API Headers**:
- `X-Organization-ID` - Used by frontend to specify org context
- Validated against user's organization memberships

---

### Scenario 4: Edge Case — User Signs Up Without Invite, But Email Matches an Org Invite

**Flow Overview**:
1. User signs up via standard signup (no org context)
2. Backend detects: user's email was invited to an org
3. App prompts: "You've been invited to [Org], join now?"
4. If accepted, backend assigns user to org via Auth0 API
5. If declined, user can continue and create a new org

**Modules Touched**:

**Frontend**:
- `frontend/src/pages/Callback.tsx`
  - Enhanced to check for pending invitations
  - Shows invitation prompt modal if found

- `frontend/src/components/PendingInvitationModal.tsx` (New)
  - Modal component for invitation prompt
  - Shows organization details
  - Accept/Decline actions

- `frontend/src/hooks/use-organization-context.tsx:acceptInvitation()`
  - Handles invitation acceptance
  - Updates organization list after acceptance

**Backend**:
- `backend/airweave/core/organization_sync_service.py:handle_new_user_signup()`
  - Enhanced to check for pending invitations by email
  - Returns invitation details if found

- `backend/airweave/api/v1/endpoints/invitations.py:check_pending_by_email()`
  - Checks for pending invitations by email
  - Returns organization details for prompt

- `backend/airweave/api/v1/endpoints/invitations.py:accept_invitation()`
  - Accepts pending invitation
  - Assigns user to Auth0 organization
  - Updates local relationships

- `backend/airweave/integrations/auth0_management.py:add_user_to_organization()`
  - Adds user to Auth0 organization
  - Sets appropriate role

**Database Tables**:
- `invitation` - Checked for pending invitations by email
- `user_organization` - Created if invitation accepted
- `organization` - User either joins existing or creates new

**Decision Flow**:
```
User Signup → Check Pending Invitations by Email
    ↓
Found Invitation?
    ├── Yes → Show Modal → Accept/Decline
    │   ├── Accept → Add to Auth0 Org → Sync to DB → Dashboard
    │   └── Decline → Create New Org → Dashboard
    └── No → Create New Org → Dashboard
```

---

### Cross-Cutting Concerns

**Organization Context Propagation**:
- All API requests include `X-Organization-ID` header
- `backend/airweave/api/deps.py:get_user()` validates org access
- CRUD operations automatically filter by organization

**Caching Strategy**:
- Auth0 API calls minimized through smart caching
- Frontend stores organization data in Zustand with persistence

**Error Handling**:
- Organization access validation at every API boundary using dependency injection
- Frontend shows appropriate error states

**Security Validation Points**:
1. API endpoint: Organization access validation
2. CRUD layer: Automatic organization scoping
3. Database: Foreign key constraints
4. Frontend: UI state validation

This detailed breakdown ensures every module understands its role in the organization transition and provides clear implementation guidance for each user scenario.
