import { create } from 'zustand';
import { persist } from 'zustand/middleware';
import { apiClient } from '@/lib/api';

interface Organization {
  id: string;
  name: string;
  description?: string;
  auth0_org_id?: string;
  role: 'owner' | 'admin' | 'member';
  is_primary: boolean;
  created_at?: string;
  modified_at?: string;
}

interface CreateOrganizationRequest {
  name: string;
  description?: string;
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
  createOrganization: (orgData: CreateOrganizationRequest) => Promise<Organization>;
  fetchUserOrganizations: () => Promise<void>;
  switchOrganization: (orgId: string) => void;
  setPrimaryOrganization: (orgId: string) => Promise<boolean>;
  initializeOrganizations: () => Promise<Organization[]>;

  // Member management actions
  inviteUserToOrganization: (orgId: string, email: string, role: string) => Promise<boolean>;
  removeUserFromOrganization: (orgId: string, userId: string) => Promise<boolean>;
  leaveOrganization: (orgId: string) => Promise<boolean>;
}

// Helper function to select the best organization
const selectBestOrganization = (
  organizations: Organization[],
  currentOrgId?: string | null
): Organization | null => {
  if (organizations.length === 0) return null;

  // Priority:
  // 1. Current organization (if it still exists and is valid)
  // 2. Primary organization
  // 3. First organization

  // Check if current org is still valid
  if (currentOrgId) {
    const currentOrg = organizations.find(org => org.id === currentOrgId);
    if (currentOrg) {
      return currentOrg;
    }
  }

  // Find primary organization
  const primaryOrg = organizations.find(org => org.is_primary);
  if (primaryOrg) {
    return primaryOrg;
  }

  // Fallback to first organization
  return organizations[0];
};

export const useOrganizationStore = create<OrganizationState>()(
  persist(
    (set, get) => ({
      organizations: [],
      currentOrganization: null,
      isLoading: false,

      setOrganizations: (organizations) => {
        const currentOrgId = get().currentOrganization?.id;
        const currentOrg = selectBestOrganization(organizations, currentOrgId);

        set({ organizations, currentOrganization: currentOrg });
      },

      setCurrentOrganization: (currentOrganization) => set({ currentOrganization }),

      addOrganization: (org) => set((state) => ({
        organizations: [...state.organizations, org]
      })),

      removeOrganization: (orgId) => set((state) => {
        const newOrganizations = state.organizations.filter(org => org.id !== orgId);
        const newCurrentOrg = state.currentOrganization?.id === orgId
          ? selectBestOrganization(newOrganizations)
          : state.currentOrganization;

        return {
          organizations: newOrganizations,
          currentOrganization: newCurrentOrg
        };
      }),

      updateOrganization: (orgId, updates) => set((state) => ({
        organizations: state.organizations.map(org =>
          org.id === orgId ? { ...org, ...updates } : org
        ),
        currentOrganization: state.currentOrganization?.id === orgId ?
          { ...state.currentOrganization, ...updates } : state.currentOrganization
      })),

      setLoading: (isLoading) => set({ isLoading }),

      switchOrganization: (orgId) => {
        const { organizations } = get();
        const org = organizations.find(o => o.id === orgId);
        if (org) {
          set({ currentOrganization: org });
          console.log(`🔄 [OrganizationStore] Switched to organization: ${org.name} (${org.id})`);
        }
      },

      setPrimaryOrganization: async (orgId: string): Promise<boolean> => {
        try {
          set({ isLoading: true });

          const response = await apiClient.post(`/organizations/${orgId}/set-primary`);

          if (!response.ok) {
            throw new Error(`Failed to set primary organization: ${response.status}`);
          }

          const updatedOrg = await response.json();

          // Update all organizations - clear is_primary from others, set it for the target
          set((state) => ({
            organizations: state.organizations.map(org => ({
              ...org,
              is_primary: org.id === orgId
            })),
            currentOrganization: state.currentOrganization?.id === orgId ?
              { ...state.currentOrganization, is_primary: true } :
              state.currentOrganization,
            isLoading: false
          }));

          return true;
        } catch (error) {
          console.error('Failed to set primary organization:', error);
          set({ isLoading: false });
          return false;
        }
      },

      initializeOrganizations: async (): Promise<Organization[]> => {
        try {
          set({ isLoading: true });

          // Get organizations directly from the new endpoint
          const response = await apiClient.get('/users/me/organizations');

          if (!response.ok) {
            throw new Error(`Failed to fetch organizations: ${response.status}`);
          }

          const organizations: Organization[] = await response.json();

          // Respect persisted organization selection if available, otherwise prefer primary organization
          const currentOrgId = get().currentOrganization?.id;
          const currentOrg = selectBestOrganization(organizations, currentOrgId);

          set({
            organizations,
            currentOrganization: currentOrg,
            isLoading: false
          });

          console.log('Organizations initialized:', {
            total: organizations.length,
            selected: currentOrg?.name,
            isPrimary: currentOrg?.is_primary,
            wasFromPersistence: !!currentOrgId && currentOrgId === currentOrg?.id
          });

          return organizations;
        } catch (error) {
          console.error('Failed to initialize organizations:', error);
          set({ isLoading: false });
          throw error;
        }
      },

      fetchUserOrganizations: async () => {
        try {
          set({ isLoading: true });

          const response = await apiClient.get('/users/me/organizations');

          if (!response.ok) {
            throw new Error(`Failed to fetch organizations: ${response.status}`);
          }

          const organizations: Organization[] = await response.json();

          // For regular fetches, preserve current selection if valid
          const currentOrgId = get().currentOrganization?.id;
          const currentOrg = selectBestOrganization(organizations, currentOrgId);

          set({
            organizations,
            currentOrganization: currentOrg,
            isLoading: false
          });
        } catch (error) {
          console.error('Failed to fetch user organizations:', error);
          set({ isLoading: false });
          throw error;
        }
      },

      createOrganization: async (orgData: CreateOrganizationRequest) => {
        try {
          set({ isLoading: true });

          const response = await apiClient.post('/organizations', orgData);

          if (!response.ok) {
            const errorData = await response.json().catch(() => ({}));
            throw new Error(errorData.detail || `Failed to create organization: ${response.status}`);
          }

          const newOrganization = await response.json();

          // Add the new organization to the store
          set((state) => ({
            organizations: [...state.organizations, newOrganization],
            currentOrganization: newOrganization, // Set as current organization
            isLoading: false,
          }));

          return newOrganization;
        } catch (error) {
          set({ isLoading: false });
          throw error;
        }
      },

      // Member management actions
      inviteUserToOrganization: async (orgId: string, email: string, role: string): Promise<boolean> => {
        try {
          set({ isLoading: true });

          const response = await apiClient.post(`/organizations/${orgId}/invite`, {
            email,
            role
          });

          if (!response.ok) {
            const errorData = await response.json().catch(() => ({}));
            throw new Error(errorData.detail || `Failed to invite user: ${response.status}`);
          }

          set({ isLoading: false });
          return true;
        } catch (error) {
          console.error('Failed to invite user to organization:', error);
          set({ isLoading: false });
          throw error;
        }
      },

      removeUserFromOrganization: async (orgId: string, userId: string): Promise<boolean> => {
        try {
          set({ isLoading: true });

          const response = await apiClient.delete(`/organizations/${orgId}/members/${userId}`);

          if (!response.ok) {
            const errorData = await response.json().catch(() => ({}));
            throw new Error(errorData.detail || `Failed to remove user: ${response.status}`);
          }

          set({ isLoading: false });
          return true;
        } catch (error) {
          console.error('Failed to remove user from organization:', error);
          set({ isLoading: false });
          throw error;
        }
      },

      leaveOrganization: async (orgId: string): Promise<boolean> => {
        try {
          set({ isLoading: true });

          const response = await apiClient.post(`/organizations/${orgId}/leave`);

          if (!response.ok) {
            const errorData = await response.json().catch(() => ({}));
            throw new Error(errorData.detail || `Failed to leave organization: ${response.status}`);
          }

          // Remove the organization from the local state
          const { organizations, currentOrganization } = get();
          const newOrganizations = organizations.filter(org => org.id !== orgId);
          const newCurrentOrg = currentOrganization?.id === orgId
            ? selectBestOrganization(newOrganizations)
            : currentOrganization;

          set({
            organizations: newOrganizations,
            currentOrganization: newCurrentOrg,
            isLoading: false
          });

          return true;
        } catch (error) {
          console.error('Failed to leave organization:', error);
          set({ isLoading: false });
          throw error;
        }
      },
    }),
    {
      name: 'organization-storage',
      partialize: (state) => ({
        currentOrganization: state.currentOrganization
      }),
    }
  )
);
