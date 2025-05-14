import { createContext, useContext, useState, useEffect, useCallback, ReactNode } from 'react';
import { apiClient } from '@/lib/api';
import { onCollectionEvent, COLLECTION_DELETED, COLLECTION_CREATED, COLLECTION_UPDATED } from "@/lib/events";

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

  // Function to fetch collections from the API
  const fetchCollections = useCallback(async () => {
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
  }, []);

  // Initial fetch of collections
  useEffect(() => {
    fetchCollections();
  }, [fetchCollections]);

  // Listen for collection events to refresh the list
  useEffect(() => {
    // Subscribe to collection events
    const unsubscribeDeleted = onCollectionEvent(COLLECTION_DELETED, () => {
      fetchCollections();
    });

    const unsubscribeCreated = onCollectionEvent(COLLECTION_CREATED, () => {
      fetchCollections();
    });

    const unsubscribeUpdated = onCollectionEvent(COLLECTION_UPDATED, () => {
      fetchCollections();
    });

    // Cleanup event listeners
    return () => {
      unsubscribeDeleted();
      unsubscribeCreated();
      unsubscribeUpdated();
    };
  }, [fetchCollections]);

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
