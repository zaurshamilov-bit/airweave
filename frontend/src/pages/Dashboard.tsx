import { useState, useEffect, useCallback } from "react";

import { Copy, Eye, Key, Plus, ExternalLink, FileText, Github } from "lucide-react";
import { useNavigate, Link, useLocation, useSearchParams } from "react-router-dom";
import { toast } from "sonner";
import { useTheme } from "@/lib/theme-provider";
import {
  CollectionCard,
  SourceButton,
  ApiKeyCard,
  ExampleProjectCard,
} from "@/components/dashboard";
import { clearStoredErrorDetails, getStoredErrorDetails } from "@/lib/error-utils";
import { DialogFlow } from "@/components/shared/DialogFlow";
import { useCollectionsStore, useSourcesStore } from "@/lib/stores";
import { apiClient } from "@/lib/api";
import { cn } from "@/lib/utils";
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip";

// Collection type definition
interface Collection {
  id: string;
  name: string;
  readable_id: string;
  status: string;
}

// Source type definition
interface Source {
  id: string;
  name: string;
  description?: string | null;
  short_name: string;
  labels?: string[];
}

// Source Connection definition
interface SourceConnection {
  id: string;
  name: string;
  short_name: string;
  collection: string;
  status?: string;
}

// Define action check response interface
interface ActionCheckResponse {
  allowed: boolean;
  action: string;
  reason?: 'payment_required' | 'usage_limit_exceeded' | null;
  details?: {
    message: string;
    current_usage?: number;
    limit?: number;
    payment_status?: string;
  } | null;
}


const Dashboard = () => {
  const navigate = useNavigate();
  const location = useLocation();
  const [searchParams] = useSearchParams();
  const { resolvedTheme } = useTheme();

  // Use collections store
  const {
    collections,
    isLoading: isLoadingCollections,
    fetchCollections,
    sourceConnections,
    fetchSourceConnections
  } = useCollectionsStore();

  // Use sources store
  const { sources, isLoading: isLoadingSources, fetchSources } = useSourcesStore();

  // Dialog state
  const [dialogOpen, setDialogOpen] = useState(false);
  const [selectedSource, setSelectedSource] = useState<{ id: string; name: string; short_name: string } | null>(null);

  // Error state for connection errors
  const [connectionError, setConnectionError] = useState<any>(null);
  const [errorDialogOpen, setErrorDialogOpen] = useState(false);

  // State for usage limits
  const [collectionsAllowed, setCollectionsAllowed] = useState(true);
  const [sourceConnectionsAllowed, setSourceConnectionsAllowed] = useState(true);
  const [entitiesAllowed, setEntitiesAllowed] = useState(true);
  const [syncsAllowed, setSyncsAllowed] = useState(true);
  const [usageCheckDetails, setUsageCheckDetails] = useState<{
    collections?: ActionCheckResponse | null;
    source_connections?: ActionCheckResponse | null;
    entities?: ActionCheckResponse | null;
    syncs?: ActionCheckResponse | null;
  }>({});
  const [isCheckingUsage, setIsCheckingUsage] = useState(true);

  // Check if actions are allowed based on usage limits
  const checkUsageActions = useCallback(async () => {
    try {
      // Check all four actions in parallel
      const [collectionsRes, sourceConnectionsRes, entitiesRes, syncsRes] = await Promise.all([
        apiClient.get('/usage/check-action?action=collections'),
        apiClient.get('/usage/check-action?action=source_connections'),
        apiClient.get('/usage/check-action?action=entities'),
        apiClient.get('/usage/check-action?action=syncs')
      ]);

      const details: typeof usageCheckDetails = {};

      if (collectionsRes.ok) {
        const data: ActionCheckResponse = await collectionsRes.json();
        setCollectionsAllowed(data.allowed);
        details.collections = data;
      }

      if (sourceConnectionsRes.ok) {
        const data: ActionCheckResponse = await sourceConnectionsRes.json();
        setSourceConnectionsAllowed(data.allowed);
        details.source_connections = data;
      }

      if (entitiesRes.ok) {
        const data: ActionCheckResponse = await entitiesRes.json();
        setEntitiesAllowed(data.allowed);
        details.entities = data;
      }

      if (syncsRes.ok) {
        const data: ActionCheckResponse = await syncsRes.json();
        setSyncsAllowed(data.allowed);
        details.syncs = data;
      }

      setUsageCheckDetails(details);
    } catch (error) {
      console.error('Failed to check usage actions:', error);
      // Default to allowed on error to not block users
      setCollectionsAllowed(true);
      setSourceConnectionsAllowed(true);
      setEntitiesAllowed(true);
      setSyncsAllowed(true);
    } finally {
      setIsCheckingUsage(false);
    }
  }, []);

  // Check for connection errors on mount
  useEffect(() => {
    const connectionStatus = searchParams.get('connected');
    if (connectionStatus === 'error') {
      const errorDetails = getStoredErrorDetails();
      if (errorDetails) {
        console.log("🔔 [Dashboard] Found stored error details:", errorDetails);
        setConnectionError(errorDetails);
        setErrorDialogOpen(true);

        // Clean up URL
        const newUrl = window.location.pathname;
        window.history.replaceState({}, '', newUrl);
      }
    }
  }, [searchParams]);

  // Initialize Zustand store subscribers
  useEffect(() => {
    // Subscribe to collections events
    const unsubscribeCollections = useCollectionsStore.getState().subscribeToEvents();

    // Initial fetch - use console logging to track API calls
    console.log("🔄 [Dashboard] Initializing collections and sources");

    // Load collections (will use cache if available)
    fetchCollections().then(collections => {
      console.log(`🔄 [Dashboard] Collections loaded: ${collections.length} collections available`);
    });

    // Load sources - will use cached data if available
    fetchSources().then(sources => {
      console.log(`🔄 [Dashboard] Sources loaded: ${sources.length} sources available`);
    });

    return () => {
      unsubscribeCollections();
    };
  }, [fetchCollections, fetchSources]);

  // Check usage limits on mount
  useEffect(() => {
    checkUsageActions();
  }, [checkUsageActions]);


  const handleRequestNewKey = () => {
    // Placeholder for requesting a new API key
    toast.info("New API key feature coming soon");
  };

  const handleSourceClick = (source: Source) => {
    setSelectedSource(source);
    setDialogOpen(true);
  };



  // Handle dialog close
  const handleDialogClose = async () => {
    setDialogOpen(false);
    setSelectedSource(null);
    setConnectionError(null);
    clearStoredErrorDetails(); // Ensure error data is cleared
    // Refresh collections
    fetchCollections();
    // Re-check usage limits after potentially creating a collection
    await checkUsageActions();
  };

  // Handle error dialog close
  const handleErrorDialogClose = () => {
    setErrorDialogOpen(false);
    setConnectionError(null);
    clearStoredErrorDetails();
  };

  // Top 3 collections
  const topCollections = collections.slice(0, 3);

  // Log when dialog open state changes
  useEffect(() => {
    console.log("🚪 Dashboard dialog open state:", dialogOpen);
  }, [dialogOpen]);

  // Modify the dialog open handler
  const handleDialogOpen = (open: boolean) => {
    console.log("🚪 Dashboard handleDialogOpen called with:", open);
    setDialogOpen(open);
  };

  return (
    <div className="mx-auto w-full max-w-[1800px] px-6 py-6 pb-8">
      <DialogFlow
        isOpen={dialogOpen}
        onOpenChange={handleDialogOpen}
        mode="source-button"
        sourceId={selectedSource?.id}
        sourceName={selectedSource?.name}
        sourceShortName={selectedSource?.short_name}
        dialogId="dashboard-source-dialog"
        onComplete={() => {
          // Handle completion
          fetchCollections(false);
        }}
      />

      {/* Error Dialog - for displaying errors from other pages */}
      {connectionError && (
        <DialogFlow
          isOpen={errorDialogOpen}
          onOpenChange={setErrorDialogOpen}
          mode="source-button"
          dialogId="dashboard-error-dialog"
          errorData={connectionError}
          onComplete={handleErrorDialogClose}
        />
      )}

      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        {/* Main content (left column) */}
        <div className="md:col-span-2 space-y-6 md:space-y-8">
          {/* Collections Section - only show when loading or has collections */}
          {(isLoadingCollections || collections.length > 0) && (
            <section>
              <div className="flex items-center justify-between mb-4 sm:mb-6">
                <h2 className="text-2xl sm:text-3xl font-bold">Collections</h2>
                <Link
                  to="/collections"
                  className="flex items-center text-sm text-primary hover:text-primary/80 hover:bg-accent/30 px-2 py-1.5 rounded-md"
                >
                  <ExternalLink className="mr-2 h-3.5 w-3.5 opacity-70" />
                  <span>See all {collections.length > 0 ? `(${collections.length})` : ''}</span>
                </Link>
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-3 gap-4 auto-rows-fr">
                {isLoadingCollections ? (
                  Array.from({ length: 3 }).map((_, index) => (
                    <div
                      key={index}
                      className="h-[160px] rounded-xl animate-pulse bg-slate-100 dark:bg-slate-800/50"
                    />
                  ))
                ) : (
                  topCollections.map((collection) => (
                    <CollectionCard
                      key={collection.id}
                      id={collection.id}
                      name={collection.name}
                      readableId={collection.readable_id}
                      status={collection.status}
                      onClick={() => navigate(`/collections/${collection.readable_id}`)}
                    />
                  ))
                )}
              </div>
            </section>
          )}

          {/* Create Collection Section */}
          <section>
            <h2 className="text-xl sm:text-2xl font-semibold mb-1 sm:mb-2">Create collection</h2>
            <p className="text-xs sm:text-sm text-muted-foreground mb-3 sm:mb-5">
              Choose a first source to add to your new collection
            </p>

            <div className="grid grid-cols-1 xs:grid-cols-2 sm:grid-cols-3 md:grid-cols-3 gap-3 auto-rows-fr">
              {isLoadingSources ? (
                <div className="col-span-full h-40 flex items-center justify-center">
                  <div className="animate-pulse flex flex-col items-center">
                    <div className="h-10 w-10 bg-gray-200 dark:bg-gray-700 rounded-md mb-4"></div>
                    <div className="h-4 w-32 bg-gray-200 dark:bg-gray-700 rounded mb-2"></div>
                    <div className="h-3 w-24 bg-gray-200 dark:bg-gray-700 rounded"></div>
                  </div>
                </div>
              ) : sources.length === 0 ? (
                <div className="col-span-full text-center py-10 text-muted-foreground">
                  No sources found
                </div>
              ) : (
                [...sources].sort((a, b) => a.name.localeCompare(b.name)).map((source) => (
                  <SourceButton
                    key={source.id}
                    id={source.id}
                    name={source.name}
                    shortName={source.short_name}
                    onClick={() => handleSourceClick(source)}
                    disabled={!collectionsAllowed || !sourceConnectionsAllowed || !entitiesAllowed || !syncsAllowed || isCheckingUsage}
                    usageCheckDetails={usageCheckDetails}
                  />
                ))
              )}
            </div>
          </section>
        </div>

        {/* Right Column */}
        <div className="md:col-span-1 space-y-6">
          {/* API Key Card */}
          <ApiKeyCard
            onRequestNewKey={handleRequestNewKey}
          />


        </div>
      </div>
    </div>
  );
};

export default Dashboard;
