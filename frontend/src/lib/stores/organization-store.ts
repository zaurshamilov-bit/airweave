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
