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
- `CRUDBaseSystem`: No scoping (system tables)

### API Layer (Current)
**Organization Enforcement Pattern**:
```python
# Every endpoint uses this pattern:
async def endpoint(
    current_user: User = Depends(deps.get_user),
    db: AsyncSession = Depends(deps.get_db)
):
    # Auto-scoped by current_user.organization_id
    return await crud.entity.get_multi_by_organization(
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

## Frontend State Management & Organization Context

### State Management Architecture with Zustand

**Core State Stores**:

**New File**: `frontend/src/stores/auth-store.ts`
```typescript
import { create } from 'zustand';
import { persist } from 'zustand/middleware';

interface User {
  id: string;
  email: string;
  name: string;
  picture?: string;
  auth0_id: string;
}

interface AuthState {
  // User state
  user: User | null;
  isAuthenticated: boolean;
  isLoading: boolean;
  token: string | null;

  // Actions
  setUser: (user: User | null) => void;
  setToken: (token: string | null) => void;
  setLoading: (loading: boolean) => void;
  logout: () => void;
}

export const useAuthStore = create<AuthState>()(
  persist(
    (set) => ({
      user: null,
      isAuthenticated: false,
      isLoading: true,
      token: null,

      setUser: (user) => set({ user, isAuthenticated: !!user }),
      setToken: (token) => set({ token }),
      setLoading: (isLoading) => set({ isLoading }),
      logout: () => set({ user: null, isAuthenticated: false, token: null }),
    }),
    {
      name: 'auth-storage',
      partialize: (state) => ({ user: state.user, token: state.token }),
    }
  )
);
```

**New File**: `frontend/src/stores/organization-store.ts`
```typescript
import { create } from 'zustand';
import { persist } from 'zustand/middleware';

interface Organization {
  id: string;
  name: string;
  description?: string;
  auth0_org_id?: string;
  role: 'owner' | 'admin' | 'member';
  is_primary: boolean;
}

interface OrganizationState {
  // Organization state
  organizations: Organization[];
  currentOrganization: Organization | null;
  isLoading: boolean;

  // Actions
  setOrganizations: (orgs: Organization[]) => void;
  setCurrentOrganization: (org: Organization) => void;
  addOrganization: (org: Organization) => void;
  removeOrganization: (orgId: string) => void;
  updateOrganization: (orgId: string, updates: Partial<Organization>) => void;
  setLoading: (loading: boolean) => void;
}

export const useOrganizationStore = create<OrganizationState>()(
  persist(
    (set, get) => ({
      organizations: [],
      currentOrganization: null,
      isLoading: false,

      setOrganizations: (organizations) => {
        const currentOrgId = get().currentOrganization?.id;
        const currentOrg = organizations.find(org => org.id === currentOrgId) ||
                          organizations.find(org => org.is_primary) ||
                          organizations[0];

        set({ organizations, currentOrganization: currentOrg });
      },

      setCurrentOrganization: (currentOrganization) => set({ currentOrganization }),

      addOrganization: (org) => set((state) => ({
        organizations: [...state.organizations, org]
      })),

      removeOrganization: (orgId) => set((state) => ({
        organizations: state.organizations.filter(org => org.id !== orgId),
        currentOrganization: state.currentOrganization?.id === orgId ?
          state.organizations.find(org => org.is_primary) || state.organizations[0] :
          state.currentOrganization
      })),

      updateOrganization: (orgId, updates) => set((state) => ({
        organizations: state.organizations.map(org =>
          org.id === orgId ? { ...org, ...updates } : org
        ),
        currentOrganization: state.currentOrganization?.id === orgId ?
          { ...state.currentOrganization, ...updates } : state.currentOrganization
      })),

      setLoading: (isLoading) => set({ isLoading }),
    }),
    {
      name: 'organization-storage',
      partialize: (state) => ({
        organizations: state.organizations,
        currentOrganization: state.currentOrganization
      }),
    }
  )
);
```

### Enhanced API Client with Organization Context

**Update**: `frontend/src/lib/api.ts`

```typescript
import { useAuthStore } from '@/stores/auth-store';
import { useOrganizationStore } from '@/stores/organization-store';

// Enhanced API client with automatic organization context
class APIClient {
  private getAuthHeaders(): Record<string, string> {
    const { token } = useAuthStore.getState();
    const { currentOrganization } = useOrganizationStore.getState();

    const headers: Record<string, string> = {
      'Content-Type': 'application/json',
    };

    if (token) {
      headers['Authorization'] = `Bearer ${token}`;
    }

    if (currentOrganization) {
      headers['X-Organization-ID'] = currentOrganization.id;
    }

    return headers;
  }

  async request<T>(endpoint: string, options: RequestInit = {}): Promise<T> {
    const url = `${API_CONFIG.baseURL}${endpoint}`;
    const headers = { ...this.getAuthHeaders(), ...options.headers };

    const response = await fetch(url, { ...options, headers });

    if (!response.ok) {
      throw new APIError(`HTTP ${response.status}: ${response.statusText}`, response.status);
    }

    return response.json();
  }

  // Organization-specific methods
  async switchOrganization(organizationId: string): Promise<void> {
    const organizations = useOrganizationStore.getState().organizations;
    const org = organizations.find(o => o.id === organizationId);

    if (!org) {
      throw new Error(`Organization ${organizationId} not found in user's organizations`);
    }

    useOrganizationStore.getState().setCurrentOrganization(org);
  }
}

export const apiClient = new APIClient();
```

### Dependency Injection Pattern for Organization Context

**New File**: `frontend/src/hooks/use-organization-context.tsx`

```typescript
import { useEffect } from 'react';
import { useAuthStore } from '@/stores/auth-store';
import { useOrganizationStore } from '@/stores/organization-store';
import { apiClient } from '@/lib/api';

export const useOrganizationContext = () => {
  const { user, isAuthenticated } = useAuthStore();
  const {
    organizations,
    currentOrganization,
    setOrganizations,
    setCurrentOrganization,
    setLoading
  } = useOrganizationStore();

  // Fetch organizations when user is authenticated
  useEffect(() => {
    const fetchOrganizations = async () => {
      if (!isAuthenticated || !user) return;

      try {
        setLoading(true);
        const userOrgs = await apiClient.get<Organization[]>('/users/me/organizations');
        setOrganizations(userOrgs);
      } catch (error) {
        console.error('Failed to fetch organizations:', error);
      } finally {
        setLoading(false);
      }
    };

    fetchOrganizations();
  }, [isAuthenticated, user, setOrganizations, setLoading]);

  // Organization management actions
  const switchOrganization = async (orgId: string) => {
    await apiClient.switchOrganization(orgId);
  };

  const inviteUser = async (email: string, role: string = 'member') => {
    if (!currentOrganization) throw new Error('No organization selected');

    return apiClient.post('/invitations', {
      email,
      organization_id: currentOrganization.id,
      role
    });
  };

  const leaveOrganization = async (orgId: string) => {
    await apiClient.delete(`/organizations/${orgId}/members/me`);
    // Refresh organizations after leaving
    const updatedOrgs = await apiClient.get<Organization[]>('/users/me/organizations');
    setOrganizations(updatedOrgs);
  };

  return {
    organizations,
    currentOrganization,
    switchOrganization,
    inviteUser,
    leaveOrganization,
    isLoading: useOrganizationStore(state => state.isLoading)
  };
};
```

**New File**: `frontend/src/providers/OrganizationProvider.tsx`

```typescript
import React, { createContext, useContext, ReactNode } from 'react';
import { useOrganizationContext } from '@/hooks/use-organization-context';

const OrganizationContext = createContext<ReturnType<typeof useOrganizationContext> | null>(null);

export const OrganizationProvider: React.FC<{ children: ReactNode }> = ({ children }) => {
  const organizationContext = useOrganizationContext();

  return (
    <OrganizationContext.Provider value={organizationContext}>
      {children}
    </OrganizationContext.Provider>
  );
};

export const useOrganization = () => {
  const context = useContext(OrganizationContext);
  if (!context) {
    throw new Error('useOrganization must be used within OrganizationProvider');
  }
  return context;
};
```

### Integration with Auth0Provider

**Update**: `frontend/src/lib/auth0-provider.tsx`

```typescript
export const Auth0ProviderWithNavigation = ({ children }: Auth0ProviderWithNavigationProps) => {
  return (
    <Auth0Provider {...authConfig}>
      <AuthStateSync>
        <OrganizationProvider>
          {children}
        </OrganizationProvider>
      </AuthStateSync>
    </Auth0Provider>
  );
};

// Sync Auth0 state with Zustand stores
const AuthStateSync: React.FC<{ children: ReactNode }> = ({ children }) => {
  const { user, isAuthenticated, isLoading, getAccessTokenSilently } = useAuth0();
  const { setUser, setToken, setLoading } = useAuthStore();

  useEffect(() => {
    setUser(user);
    setLoading(isLoading);
  }, [user, isLoading, setUser, setLoading]);

  useEffect(() => {
    const getToken = async () => {
      if (isAuthenticated) {
        try {
          const token = await getAccessTokenSilently();
          setToken(token);
        } catch (error) {
          console.error('Failed to get token:', error);
        }
      }
    };
    getToken();
  }, [isAuthenticated, getAccessTokenSilently, setToken]);

  return <>{children}</>;
};
```

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

**2. CRUDUserInOrganization**: User-owned resources within organization context
- **Models**: Collection, SourceConnection, WhiteLabel (all extend OrganizationBase + UserMixin)
- **Pattern**: User owns the resource, but within organization scope
- **Access**: User must be creator/modifier AND be in the organization
- **API Pattern**: Public-facing user resources

**3. CRUDOrganization**: Organization-wide resources
- **Two sub-patterns**:
  - With user tracking: APIKey, IntegrationCredential (OrganizationBase + UserMixin)
  - Without user tracking: Entity, Sync, SyncJob (OrganizationBase only)
- **Pattern**: Organization membership required, optional user tracking
- **Access**: Any organization member can access (with role-based restrictions)

**4. CRUDPublic**: System-wide resources
- **Models**: Source, Destination, EntityDefinition, Transformer (Base with nullable organization_id)
- **Pattern**: Available to all authenticated users, optionally organization-specific
- **Access**: No organization filtering (or filtered by nullable organization_id)

### Implementation Strategy

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

**New File**: `backend/airweave/crud/_base_user_in_organization.py`
```python
class CRUDUserInOrganization(Generic[ModelType, CreateSchemaType, UpdateSchemaType]):
    """CRUD for user-owned resources within organization context."""

    def __init__(self, model: Type[ModelType]):
        self.model = model

    async def get(self, db: AsyncSession, id: UUID, current_user: User) -> Optional[ModelType]:
        """Get user-owned resource in current user's organization."""
        query = select(self.model).where(
            self.model.id == id,
            self.model.organization_id == current_user.current_organization_id,
            # User must be creator or modifier
            (self.model.created_by_email == current_user.email) |
            (self.model.modified_by_email == current_user.email)
        )
        result = await db.execute(query)
        return result.unique().scalar_one_or_none()

    async def get_multi_for_user(
        self,
        db: AsyncSession,
        current_user: User,
        *, skip: int = 0, limit: int = 100
    ) -> list[ModelType]:
        """Get all user-owned resources in current organization."""
        query = select(self.model).where(
            self.model.organization_id == current_user.current_organization_id,
            (self.model.created_by_email == current_user.email) |
            (self.model.modified_by_email == current_user.email)
        ).offset(skip).limit(limit)

        result = await db.execute(query)
        return list(result.unique().scalars().all())

    async def create(
        self,
        db: AsyncSession,
        *,
        obj_in: CreateSchemaType,
        current_user: User
    ) -> ModelType:
        """Create user-owned resource in current organization."""
        if not isinstance(obj_in, dict):
            obj_in = obj_in.model_dump(exclude_unset=True)

        obj_in['organization_id'] = current_user.current_organization_id
        obj_in['created_by_email'] = current_user.email
        obj_in['modified_by_email'] = current_user.email

        db_obj = self.model(**obj_in)
        db.add(db_obj)
        await db.commit()
        await db.refresh(db_obj)
        return db_obj
```

**New File**: `backend/airweave/crud/_base_organization.py` (Enhanced)
```python
class CRUDOrganization(Generic[ModelType, CreateSchemaType, UpdateSchemaType]):
    """CRUD for organization-wide resources."""

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
        """Get organization resource - user must be org member."""
        effective_org_id = organization_id or current_user.current_organization_id

        # Validate user has org access
        await self._validate_organization_access(db, current_user, effective_org_id)

        query = select(self.model).where(
            self.model.id == id,
            self.model.organization_id == effective_org_id
        )
        result = await db.execute(query)
        return result.unique().scalar_one_or_none()

    async def get_multi_for_organization(
        self,
        db: AsyncSession,
        current_user: User,
        organization_id: Optional[UUID] = None,
        *, skip: int = 0, limit: int = 100
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

**Step 1: Update Existing Classes**
```python
# Update Collection (UserInOrganization pattern)
class CRUDCollection(CRUDUserInOrganization[Collection, CollectionCreate, CollectionUpdate]):
    def __init__(self):
        super().__init__(Collection)

# Update Entity (Organization pattern, no user tracking)
class CRUDEntity(CRUDOrganization[Entity, EntityCreate, EntityUpdate]):
    def __init__(self):
        super().__init__(Entity, track_user=False)

# Update APIKey (Organization pattern, with user tracking)
class CRUDAPIKey(CRUDOrganization[APIKey, APIKeyCreate, APIKeyUpdate]):
    def __init__(self):
        super().__init__(APIKey, track_user=True)

# Update Source (Public pattern)
class CRUDSource(CRUDPublic[Source, SourceCreate, SourceUpdate]):
    def __init__(self):
        super().__init__(Source)
```

**Step 2: API Layer Updates**
```python
# UserInOrganization pattern endpoints
@router.get("/collections/", response_model=List[schemas.Collection])
async def list_collections(
    current_user: User = Depends(deps.get_user),
    db: AsyncSession = Depends(deps.get_db),
):
    """List user's collections in current organization."""
    return await crud.collection.get_multi_for_user(db, current_user)

# Organization pattern endpoints
@router.get("/entities/", response_model=List[schemas.Entity])
async def list_entities(
    current_user: User = Depends(deps.get_user),
    db: AsyncSession = Depends(deps.get_db),
):
    """List all entities in current organization."""
    return await crud.entity.get_multi_for_organization(db, current_user)

# Public pattern endpoints
@router.get("/sources/", response_model=List[schemas.Source])
async def list_sources(
    current_user: User = Depends(deps.get_user),
    db: AsyncSession = Depends(deps.get_db),
):
    """List all available sources."""
    return await crud.source.get_multi(db, organization_id=current_user.current_organization_id)
```

### Model Classification Summary

**CRUDUser**:
- User (self-management only)
- Future: UserPreferences

**CRUDUserInOrganization** (OrganizationBase + UserMixin):
- Collection
- SourceConnection
- WhiteLabel

**CRUDOrganization**:
- *With user tracking*: APIKey, IntegrationCredential, Chat
- *Without user tracking*: Entity, Sync, SyncJob, DAG, Connection

**CRUDPublic** (Base, optional nullable organization_id):
- Source, Destination
- EntityDefinition
- Transformer, EmbeddingModel

This approach avoids god classes while providing clear, purpose-built CRUD patterns that match the actual usage in your codebase.

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

## Frontend Organization Management UI

### Enhanced UserProfileDropdown with Organization Management

**Update**: `frontend/src/components/UserProfileDropdown.tsx`

```typescript
import { useState, useEffect } from 'react';
import { useAuth } from '@/lib/auth-context';
import { useOrganization } from '@/providers/OrganizationProvider';
import { Link } from 'react-router-dom';
import {
  DropdownMenu, DropdownMenuContent, DropdownMenuItem,
  DropdownMenuSeparator, DropdownMenuTrigger, DropdownMenuSub,
  DropdownMenuSubContent, DropdownMenuSubTrigger
} from '@/components/ui/dropdown-menu';
import { Avatar, AvatarFallback, AvatarImage } from '@/components/ui/avatar';
import { Badge } from '@/components/ui/badge';
import {
  ExternalLink, MoreVertical, Building2, Settings,
  UserPlus, Crown, Shield, Users
} from 'lucide-react';

export function UserProfileDropdown() {
  const { user, logout } = useAuth();
  const {
    organizations,
    currentOrganization,
    switchOrganization,
    isLoading
  } = useOrganization();

  const [firstName, setFirstName] = useState<string>('');
  const [lastName, setLastName] = useState<string>('');

  useEffect(() => {
    if (user?.name) {
      const nameParts = user.name.split(' ');
      setFirstName(nameParts[0] || '');
      setLastName(nameParts.slice(1).join(' ') || '');
    }
  }, [user]);

  const handleLogout = () => {
    apiClient.clearToken();
    logout();
  };

  const getRoleIcon = (role: string) => {
    switch (role) {
      case 'owner': return <Crown className="h-3 w-3" />;
      case 'admin': return <Shield className="h-3 w-3" />;
      default: return <Users className="h-3 w-3" />;
    }
  };

  const getRoleBadgeVariant = (role: string) => {
    switch (role) {
      case 'owner': return 'default';
      case 'admin': return 'secondary';
      default: return 'outline';
    }
  };

  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <button className="flex items-center justify-between px-1 py-2 text-sm font-medium rounded-md text-muted-foreground hover:bg-accent hover:text-accent-foreground transition-all duration-200 ease-in-out w-full">
          <div className="flex items-center">
            <Avatar className="h-8 w-8 mr-3">
              <AvatarImage src={user?.picture} alt={user?.name || "User"} />
              <AvatarFallback className="bg-primary/0 border text-primary text-xs">
                {firstName
                  ? firstName[0]
                  : user?.email?.substring(0, 1).toUpperCase() || 'U'}
              </AvatarFallback>
            </Avatar>
            <div className="flex flex-col items-start">
              <span>{user?.name || "User"}</span>
              {currentOrganization && (
                <span className="text-xs text-muted-foreground truncate max-w-32">
                  {currentOrganization.name}
                </span>
              )}
            </div>
          </div>
          <MoreVertical className="h-4 w-4 opacity-70" />
        </button>
      </DropdownMenuTrigger>

      <DropdownMenuContent className="ml-2 w-[280px] p-0 rounded-md" align="end" side="top" sideOffset={4}>
        {/* User Info Section */}
        <div className="py-2 px-3 border-b border-border/10">
          <p className="text-sm text-muted-foreground truncate">
            {user?.email}
          </p>
          {currentOrganization && (
            <div className="flex items-center gap-2 mt-1">
              <Building2 className="h-3 w-3" />
              <span className="text-xs font-medium">{currentOrganization.name}</span>
              <Badge
                variant={getRoleBadgeVariant(currentOrganization.role)}
                className="text-xs h-4 px-1"
              >
                {getRoleIcon(currentOrganization.role)}
                {currentOrganization.role}
              </Badge>
            </div>
          )}
        </div>

        {/* Organization Switcher */}
        {organizations.length > 1 && (
          <>
            <DropdownMenuSub>
              <DropdownMenuSubTrigger className="px-3 py-1.5 text-sm">
                <Building2 className="h-4 w-4 mr-2" />
                Switch Organization
              </DropdownMenuSubTrigger>
              <DropdownMenuSubContent className="w-64">
                {organizations.map((org) => (
                  <DropdownMenuItem
                    key={org.id}
                    onSelect={() => switchOrganization(org.id)}
                    disabled={org.id === currentOrganization?.id}
                    className="flex items-center justify-between px-3 py-2"
                  >
                    <div className="flex items-center">
                      <Building2 className="h-4 w-4 mr-2" />
                      <div>
                        <div className="font-medium">{org.name}</div>
                        {org.is_primary && (
                          <div className="text-xs text-muted-foreground">Primary</div>
                        )}
                      </div>
                    </div>
                    <div className="flex items-center gap-1">
                      {org.id === currentOrganization?.id && (
                        <div className="w-2 h-2 bg-green-500 rounded-full" />
                      )}
                      <Badge
                        variant={getRoleBadgeVariant(org.role)}
                        className="text-xs h-4 px-1"
                      >
                        {getRoleIcon(org.role)}
                      </Badge>
                    </div>
                  </DropdownMenuItem>
                ))}
              </DropdownMenuSubContent>
            </DropdownMenuSub>
            <DropdownMenuSeparator className="opacity-10" />
          </>
        )}

        {/* Organization Management */}
        {currentOrganization && ['owner', 'admin'].includes(currentOrganization.role) && (
          <>
            <div className="py-1">
              <DropdownMenuItem asChild>
                <Link to="/organization/members" className="flex items-center px-3 py-1.5 text-sm">
                  <UserPlus className="h-4 w-4 mr-2" />
                  Invite Members
                </Link>
              </DropdownMenuItem>

              <DropdownMenuItem asChild>
                <Link to="/organization/settings" className="flex items-center px-3 py-1.5 text-sm">
                  <Settings className="h-4 w-4 mr-2" />
                  Organization Settings
                </Link>
              </DropdownMenuItem>
            </div>
            <DropdownMenuSeparator className="opacity-10" />
          </>
        )}

        {/* External Links */}
        <div className="py-1">
          <DropdownMenuItem asChild>
            <a href="https://airweave.ai" target="_blank" rel="noopener noreferrer" className="flex items-center justify-between px-3 py-1.5 text-sm">
              Blog <ExternalLink className="h-3.5 w-3.5 opacity-70" />
            </a>
          </DropdownMenuItem>

          <DropdownMenuItem asChild>
            <a href="https://docs.airweave.ai" target="_blank" rel="noopener noreferrer" className="flex items-center justify-between px-3 py-1.5 text-sm">
              Documentation <ExternalLink className="h-3.5 w-3.5 opacity-70" />
            </a>
          </DropdownMenuItem>

          <DropdownMenuItem asChild>
            <a href="https://discord.gg/484HY9Ehxt" target="_blank" rel="noopener noreferrer" className="flex items-center justify-between px-3 py-1.5 text-sm">
              Join Discord community <ExternalLink className="h-3.5 w-3.5 opacity-70" />
            </a>
          </DropdownMenuItem>
        </div>

        <DropdownMenuSeparator className="opacity-10" />

        {/* Account Settings */}
        <div className="py-1">
          <DropdownMenuItem asChild>
            <Link to="/settings/account" className="px-3 py-1.5 text-sm">
              Account Settings
            </Link>
          </DropdownMenuItem>
        </div>

        <DropdownMenuSeparator className="opacity-10" />

        {/* Logout */}
        <div className="py-1">
          <DropdownMenuItem onSelect={handleLogout} className="px-3 py-1.5 text-sm text-muted-foreground">
            Sign out
          </DropdownMenuItem>
        </div>
      </DropdownMenuContent>
    </DropdownMenu>
  );
}
```

### Organization Settings Pages

**New File**: `frontend/src/pages/organization/OrganizationSettings.tsx`

```typescript
import { useState, useEffect } from 'react';
import { useOrganization } from '@/providers/OrganizationProvider';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Textarea } from '@/components/ui/textarea';
import { Separator } from '@/components/ui/separator';
import { Badge } from '@/components/ui/badge';
import { Building2, Save, Trash2 } from 'lucide-react';
import { apiClient } from '@/lib/api';

export const OrganizationSettings = () => {
  const { currentOrganization, updateOrganization } = useOrganization();
  const [name, setName] = useState('');
  const [description, setDescription] = useState('');
  const [isLoading, setIsLoading] = useState(false);

  useEffect(() => {
    if (currentOrganization) {
      setName(currentOrganization.name);
      setDescription(currentOrganization.description || '');
    }
  }, [currentOrganization]);

  const handleSave = async () => {
    if (!currentOrganization) return;

    try {
      setIsLoading(true);
      await apiClient.put(`/organizations/${currentOrganization.id}`, {
        name,
        description
      });

      updateOrganization(currentOrganization.id, { name, description });
    } catch (error) {
      console.error('Failed to update organization:', error);
    } finally {
      setIsLoading(false);
    }
  };

  if (!currentOrganization) {
    return <div>No organization selected</div>;
  }

  return (
    <div className="container mx-auto py-6 max-w-4xl">
      <div className="flex items-center gap-2 mb-6">
        <Building2 className="h-6 w-6" />
        <h1 className="text-2xl font-bold">Organization Settings</h1>
        <Badge variant="outline">
          {currentOrganization.role}
        </Badge>
      </div>

      <div className="grid gap-6">
        {/* Basic Information */}
        <Card>
          <CardHeader>
            <CardTitle>Basic Information</CardTitle>
            <CardDescription>
              Update your organization's basic information.
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div>
              <Label htmlFor="name">Organization Name</Label>
              <Input
                id="name"
                value={name}
                onChange={(e) => setName(e.target.value)}
                placeholder="Enter organization name"
              />
            </div>

            <div>
              <Label htmlFor="description">Description</Label>
              <Textarea
                id="description"
                value={description}
                onChange={(e) => setDescription(e.target.value)}
                placeholder="Enter organization description"
                rows={3}
              />
            </div>

            <Button
              onClick={handleSave}
              disabled={isLoading}
              className="flex items-center gap-2"
            >
              <Save className="h-4 w-4" />
              {isLoading ? 'Saving...' : 'Save Changes'}
            </Button>
          </CardContent>
        </Card>

        {/* Organization ID */}
        <Card>
          <CardHeader>
            <CardTitle>Organization ID</CardTitle>
            <CardDescription>
              Your organization's unique identifier.
            </CardDescription>
          </CardHeader>
          <CardContent>
            <div className="flex items-center gap-2">
              <Input
                value={currentOrganization.id}
                readOnly
                className="font-mono text-sm"
              />
              <Button
                variant="outline"
                onClick={() => navigator.clipboard.writeText(currentOrganization.id)}
              >
                Copy
              </Button>
            </div>
          </CardContent>
        </Card>

        {/* Danger Zone */}
        {currentOrganization.role === 'owner' && (
          <Card className="border-red-200">
            <CardHeader>
              <CardTitle className="text-red-600">Danger Zone</CardTitle>
              <CardDescription>
                These actions cannot be undone.
              </CardDescription>
            </CardHeader>
            <CardContent>
              <Button variant="destructive" className="flex items-center gap-2">
                <Trash2 className="h-4 w-4" />
                Delete Organization
              </Button>
            </CardContent>
          </Card>
        )}
      </div>
    </div>
  );
};
```

**New File**: `frontend/src/pages/organization/OrganizationMembers.tsx`

```typescript
import { useState, useEffect } from 'react';
import { useOrganization } from '@/providers/OrganizationProvider';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Badge } from '@/components/ui/badge';
import { Avatar, AvatarFallback, AvatarImage } from '@/components/ui/avatar';
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue
} from '@/components/ui/select';
import {
  Table, TableBody, TableCell, TableHead, TableHeader, TableRow
} from '@/components/ui/table';
import { UserPlus, Mail, MoreHorizontal, Crown, Shield, Users } from 'lucide-react';
import { apiClient } from '@/lib/api';

interface Member {
  id: string;
  email: string;
  name: string;
  role: string;
  status: 'active' | 'pending';
  avatar?: string;
}

interface PendingInvitation {
  id: string;
  email: string;
  role: string;
  invited_at: string;
  status: 'pending' | 'expired';
}

export const OrganizationMembers = () => {
  const { currentOrganization, inviteUser } = useOrganization();
  const [members, setMembers] = useState<Member[]>([]);
  const [pendingInvitations, setPendingInvitations] = useState<PendingInvitation[]>([]);
  const [inviteEmail, setInviteEmail] = useState('');
  const [inviteRole, setInviteRole] = useState('member');
  const [isLoading, setIsLoading] = useState(false);

  useEffect(() => {
    fetchMembers();
    fetchPendingInvitations();
  }, [currentOrganization]);

  const fetchMembers = async () => {
    if (!currentOrganization) return;

    try {
      const response = await apiClient.get<Member[]>(`/organizations/${currentOrganization.id}/members`);
      setMembers(response);
    } catch (error) {
      console.error('Failed to fetch members:', error);
    }
  };

  const fetchPendingInvitations = async () => {
    if (!currentOrganization) return;

    try {
      const response = await apiClient.get<PendingInvitation[]>('/invitations/pending');
      setPendingInvitations(response);
    } catch (error) {
      console.error('Failed to fetch pending invitations:', error);
    }
  };

  const handleInvite = async () => {
    if (!inviteEmail) return;

    try {
      setIsLoading(true);
      await inviteUser(inviteEmail, inviteRole);
      setInviteEmail('');
      setInviteRole('member');
      await fetchPendingInvitations();
    } catch (error) {
      console.error('Failed to send invitation:', error);
    } finally {
      setIsLoading(false);
    }
  };

  const getRoleIcon = (role: string) => {
    switch (role) {
      case 'owner': return <Crown className="h-4 w-4" />;
      case 'admin': return <Shield className="h-4 w-4" />;
      default: return <Users className="h-4 w-4" />;
    }
  };

  const getRoleBadgeVariant = (role: string) => {
    switch (role) {
      case 'owner': return 'default';
      case 'admin': return 'secondary';
      default: return 'outline';
    }
  };

  if (!currentOrganization) {
    return <div>No organization selected</div>;
  }

  return (
    <div className="container mx-auto py-6 max-w-6xl">
      <div className="flex items-center gap-2 mb-6">
        <Users className="h-6 w-6" />
        <h1 className="text-2xl font-bold">Organization Members</h1>
      </div>

      <div className="grid gap-6">
        {/* Invite Members */}
        {['owner', 'admin'].includes(currentOrganization.role) && (
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <UserPlus className="h-5 w-5" />
                Invite New Member
              </CardTitle>
              <CardDescription>
                Send an invitation to add a new member to your organization.
              </CardDescription>
            </CardHeader>
            <CardContent>
              <div className="flex gap-4">
                <div className="flex-1">
                  <Label htmlFor="email">Email Address</Label>
                  <Input
                    id="email"
                    type="email"
                    value={inviteEmail}
                    onChange={(e) => setInviteEmail(e.target.value)}
                    placeholder="Enter email address"
                  />
                </div>
                <div>
                  <Label htmlFor="role">Role</Label>
                  <Select value={inviteRole} onValueChange={setInviteRole}>
                    <SelectTrigger className="w-32">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="member">Member</SelectItem>
                      <SelectItem value="admin">Admin</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
                <div className="flex items-end">
                  <Button
                    onClick={handleInvite}
                    disabled={!inviteEmail || isLoading}
                    className="flex items-center gap-2"
                  >
                    <Mail className="h-4 w-4" />
                    {isLoading ? 'Sending...' : 'Send Invite'}
                  </Button>
                </div>
              </div>
            </CardContent>
          </Card>
        )}

        {/* Current Members */}
        <Card>
          <CardHeader>
            <CardTitle>Current Members ({members.length})</CardTitle>
            <CardDescription>
              Manage your organization's members and their roles.
            </CardDescription>
          </CardHeader>
          <CardContent>
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Member</TableHead>
                  <TableHead>Role</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead className="w-12"></TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {members.map((member) => (
                  <TableRow key={member.id}>
                    <TableCell>
                      <div className="flex items-center gap-3">
                        <Avatar className="h-8 w-8">
                          <AvatarImage src={member.avatar} />
                          <AvatarFallback>
                            {member.name?.substring(0, 2).toUpperCase() ||
                             member.email.substring(0, 2).toUpperCase()}
                          </AvatarFallback>
                        </Avatar>
                        <div>
                          <div className="font-medium">{member.name || member.email}</div>
                          {member.name && (
                            <div className="text-sm text-muted-foreground">{member.email}</div>
                          )}
                        </div>
                      </div>
                    </TableCell>
                    <TableCell>
                      <Badge
                        variant={getRoleBadgeVariant(member.role)}
                        className="flex items-center gap-1 w-fit"
                      >
                        {getRoleIcon(member.role)}
                        {member.role}
                      </Badge>
                    </TableCell>
                    <TableCell>
                      <Badge variant={member.status === 'active' ? 'default' : 'secondary'}>
                        {member.status}
                      </Badge>
                    </TableCell>
                    <TableCell>
                      <Button variant="ghost" size="sm">
                        <MoreHorizontal className="h-4 w-4" />
                      </Button>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </CardContent>
        </Card>

        {/* Pending Invitations */}
        {pendingInvitations.length > 0 && (
          <Card>
            <CardHeader>
              <CardTitle>Pending Invitations ({pendingInvitations.length})</CardTitle>
              <CardDescription>
                Invitations that have been sent but not yet accepted.
              </CardDescription>
            </CardHeader>
            <CardContent>
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Email</TableHead>
                    <TableHead>Role</TableHead>
                    <TableHead>Invited</TableHead>
                    <TableHead>Status</TableHead>
                    <TableHead className="w-12"></TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {pendingInvitations.map((invitation) => (
                    <TableRow key={invitation.id}>
                      <TableCell>{invitation.email}</TableCell>
                      <TableCell>
                        <Badge
                          variant={getRoleBadgeVariant(invitation.role)}
                          className="flex items-center gap-1 w-fit"
                        >
                          {getRoleIcon(invitation.role)}
                          {invitation.role}
                        </Badge>
                      </TableCell>
                      <TableCell>
                        {new Date(invitation.invited_at).toLocaleDateString()}
                      </TableCell>
                      <TableCell>
                        <Badge variant={invitation.status === 'pending' ? 'default' : 'destructive'}>
                          {invitation.status}
                        </Badge>
                      </TableCell>
                      <TableCell>
                        <Button variant="ghost" size="sm">
                          <MoreHorizontal className="h-4 w-4" />
                        </Button>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </CardContent>
          </Card>
        )}
      </div>
    </div>
  );
};
```

---

## Conclusion

This comprehensive design leverages Airweave's existing organization infrastructure while adding Auth0 Organizations integration. The phased approach ensures minimal disruption to existing users while providing a clear path to full multi-organization support.

**Key Success Factors**:
1. **Leverage Existing Patterns**: Build on current `OrganizationBase` and CRUD patterns
2. **Backward Compatibility**: Maintain existing API contracts during transition
3. **Incremental Rollout**: Feature flags enable safe, gradual deployment
4. **Comprehensive Testing**: Cover all user flows and edge cases
5. **Security First**: Organization access validation at every layer

The implementation provides a robust foundation for Airweave's evolution into a multi-tenant, organization-aware platform while preserving the simplicity that makes it powerful.

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
- Organization memberships cached for 5 minutes
- Auth0 API calls minimized through smart caching
- Frontend stores organization data in Zustand with persistence

**Error Handling**:
- Auth0 API failures gracefully degrade to cached data
- Organization access validation at every API boundary
- Frontend shows appropriate error states

**Security Validation Points**:
1. API endpoint: Organization access validation
2. CRUD layer: Automatic organization scoping
3. Database: Foreign key constraints
4. Frontend: UI state validation

This detailed breakdown ensures every module understands its role in the organization transition and provides clear implementation guidance for each user scenario.
