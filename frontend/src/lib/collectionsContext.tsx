import { createContext, useContext, useState, useEffect, useCallback, ReactNode } from 'react';
import { apiClient } from '@/lib/api';
import { onCollectionEvent, COLLECTION_DELETED, COLLECTION_CREATED, COLLECTION_UPDATED } from "@/lib/events";
import { useAuth } from './auth-context';

// Interface for Collection type
export interface Collection {
  id: string;
  name: string;
  readable_id: string;
  status: string;
}

interface CollectionsContextType {
  collections: Collection[];
  isLoading: boolean;
  error: string | null;
  refetchCollections: () => Promise<void>;
}

// Create the context
const CollectionsContext = createContext<CollectionsContextType>({
  collections: [],
  isLoading: false,
  error: null,
  refetchCollections: async () => {}
});

// Custom hook to use collections context
export const useCollections = () => useContext(CollectionsContext);

// Provider component
export const CollectionsProvider = ({ children }: { children: ReactNode }) => {
  const [collections, setCollections] = useState<Collection[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const { isReady } = useAuth();

  // Function to fetch collections from the API
  const fetchCollections = useCallback(async () => {
    // Don't attempt to fetch if authentication is not ready
    if (!isReady()) {
      console.log('Auth not ready yet, deferring collections fetch');
      return;
    }

    setIsLoading(true);
    setError(null);

    try {
      const response = await apiClient.get('/collections');

      if (response.ok) {
        const data = await response.json();
        setCollections(data);
      } else {
        const errorText = await response.text();
        setError(`Failed to load collections: ${errorText}`);
      }
    } catch (err) {
      setError(`An error occurred: ${err instanceof Error ? err.message : String(err)}`);
    } finally {
      setIsLoading(false);
    }
  }, [isReady]);

  // Initial fetch of collections only when auth is ready
  useEffect(() => {
    if (isReady()) {
      fetchCollections();
    }
  }, [fetchCollections, isReady]);

  // Listen for collection events to refresh the list
  useEffect(() => {
    // Subscribe to collection events
    const unsubscribeDeleted = onCollectionEvent(COLLECTION_DELETED, () => {
      if (isReady()) {
        fetchCollections();
      }
    });

    const unsubscribeCreated = onCollectionEvent(COLLECTION_CREATED, () => {
      if (isReady()) {
        fetchCollections();
      }
    });

    const unsubscribeUpdated = onCollectionEvent(COLLECTION_UPDATED, () => {
      if (isReady()) {
        fetchCollections();
      }
    });

    // Cleanup event listeners
    return () => {
      unsubscribeDeleted();
      unsubscribeCreated();
      unsubscribeUpdated();
    };
  }, [fetchCollections, isReady]);

  const value = {
    collections,
    isLoading,
    error,
    refetchCollections: fetchCollections
  };

  return (
    <CollectionsContext.Provider value={value}>
      {children}
    </CollectionsContext.Provider>
  );
};
