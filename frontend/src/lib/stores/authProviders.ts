import { create } from 'zustand';
import { apiClient } from '@/lib/api';

export interface AuthProvider {
    id: string;
    name: string;
    short_name: string;
    description?: string;
    auth_type: string;
    class_name: string;
    auth_config_class: string;
    config_class: string;
    organization_id?: string;
    created_at: string;
    modified_at: string;
}

interface AuthProvidersStore {
    authProviders: AuthProvider[];
    isLoading: boolean;
    error: string | null;
    fetchAuthProviders: () => Promise<AuthProvider[]>;
}

export const useAuthProvidersStore = create<AuthProvidersStore>((set, get) => ({
    authProviders: [],
    isLoading: false,
    error: null,

    fetchAuthProviders: async () => {
        // Return cached data if available and not loading
        const currentState = get();
        if (currentState.authProviders.length > 0 && !currentState.isLoading) {
            return currentState.authProviders;
        }

        set({ isLoading: true, error: null });

        try {
            const response = await apiClient.get('/auth-providers/list');

            if (!response.ok) {
                throw new Error(`Failed to fetch auth providers: ${response.status}`);
            }

            const authProviders = await response.json();
            set({ authProviders, isLoading: false });
            return authProviders;
        } catch (error) {
            const errorMessage = error instanceof Error ? error.message : 'Failed to fetch auth providers';
            set({ error: errorMessage, isLoading: false });
            throw error;
        }
    },
}));
