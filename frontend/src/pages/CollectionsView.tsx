import { useState, useEffect, useCallback } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Search, Plus } from "lucide-react";
import { useNavigate } from "react-router-dom";
import { CollectionCard } from "@/components/dashboard";
import { useCollectionsStore, useSourcesStore } from "@/lib/stores";
import { DialogFlow } from "@/components/shared";
import { apiClient } from "@/lib/api";
import { cn } from "@/lib/utils";
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip";
import { ActionCheckResponse } from "@/types";

const CollectionsView = () => {
  const navigate = useNavigate();
  const {
    collections,
    isLoading: isLoadingCollections,
    fetchCollections
  } = useCollectionsStore();

  const { fetchSources } = useSourcesStore();
  const [filteredCollections, setFilteredCollections] = useState([]);
  const [searchQuery, setSearchQuery] = useState("");

  // Dialog state
  const [dialogOpen, setDialogOpen] = useState(false);

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

  // Initialize collections and event listeners
  useEffect(() => {
    console.log("🔄 [CollectionsView] Initializing");

    // Subscribe to collection events
    const unsubscribe = useCollectionsStore.getState().subscribeToEvents();

    // Load collections (will use cache if available)
    fetchCollections().then(collections => {
      console.log(`🔄 [CollectionsView] Collections loaded: ${collections.length} collections available`);
    });

    return unsubscribe;
  }, [fetchCollections]);

  // Check usage limits on mount
  useEffect(() => {
    checkUsageActions();
  }, [checkUsageActions]);

  // Filter collections based on search query
  useEffect(() => {
    if (searchQuery.trim() === "") {
      setFilteredCollections(collections);
    } else {
      const query = searchQuery.toLowerCase();
      const filtered = collections.filter(
        (collection) =>
          collection.name.toLowerCase().includes(query) ||
          collection.readable_id.toLowerCase().includes(query)
      );
      setFilteredCollections(filtered);
    }
  }, [searchQuery, collections]);

  // Refresh collections after creating a new one
  const handleDialogClose = async () => {
    setDialogOpen(false);
    // Force refresh collections to get the newly created one
    fetchCollections(true);
    // Re-check usage limits after creating a collection
    await checkUsageActions();
  };

  // Open create collection dialog
  const handleCreateCollection = () => {
    // Prefetch sources before opening the dialog
    console.log("🔍 [CollectionsView] Pre-fetching sources before showing DialogFlow");
    fetchSources()
      .then(() => {
        // Open the DialogFlow with create-collection mode
        setDialogOpen(true);
      })
      .catch(err => {
        console.error("❌ [CollectionsView] Error prefetching sources:", err);
        // Still open the dialog even if prefetch fails
        setDialogOpen(true);
      });
  };

  return (
    <div className="mx-auto w-full max-w-[1800px] px-6 py-6 pb-8">
      {/* DialogFlow Dialog */}
      <DialogFlow
        isOpen={dialogOpen}
        onOpenChange={setDialogOpen}
        mode="create-collection"
        dialogId="collections-view-create-collection"
        onComplete={handleDialogClose}
      />

      {/* Header */}
      <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between mb-6 gap-4">
        <div>
          <h1 className="text-3xl font-bold mb-1">Collections</h1>
          <p className="text-sm text-muted-foreground">
            View and manage all your collections
          </p>
        </div>
        <TooltipProvider delayDuration={100}>
          <Tooltip>
            <TooltipTrigger asChild>
              <span tabIndex={0}>
                <Button
                  onClick={handleCreateCollection}
                  disabled={!collectionsAllowed || !sourceConnectionsAllowed || !entitiesAllowed || !syncsAllowed || isCheckingUsage}
                  className={cn(
                    "bg-primary text-white rounded-lg h-9 px-4 transition-all duration-200",
                    (!collectionsAllowed || !sourceConnectionsAllowed || !entitiesAllowed || !syncsAllowed || isCheckingUsage)
                      ? "opacity-50 cursor-not-allowed hover:bg-primary"
                      : "hover:bg-primary/90"
                  )}
                >
                  <Plus className="mr-2 h-4 w-4" />
                  Create Collection
                </Button>
              </span>
            </TooltipTrigger>
            {(!collectionsAllowed || !sourceConnectionsAllowed || !entitiesAllowed || !syncsAllowed) && (
              <TooltipContent className="max-w-xs">
                <p className="text-xs">
                  {!collectionsAllowed && usageCheckDetails.collections?.reason === 'usage_limit_exceeded' ? (
                    <>
                      Collection limit reached.{' '}
                      <a
                        href="/organization/settings?tab=billing"
                        className="underline"
                        onClick={(e) => e.stopPropagation()}
                      >
                        Upgrade your plan
                      </a>
                      {' '}to create more collections.
                    </>
                  ) : !sourceConnectionsAllowed && usageCheckDetails.source_connections?.reason === 'usage_limit_exceeded' ? (
                    <>
                      Source connection limit reached.{' '}
                      <a
                        href="/organization/settings?tab=billing"
                        className="underline"
                        onClick={(e) => e.stopPropagation()}
                      >
                        Upgrade your plan
                      </a>
                      {' '}for more connections.
                    </>
                  ) : !entitiesAllowed && usageCheckDetails.entities?.reason === 'usage_limit_exceeded' ? (
                    <>
                      Entity processing limit reached.{' '}
                      <a
                        href="/organization/settings?tab=billing"
                        className="underline"
                        onClick={(e) => e.stopPropagation()}
                      >
                        Upgrade your plan
                      </a>
                      {' '}to process more data.
                    </>
                  ) : !syncsAllowed && usageCheckDetails.syncs?.reason === 'usage_limit_exceeded' ? (
                    <>
                      Sync limit reached.{' '}
                      <a
                        href="/organization/settings?tab=billing"
                        className="underline"
                        onClick={(e) => e.stopPropagation()}
                      >
                        Upgrade your plan
                      </a>
                      {' '}for more syncs.
                    </>
                  ) : (
                    'Unable to create collection at this time.'
                  )}
                </p>
              </TooltipContent>
            )}
          </Tooltip>
        </TooltipProvider>
      </div>

      {/* Search bar */}
      <div className="mb-6">
        <div className="relative">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
          <Input
            type="text"
            placeholder="Search collections by name or ID..."
            className="pl-10 h-10 rounded-xl border-border focus:border-text/50 focus:ring-0 focus:ring-offset-0 focus:ring-text/50 dark:bg-background dark:focus:bg-background/80 transition-colors"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
          />
        </div>
      </div>

      {/* Collections Grid */}
      <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-3 xl:grid-cols-4 gap-6 sm:gap-8 auto-rows-fr">
        {isLoadingCollections ? (
          Array.from({ length: 8 }).map((_, index) => (
            <div
              key={index}
              className="h-[220px] rounded-xl animate-pulse bg-slate-100 dark:bg-slate-800/50"
            />
          ))
        ) : filteredCollections.length === 0 ? (
          <div className="col-span-full text-center py-20 text-muted-foreground">
            {searchQuery ? "No collections found matching your search" : "No collections found"}
          </div>
        ) : (
          filteredCollections.map((collection) => (
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
    </div>
  );
};

export default CollectionsView;
