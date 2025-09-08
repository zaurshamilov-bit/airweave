import { create } from 'zustand';
import { persist } from 'zustand/middleware';

export type CreationStep =
  | 'collection-form'
  | 'source-select'
  | 'source-config'
  | 'oauth-redirect'
  | 'success';

export type AuthMode = 'oauth2' | 'direct_auth' | 'external_provider';

// Flow types to track entry point
export type FlowType =
  | 'create-collection'        // From DashboardLayout - no preselection
  | 'create-with-source'       // From Dashboard - source preselected
  | 'add-to-collection';       // From CollectionDetailView - collection exists

interface CollectionCreationState {
  // Modal state
  isOpen: boolean;
  currentStep: CreationStep;
  flowType: FlowType;

  // Collection data
  collectionName: string;
  collectionDescription: string;
  collectionId?: string; // Set after creation or passed in for add-to-collection
  existingCollectionId?: string; // For add-to-collection flow
  existingCollectionName?: string; // For add-to-collection flow

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
  openForCreateCollection: () => void;
  openForCreateWithSource: (sourceShortName: string, sourceName: string, authMode?: AuthMode) => void;
  openForAddToCollection: (collectionId: string, collectionName: string) => void;
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

  // Helper getters
  isAddingToExistingCollection: () => boolean;
  getInitialStep: () => CreationStep;
}

const initialState = {
  isOpen: false,
  currentStep: 'collection-form' as CreationStep,
  flowType: 'create-collection' as FlowType,
  collectionName: '',
  collectionDescription: '',
  collectionId: undefined,
  existingCollectionId: undefined,
  existingCollectionName: undefined,
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
    (set, get) => ({
      ...initialState,

      openModal: (startStep = 'collection-form') => set({ isOpen: true, currentStep: startStep }),

      // Flow-specific open methods
      openForCreateCollection: () => {
        // Clear any previous state first
        const currentState = get();
        if (currentState.isOpen) {
          set({ isOpen: false });
        }

        // Then open with new state
        setTimeout(() => {
          set({
            ...initialState,
            isOpen: true,
            flowType: 'create-collection',
            currentStep: 'source-select', // Start with source selection
          });
        }, 50);
      },

      openForCreateWithSource: (sourceShortName, sourceName, authMode) => {
        // Clear any previous state first
        const currentState = get();
        if (currentState.isOpen) {
          set({ isOpen: false });
        }

        // Then open with new state
        setTimeout(() => {
          set({
            ...initialState,
            isOpen: true,
            flowType: 'create-with-source',
            currentStep: 'collection-form', // Start with collection form since source is preselected
            selectedSource: sourceShortName,
            sourceName: sourceName,
            authMode: authMode,
          });
        }, 50);
      },

      openForAddToCollection: (collectionId, collectionName) => {
        // Clear any previous state first
        const currentState = get();
        if (currentState.isOpen) {
          set({ isOpen: false });
        }

        // Then open with new state
        setTimeout(() => {
          set({
            ...initialState,
            isOpen: true,
            flowType: 'add-to-collection',
            currentStep: 'source-select', // Start with source selection
            existingCollectionId: collectionId,
            existingCollectionName: collectionName,
            collectionId: collectionId, // Set this for the flow
            collectionName: collectionName, // Use existing name
          });
        }, 50);
      },

      closeModal: () => {
        set({ isOpen: false });
        // Don't automatically reset state here - let components handle it
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

      // Helper getters
      isAddingToExistingCollection: () => {
        const state = get();
        return state.flowType === 'add-to-collection';
      },

      getInitialStep: () => {
        const state = get();
        switch (state.flowType) {
          case 'create-collection':
            return 'source-select';
          case 'create-with-source':
            return 'collection-form';
          case 'add-to-collection':
            return 'source-select';
          default:
            return 'collection-form';
        }
      },
    }),
    {
      name: 'collection-creation-storage',
      partialize: (state) => ({
        // Only persist what's needed for OAuth redirect
        // DO NOT persist isOpen to avoid modal getting stuck
        flowType: state.flowType,
        collectionId: state.collectionId,
        collectionName: state.collectionName,
        existingCollectionId: state.existingCollectionId,
        existingCollectionName: state.existingCollectionName,
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
