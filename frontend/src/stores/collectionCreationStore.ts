import { create } from 'zustand';
import { persist } from 'zustand/middleware';

export type CreationStep =
  | 'collection-form'
  | 'source-select'
  | 'source-config'
  | 'oauth-redirect'
  | 'success';

export type AuthMode = 'oauth2' | 'direct_auth' | 'external_provider';

interface CollectionCreationState {
  // Modal state
  isOpen: boolean;
  currentStep: CreationStep;

  // Collection data
  collectionName: string;
  collectionDescription: string;
  collectionId?: string; // Set after creation

  // Source connection data
  selectedSource?: string; // short_name
  sourceName?: string; // Display name
  authMode?: AuthMode;
  authConfig?: Record<string, any>;
  configFields?: Record<string, any>;

  // OAuth flow state
  oauthState?: string;
  redirectUrl?: string;
  authenticationUrl?: string;
  connectionId?: string; // Set after successful connection

  // Actions
  openModal: (startStep?: CreationStep) => void;
  closeModal: () => void;
  setStep: (step: CreationStep) => void;

  // Collection actions
  setCollectionData: (name: string, description?: string) => void;
  setCollectionId: (id: string) => void;

  // Source actions
  selectSource: (shortName: string, displayName: string) => void;
  setAuthMode: (mode: AuthMode) => void;
  setAuthConfig: (config: Record<string, any>) => void;
  setConfigFields: (fields: Record<string, any>) => void;

  // OAuth actions
  setOAuthData: (state: string, redirectUrl: string, authUrl?: string) => void;
  setConnectionId: (id: string) => void;

  // Reset
  reset: () => void;
  resetSourceData: () => void;
}

const initialState = {
  isOpen: false,
  currentStep: 'collection-form' as CreationStep,
  collectionName: '',
  collectionDescription: '',
  collectionId: undefined,
  selectedSource: undefined,
  sourceName: undefined,
  authMode: undefined,
  authConfig: undefined,
  configFields: undefined,
  oauthState: undefined,
  redirectUrl: undefined,
  authenticationUrl: undefined,
  connectionId: undefined,
};

export const useCollectionCreationStore = create<CollectionCreationState>()(
  persist(
    (set) => ({
      ...initialState,

      openModal: (startStep = 'collection-form') => set({ isOpen: true, currentStep: startStep }),
      closeModal: () => {
        set({ isOpen: false });
        // Force clear persisted state to prevent stuck modal
        setTimeout(() => {
          set(initialState);
        }, 300);
      },
      setStep: (step) => set({ currentStep: step }),

      setCollectionData: (name, description) => set({
        collectionName: name,
        collectionDescription: description || ''
      }),

      setCollectionId: (id) => set({ collectionId: id }),

      selectSource: (shortName, displayName) => set({
        selectedSource: shortName,
        sourceName: displayName
      }),

      setAuthMode: (mode) => set({ authMode: mode }),
      setAuthConfig: (config) => set({ authConfig: config }),
      setConfigFields: (fields) => set({ configFields: fields }),

      setOAuthData: (state, redirectUrl, authUrl) => set({
        oauthState: state,
        redirectUrl: redirectUrl,
        authenticationUrl: authUrl
      }),

      setConnectionId: (id) => set({ connectionId: id }),

      reset: () => set(initialState),

      resetSourceData: () => set({
        selectedSource: undefined,
        sourceName: undefined,
        authMode: undefined,
        authConfig: undefined,
        configFields: undefined,
        oauthState: undefined,
        redirectUrl: undefined,
        authenticationUrl: undefined,
        connectionId: undefined,
      }),
    }),
    {
      name: 'collection-creation-storage',
      partialize: (state) => ({
        // Only persist what's needed for OAuth redirect
        // DO NOT persist isOpen to avoid modal getting stuck
        collectionId: state.collectionId,
        collectionName: state.collectionName,
        selectedSource: state.selectedSource,
        sourceName: state.sourceName,
        authMode: state.authMode,
        configFields: state.configFields,
        oauthState: state.oauthState,
        redirectUrl: state.redirectUrl,
      }),
    }
  )
);
