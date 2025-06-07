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

      switchOrganization: (orgId) => {
        const { organizations } = get();
        const org = organizations.find(o => o.id === orgId);
        if (org) {
          set({ currentOrganization: org });
        }
      },

      fetchUserOrganizations: async () => {
        try {
          set({ isLoading: true });

          const response = await apiClient.get('/organizations');

          if (!response.ok) {
            throw new Error(`Failed to fetch organizations: ${response.status}`);
          }

          const organizations = await response.json();

          // Set organizations and select appropriate current organization
          const currentOrgId = get().currentOrganization?.id;
          const currentOrg = organizations.find((org: Organization) => org.id === currentOrgId) ||
                            organizations.find((org: Organization) => org.is_primary) ||
                            organizations[0];

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
