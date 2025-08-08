import { useState, useEffect, useRef, useCallback } from "react";
import { useParams, useNavigate, useSearchParams } from "react-router-dom";
import { Alert } from "@/components/ui/alert";
import { AlertCircle, RefreshCw, Pencil, Trash, Plus, Clock, Play, Plug, Copy, Check, Loader2 } from "lucide-react";
import { apiClient } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { toast } from "@/hooks/use-toast";
import { getAppIconUrl } from "@/lib/utils/icons";
import { useTheme } from "@/lib/theme-provider";
import { cn } from "@/lib/utils";
import { StatusBadge, statusConfig } from "@/components/ui/StatusBadge";
import {
    AlertDialog,
    AlertDialogAction,
    AlertDialogCancel,
    AlertDialogContent,
    AlertDialogDescription,
    AlertDialogFooter,
    AlertDialogHeader,
    AlertDialogTitle,
} from "@/components/ui/alert-dialog";
import {
    Tooltip,
    TooltipContent,
    TooltipProvider,
    TooltipTrigger,
} from "@/components/ui/tooltip";
import SourceConnectionDetailView from "@/components/collection/SourceConnectionDetailView";
import { emitCollectionEvent, onCollectionEvent, COLLECTION_DELETED, SOURCE_CONNECTION_UPDATED } from "@/lib/events";
import { QueryToolAndLiveDoc } from '@/components/collection/QueryToolAndLiveDoc';
import { DialogFlow } from '@/components/shared';
import { protectedPaths } from "@/constants/paths";
import { useSyncStateStore } from "@/stores/syncStateStore";
import { syncStorageService } from "@/services/syncStorageService";
import { deriveSyncStatus, getSyncStatusColorClass } from "@/utils/syncStatus";
import { redirectWithError } from "@/lib/error-utils";
import { ActionCheckResponse } from "@/types";

interface DeleteCollectionDialogProps {
    open: boolean;
    onOpenChange: (open: boolean) => void;
    onConfirm: () => void;
    collectionReadableId: string;
    confirmText: string;
    setConfirmText: (text: string) => void;
}

const DeleteCollectionDialog = ({
    open,
    onOpenChange,
    onConfirm,
    collectionReadableId,
    confirmText,
    setConfirmText
}: DeleteCollectionDialogProps) => {
    const { resolvedTheme } = useTheme();
    const isDark = resolvedTheme === 'dark';

    return (
        <AlertDialog open={open} onOpenChange={onOpenChange}>
            <AlertDialogContent className={cn(
                "border-border",
                isDark ? "bg-card-solid text-foreground" : "bg-white"
            )}>
                <AlertDialogHeader>
                    <AlertDialogTitle className="text-foreground">Delete Collection</AlertDialogTitle>
                    <AlertDialogDescription className={isDark ? "text-gray-300" : "text-foreground"}>
                        <div className="space-y-3">
                            <p className="font-medium">This action will permanently delete:</p>
                            <ul className="space-y-2 ml-4">
                                <li className="flex items-start">
                                    <span className="mr-2">•</span>
                                    <span>The collection and all its source connections</span>
                                </li>
                                <li className="flex items-start">
                                    <span className="mr-2">•</span>
                                    <span>All synced data from the knowledge base</span>
                                </li>
                                <li className="flex items-start">
                                    <span className="mr-2">•</span>
                                    <span>All sync history and configuration</span>
                                </li>
                            </ul>
                            <p className="text-sm font-semibold text-destructive">This action cannot be undone.</p>
                        </div>

                        <div className="mt-4">
                            <label htmlFor="confirm-delete" className="text-sm font-medium block mb-2">
                                Type <span className="font-bold">{collectionReadableId}</span> to confirm deletion
                            </label>
                            <Input
                                id="confirm-delete"
                                value={confirmText}
                                onChange={(e) => setConfirmText(e.target.value)}
                                className="w-full"
                                placeholder={collectionReadableId}
                            />
                        </div>
                    </AlertDialogDescription>
                </AlertDialogHeader>
                <AlertDialogFooter>
                    <AlertDialogCancel className={isDark ? "bg-gray-800 text-white hover:bg-gray-700" : ""}>
                        Cancel
                    </AlertDialogCancel>
                    <AlertDialogAction
                        onClick={onConfirm}
                        disabled={confirmText !== collectionReadableId}
                        className="bg-red-600 text-white hover:bg-red-700 dark:bg-red-500 dark:text-white dark:hover:bg-red-600 disabled:opacity-50"
                    >
                        Delete Collection
                    </AlertDialogAction>
                </AlertDialogFooter>
            </AlertDialogContent>
        </AlertDialog>
    );
};

interface Collection {
    name: string;
    readable_id: string;
    id: string;
    created_at: string;
    modified_at: string;
    organization_id: string;
    created_by_email: string;
    modified_by_email: string;
    status?: string;
}

interface SourceConnection {
    id: string;
    name: string;
    description?: string;
    short_name: string;
    config_fields?: Record<string, any>;
    sync_id?: string;
    organization_id: string;
    created_at: string;
    modified_at: string;
    connection_id?: string;
    collection: string;
    created_by_email: string;
    modified_by_email: string;
    auth_fields?: Record<string, any> | string;
    status?: string;
    latest_sync_job_status?: string;
    latest_sync_job_id?: string;
    latest_sync_job_started_at?: string;
    latest_sync_job_completed_at?: string;
    cron_schedule?: string;
}

const Collections = () => {
    /********************************************
     * COMPONENT STATE
     ********************************************/
    const { readable_id } = useParams();
    const { resolvedTheme } = useTheme();
    const isDark = resolvedTheme === 'dark';
    const navigate = useNavigate();
    const [searchParams] = useSearchParams();
    const isFromOAuthSuccess = searchParams.get("connected") === "success";

    // Sync state store
    const syncStateStore = useSyncStateStore();
    const { subscribe, cleanup, activeSubscriptions } = syncStateStore;

    // Page state
    const [isLoading, setIsLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);
    const [isReloading, setIsReloading] = useState(false);

    // Collection state
    const [collection, setCollection] = useState<Collection | null>(null);
    const [isEditingName, setIsEditingName] = useState(false);
    const nameInputRef = useRef<HTMLDivElement>(null);

    // Source connection state
    const [sourceConnections, setSourceConnections] = useState<SourceConnection[]>([]);
    const [selectedConnection, setSelectedConnection] = useState<SourceConnection | null>(null);

    // Add state for delete dialog
    const [showDeleteDialog, setShowDeleteDialog] = useState(false);
    const [confirmText, setConfirmText] = useState('');
    const [isDeleting, setIsDeleting] = useState(false);

    // Add state for copy animation
    const [isCopied, setIsCopied] = useState(false);

    // Add state for add source dialog
    const [showAddSourceDialog, setShowAddSourceDialog] = useState(false);

    // Add state for refreshing all sources
    const [isRefreshingAll, setIsRefreshingAll] = useState(false);
    const [refreshingSourceIds, setRefreshingSourceIds] = useState<string[]>([]);

    // Add state for usage limits
    const [sourceConnectionsAllowed, setSourceConnectionsAllowed] = useState(true);
    const [sourceConnectionCheckDetails, setSourceConnectionCheckDetails] = useState<ActionCheckResponse | null>(null);
    const [entitiesAllowed, setEntitiesAllowed] = useState(true);
    const [entitiesCheckDetails, setEntitiesCheckDetails] = useState<ActionCheckResponse | null>(null);
    const [syncsAllowed, setSyncsAllowed] = useState(true);
    const [syncsCheckDetails, setSyncsCheckDetails] = useState<ActionCheckResponse | null>(null);
    const [isCheckingUsage, setIsCheckingUsage] = useState(true);

    /********************************************
     * API AND DATA FETCHING FUNCTIONS
     ********************************************/

    // Check if actions are allowed based on usage limits
    const checkUsageActions = useCallback(async (syncAmount: number = 1) => {
        try {
            // Check all three actions in parallel
            const [sourceResponse, entitiesResponse, syncsResponse] = await Promise.all([
                apiClient.get('/usage/check-action?action=source_connections'),
                apiClient.get('/usage/check-action?action=entities'),
                apiClient.get(`/usage/check-action?action=syncs&amount=${syncAmount}`)
            ]);

            if (sourceResponse.ok) {
                const data: ActionCheckResponse = await sourceResponse.json();
                setSourceConnectionsAllowed(data.allowed);
                setSourceConnectionCheckDetails(data);
            }

            if (entitiesResponse.ok) {
                const data: ActionCheckResponse = await entitiesResponse.json();
                setEntitiesAllowed(data.allowed);
                setEntitiesCheckDetails(data);
            }

            if (syncsResponse.ok) {
                const data: ActionCheckResponse = await syncsResponse.json();
                setSyncsAllowed(data.allowed);
                setSyncsCheckDetails(data);
            }
        } catch (error) {
            console.error('Failed to check usage actions:', error);
            // Default to allowed on error to not block users
            setSourceConnectionsAllowed(true);
            setEntitiesAllowed(true);
            setSyncsAllowed(true);
        } finally {
            setIsCheckingUsage(false);
        }
    }, []);

    // Fetch source connections for a collection with detailed sync job status
    const fetchSourceConnections = async (collectionId: string) => {
        try {
            console.log("Fetching source connections for collection:", collectionId);
            const response = await apiClient.get(`/source-connections/?collection=${collectionId}`);

            if (response.ok) {
                const listData = await response.json();
                console.log("Loaded source connection list:", listData);

                // Fetch detailed data for each connection to get sync job status
                const detailedConnections = await Promise.all(
                    listData.map(async (connection: any) => {
                        try {
                            const detailResponse = await apiClient.get(`/source-connections/${connection.id}`);
                            if (detailResponse.ok) {
                                const detailedData = await detailResponse.json();
                                console.log(`📝 Fetched detailed data for ${connection.name}:`, {
                                    latest_sync_job_status: detailedData.latest_sync_job_status,
                                    latest_sync_job_id: detailedData.latest_sync_job_id
                                });
                                return detailedData;
                            } else {
                                console.warn(`Failed to fetch details for connection ${connection.id}`);
                                return connection; // fallback to list data
                            }
                        } catch (err) {
                            console.warn(`Error fetching details for connection ${connection.id}:`, err);
                            return connection; // fallback to list data
                        }
                    })
                );

                setSourceConnections(detailedConnections);

                // Check for active sync jobs and subscribe to them
                detailedConnections.forEach(connection => {
                    if ((connection.latest_sync_job_status === 'pending' ||
                        connection.latest_sync_job_status === 'in_progress') &&
                        connection.latest_sync_job_id) {
                        console.log(`🔄 Found active sync job for ${connection.name}, subscribing...`);
                        subscribe(connection.latest_sync_job_id, connection.id);
                    }
                });

                // Always select the first connection when loading a new collection
                if (detailedConnections.length > 0) {
                    console.log("Auto-selecting first connection:", detailedConnections[0]);
                    setSelectedConnection(detailedConnections[0]);
                } else {
                    // If no connections, ensure selectedConnection is null
                    setSelectedConnection(null);
                    console.log("No connections to select");
                }
            } else {
                console.error("Failed to load source connections:", await response.text());
                setSourceConnections([]);
                setSelectedConnection(null);
            }
        } catch (err) {
            console.error("Error fetching source connections:", err);
            setSourceConnections([]);
            setSelectedConnection(null);
        } finally {
            setIsLoading(false);
        }
    };

    // Update the existing fetchCollection function to use our new function
    const fetchCollection = async () => {
        if (!readable_id) return;

        setIsLoading(true);
        setError(null);

        try {
            const response = await apiClient.get(`/collections/${readable_id}`);

            if (response.ok) {
                const data = await response.json();
                setCollection(data);
                // After successful collection fetch, fetch source connections
                fetchSourceConnections(data.readable_id);
            } else {
                if (response.status === 404) {
                    setError("Collection not found");
                } else {
                    const errorText = await response.text();
                    setError(`Failed to load collection: ${errorText}`);
                }
                setIsLoading(false);
            }
        } catch (err) {
            setError(`An error occurred: ${err instanceof Error ? err.message : String(err)}`);
            setIsLoading(false);
        }
    };

    /********************************************
     * UI EVENT HANDLERS
     ********************************************/

    // Update selected connection
    const handleSelectConnection = async (connection: SourceConnection) => {
        console.log("Manually selecting connection:", connection.id);
        setSelectedConnection(connection);
    };

    // Handle name editing
    const startEditingName = () => {
        setIsEditingName(true);
        setTimeout(() => {
            if (nameInputRef.current) {
                nameInputRef.current.innerText = collection?.name || "";
                // Place cursor at the end of text
                const range = document.createRange();
                const selection = window.getSelection();
                const textNode = nameInputRef.current.firstChild || nameInputRef.current;
                const textLength = nameInputRef.current.innerText.length;

                // Position at the end of text
                range.setStart(textNode, textLength);
                range.setEnd(textNode, textLength);

                if (selection) {
                    selection.removeAllRanges();
                    selection.addRange(range);
                }
                nameInputRef.current.focus();
            }
        }, 0);
    };

    const handleSaveNameChange = async () => {
        const newName = nameInputRef.current?.innerText.trim() || "";

        if (!newName || newName === collection?.name) {
            setIsEditingName(false);
            return;
        }

        try {
            const response = await apiClient.put(`/collections/${readable_id}`, null, { name: newName });
            if (!response.ok) throw new Error("Failed to update collection name");

            // Update local state after successful API call
            setCollection(prev => prev ? { ...prev, name: newName } : null);
            setIsEditingName(false);

            toast({
                title: "Success",
                description: "Collection name updated successfully"
            });
        } catch (error) {
            console.error("Error updating collection name:", error);
            toast({
                title: "Error",
                description: "Failed to update collection name",
                variant: "destructive"
            });
            setIsEditingName(false);
        }
    };

    // Handle copy to clipboard
    const handleCopyId = () => {
        if (collection?.readable_id) {
            navigator.clipboard.writeText(collection.readable_id);
            setIsCopied(true);

            // Reset after animation completes
            setTimeout(() => {
                setIsCopied(false);
            }, 1500);

            toast({
                title: "Copied",
                description: "ID copied to clipboard"
            });
        }
    };

    /********************************************
     * UTILITY FUNCTIONS
     ********************************************/

    // Reload data
    const reloadData = async () => {
        if (!readable_id) return;

        setIsReloading(true);
        try {
            await fetchCollection();
        } finally {
            setIsReloading(false);
        }
    };

    /********************************************
     * SIDE EFFECTS
     ********************************************/

    // Initial data loading
    useEffect(() => {
        console.log(`\nFetching collection because of readable id change\n`)
        setSelectedConnection(null);
        fetchCollection();
    }, [readable_id]);

    // Initial usage check on mount
    useEffect(() => {
        checkUsageActions(1);
    }, []);

    // Re-check usage limits when source connections change
    useEffect(() => {
        if (!isCheckingUsage && sourceConnections.length > 0) {
            checkUsageActions(sourceConnections.length);
        }
    }, [sourceConnections.length, checkUsageActions]);

    // Handle collection deletion
    const handleDeleteCollection = async () => {
        if (!readable_id || confirmText !== readable_id) return;

        setIsDeleting(true);
        try {
            const response = await apiClient.delete(`/collections/${readable_id}`);

            if (response.ok) {
                // Emit event that collection was deleted
                emitCollectionEvent(COLLECTION_DELETED, { id: readable_id });

                toast({
                    title: "Success",
                    description: "Collection and all associated data deleted successfully"
                });
                // Navigate back to dashboard after successful deletion
                navigate(protectedPaths.dashboard);
            } else {
                const errorText = await response.text();
                throw new Error(`Failed to delete collection: ${errorText}`);
            }
        } catch (err) {
            console.error("Error deleting collection:", err);
            toast({
                title: "Error",
                description: err instanceof Error ? err.message : "Failed to delete collection",
                variant: "destructive"
            });
        } finally {
            setIsDeleting(false);
            setShowDeleteDialog(false);
            setConfirmText(''); // Reset confirm text
        }
    };

    // Restore sync state from session storage on mount
    useEffect(() => {
        const storedState = syncStorageService.getStoredState();
        console.log("Restoring sync state from session storage:", storedState);

        // We'll check and re-subscribe to active jobs after source connections are loaded
        // This is handled in fetchSourceConnections
    }, []);

    // Cleanup subscriptions on unmount
    useEffect(() => {
        return () => {
            console.log("CollectionDetailView unmounting, cleaning up subscriptions");
            cleanup();
        };
    }, [cleanup]);

    // Listen for source connection updates
    useEffect(() => {
        const unsubscribe = onCollectionEvent(SOURCE_CONNECTION_UPDATED, (data) => {
            console.log("Source connection updated:", data);

            // Always refresh the list from server to ensure consistency
            if (collection?.readable_id) {
                fetchSourceConnections(collection.readable_id);
            }

            // If the deleted connection was selected, clear the selection
            // The fetchSourceConnections will auto-select the first connection if any remain
            if (data.deleted && selectedConnection?.id === data.id) {
                setSelectedConnection(null);
            }
        });

        return unsubscribe;
    }, [collection?.readable_id, selectedConnection?.id]);

    // Add right before the source connections section in render
    useEffect(() => {
        console.log("Source connections state:", {
            count: sourceConnections.length,
            connections: sourceConnections,
            selectedId: selectedConnection?.id
        });
    }, [sourceConnections, selectedConnection]);

    // Add this in the Source Connections Section right above the mapping
    console.log("Rendering source connections section", {
        count: sourceConnections.length,
        selectedId: selectedConnection?.id
    });

    // Handle refreshing all sources
    const handleRefreshAllSources = async () => {
        if (!collection?.readable_id) return;

        let response: Response | undefined;

        setIsRefreshingAll(true);
        try {
            response = await apiClient.post(`/collections/${collection.readable_id}/refresh_all`);

            if (response.ok) {
                const jobs = await response.json();
                // Store IDs of sources being refreshed
                const sourceIds = jobs.map(job => job.source_connection_id);
                setRefreshingSourceIds(sourceIds);

                // Subscribe to all new sync jobs
                jobs.forEach(job => {
                    if (job.id && job.source_connection_id) {
                        console.log(`Subscribing to sync job ${job.id} for source ${job.source_connection_id}`);
                        subscribe(job.id, job.source_connection_id);
                    }
                });

                toast({
                    title: "Success",
                    description: `Started refreshing ${sourceIds.length} source connection${sourceIds.length !== 1 ? 's' : ''}`
                });

                // Don't reload data immediately - we'll get live updates

                // Reset refreshing state if no jobs were started
                if (!jobs || jobs.length === 0) {
                    setIsRefreshingAll(false);
                }

                // Re-check usage limits after refresh
                await checkUsageActions(sourceConnections.length);
            } else {
                throw new Error("Failed to refresh sources");
            }
        } catch (error) {
            console.error("Error refreshing sources:", error);

            let errorMessage = "Failed to refresh all sources";
            let errorDetails = "";

            // Try to parse error response
            if (error instanceof Error) {
                errorMessage = error.message;
                errorDetails = error.stack || "";
            }

            // If the error came from an API response, try to get more details
            try {
                if (response && !response.ok) {
                    const errorData = await response.json();
                    if (errorData.detail) {
                        errorMessage = errorData.detail;
                    } else if (errorData.message) {
                        errorMessage = errorData.message;
                    } else if (typeof errorData === 'string') {
                        errorMessage = errorData;
                    }
                }
            } catch (parseError) {
                console.error("Could not parse error response:", parseError);
            }

            // Use redirectWithError to show the error in a dialog
            redirectWithError(navigate, {
                serviceName: collection?.name || "Collection",
                sourceShortName: "collection",
                errorMessage: errorMessage,
                errorDetails: errorDetails,
                canRetry: true,
                dialogId: `refresh-all-${collection?.readable_id}`,
                timestamp: Date.now()
            });

            setIsRefreshingAll(false);
        }
    };

    const handleSubscriptionComplete = useCallback(() => {
        setRefreshingSourceIds(prev => {
            const newIds = prev.filter(id => id !== selectedConnection?.id);
            if (newIds.length === 0) {
                setIsRefreshingAll(false);
            }
            return newIds;
        });
    }, [selectedConnection?.id]);

    // Show sync job status for consistency with SourceConnectionDetailView
    const getConnectionStatusIndicator = (connection: SourceConnection) => {
        // Check if we have live progress for this connection
        const liveProgress = syncStateStore.getProgressForSource(connection.id);
        const hasActiveSubscription = syncStateStore.hasActiveSubscription(connection.id);

        // Use shared utility to derive status
        const statusValue = deriveSyncStatus(
            liveProgress,
            hasActiveSubscription,
            connection.latest_sync_job_status
        );

        // Use shared utility to get color class
        const colorClass = getSyncStatusColorClass(statusValue);

        return (
            <span
                className={`inline-flex h-2.5 w-2.5 rounded-full ${colorClass} opacity-80`}
                title={statusValue}
            />
        );
    };

    if (error) {
        return (
            <div className="container mx-auto py-6">
                <h1 className="text-3xl font-bold mb-6 text-foreground">Collection Error</h1>
                <Alert variant="destructive">
                    <AlertCircle className="h-4 w-4" />
                    <div className="font-medium">Error</div>
                    <div>{error}</div>
                </Alert>
                <div className="mt-4">
                    <Button onClick={() => navigate(protectedPaths.dashboard)}>
                        Return to Dashboard
                    </Button>
                </div>
            </div>
        );
    }

    return (
        <div className={cn(
            "container mx-auto py-6",
            isDark ? "text-foreground" : ""
        )}>
            {/* Show loading state when isLoading or no collection data yet */}
            {(isLoading || !collection) && !error ? (
                <div className="w-full h-48 flex flex-col items-center justify-center space-y-4">
                    <Loader2 className="h-10 w-10 animate-spin text-primary" />
                    <p className="text-muted-foreground">Loading collection data...</p>
                </div>
            ) : (
                <>
                    {/* Header with Title and Status Badge */}
                    <div className="flex items-center justify-between py-4">
                        <div className="flex items-center gap-4">
                            {/* Source Icons */}
                            <div className="flex justify-start" style={{ minWidth: "4.5rem" }}>
                                {sourceConnections.map((connection, index) => (
                                    <div
                                        key={connection.id}
                                        className={cn(
                                            "w-14 h-14 rounded-md border p-1 flex items-center justify-center overflow-hidden",
                                            isDark ? "bg-gray-800 border-gray-700" : "bg-white border-gray-200"
                                        )}
                                        style={{
                                            marginLeft: index > 0 ? `-${Math.min(index * 8, 24)}px` : "0px",
                                            zIndex: sourceConnections.length - index
                                        }}
                                    >
                                        <img
                                            src={getAppIconUrl(connection.short_name, resolvedTheme)}
                                            alt={connection.name}
                                            className="max-w-full max-h-full w-auto h-auto object-contain"
                                        />
                                    </div>
                                ))}
                            </div>

                            <div className="flex flex-col justify-center">
                                {isEditingName ? (
                                    <div className="flex items-center gap-2">
                                        <div
                                            ref={nameInputRef}
                                            contentEditable
                                            className="text-3xl font-bold tracking-tight text-foreground outline-none p-1 pl-0 pr-3 rounded border border-border/40 transition-all duration-150"
                                            onKeyDown={(e) => {
                                                if (e.key === 'Enter') {
                                                    e.preventDefault();
                                                    handleSaveNameChange();
                                                }
                                                if (e.key === 'Escape') {
                                                    e.preventDefault();
                                                    setIsEditingName(false);
                                                }
                                            }}
                                            onBlur={handleSaveNameChange}
                                        />
                                    </div>
                                ) : (
                                    <div className="flex items-center gap-2">
                                        <h1 className="text-3xl font-bold tracking-tight text-foreground py-1 pl-0">{collection?.name}</h1>
                                        <Button
                                            variant="ghost"
                                            size="icon"
                                            className="h-5 w-5 text-muted-foreground hover:text-foreground"
                                            onClick={startEditingName}
                                        >
                                            <Pencil className="h-3 w-3" />
                                        </Button>
                                        {collection?.status && (
                                            <StatusBadge status={collection.status} />
                                        )}
                                    </div>
                                )}
                                <p className="text-muted-foreground text-sm group relative flex items-center">
                                    {collection?.readable_id}
                                    <button
                                        className="ml-1.5 opacity-0 group-hover:opacity-100 transition-opacity focus:opacity-100 focus:outline-none"
                                        onClick={handleCopyId}
                                        title="Copy ID"
                                    >
                                        {isCopied ? (
                                            <Check className="h-3.5 w-3.5 text-muted-foreground  transition-all" />
                                        ) : (
                                            <Copy className="h-3.5 w-3.5 text-muted-foreground transition-all" />
                                        )}
                                    </button>
                                </p>
                            </div>
                        </div>

                        {/* Header action buttons */}
                        <div className="flex items-center gap-2">
                            <Button
                                variant="ghost"
                                size="icon"
                                onClick={reloadData}
                                disabled={isReloading}
                                className={cn(
                                    "h-8 w-8 rounded-full transition-all duration-200",
                                    isDark ? "hover:bg-gray-800" : "hover:bg-gray-50",
                                )}
                                title="Reload page"
                            >
                                <RefreshCw className={cn(
                                    "h-4 w-4 transition-transform duration-500",
                                    isReloading ? "animate-spin" : "hover:rotate-90"
                                )} />
                            </Button>

                            <Button
                                variant="ghost"
                                size="icon"
                                onClick={() => setShowDeleteDialog(true)}
                                className={cn(
                                    "h-8 w-8 rounded-full transition-all duration-200",
                                    isDark ? "hover:bg-gray-800" : "hover:bg-gray-50"
                                )}
                                title="Delete collection"
                            >
                                <Trash className="h-4 w-4" />
                            </Button>
                        </div>
                    </div>

                    <div className="flex justify-end gap-2 mb-0">
                        <TooltipProvider delayDuration={100}>
                            <Tooltip>
                                <TooltipTrigger asChild>
                                    <span tabIndex={0}>
                                        <Button
                                            variant="outline"
                                            onClick={() => setShowAddSourceDialog(true)}
                                            disabled={!sourceConnectionsAllowed || isCheckingUsage}
                                            className={cn(
                                                "gap-1 text-xs font-medium h-8 px-3",
                                                isDark ? "border-gray-700 hover:bg-gray-800" : "border-gray-200 hover:bg-gray-50",
                                                (!sourceConnectionsAllowed || isCheckingUsage) && "opacity-50 cursor-not-allowed"
                                            )}
                                        >
                                            <Plus className="h-3.5 w-3.5" />
                                            Add Source
                                        </Button>
                                    </span>
                                </TooltipTrigger>
                                {!sourceConnectionsAllowed && sourceConnectionCheckDetails?.reason === 'usage_limit_exceeded' && (
                                    <TooltipContent className="max-w-xs">
                                        <p className="text-xs">
                                            Source connection limit reached.{' '}
                                            <a
                                                href="/organization/settings?tab=billing"
                                                className="underline"
                                                onClick={(e) => e.stopPropagation()}
                                            >
                                                Upgrade your plan
                                            </a>
                                            {' '}for more connections.
                                        </p>
                                    </TooltipContent>
                                )}
                            </Tooltip>
                        </TooltipProvider>
                        <TooltipProvider delayDuration={100}>
                            <Tooltip>
                                <TooltipTrigger asChild>
                                    <span tabIndex={0}>
                                        <Button
                                            variant="outline"
                                            onClick={handleRefreshAllSources}
                                            disabled={!entitiesAllowed || !syncsAllowed || isCheckingUsage}
                                            className={cn(
                                                "gap-1 text-xs font-medium h-8 px-3",
                                                isDark ? "border-gray-700 hover:bg-gray-800" : "border-gray-200 hover:bg-gray-50",
                                                (!entitiesAllowed || !syncsAllowed || isCheckingUsage) && "opacity-50 cursor-not-allowed"
                                            )}
                                        >
                                            <Plug className="h-3.5 w-3.5 mr-1" />
                                            Refresh all sources
                                        </Button>
                                    </span>
                                </TooltipTrigger>
                                {(!entitiesAllowed || !syncsAllowed) && (
                                    <TooltipContent className="max-w-xs">
                                        <p className="text-xs">
                                            {!entitiesAllowed && entitiesCheckDetails?.reason === 'usage_limit_exceeded' ? (
                                                <>
                                                    Entity processing limit reached.{' '}
                                                    <a
                                                        href="/organization/settings?tab=billing"
                                                        className="underline"
                                                        onClick={(e) => e.stopPropagation()}
                                                    >
                                                        Upgrade your plan
                                                    </a>
                                                    {' '}to refresh sources.
                                                </>
                                            ) : !syncsAllowed && syncsCheckDetails?.reason === 'usage_limit_exceeded' ? (
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
                                                'Unable to refresh sources at this time.'
                                            )}
                                        </p>
                                    </TooltipContent>
                                )}
                            </Tooltip>
                        </TooltipProvider>
                    </div>

                    {/* Add QueryToolAndLiveDoc when a connection with syncId is selected */}
                    {selectedConnection?.sync_id && (
                        <>
                            <div className='py-3 space-y-2 mt-1'>
                                <QueryToolAndLiveDoc
                                    collectionReadableId={collection?.readable_id || ''}
                                />
                            </div>
                        </>
                    )}

                    <hr className={cn(
                        "border-t my-2 max-w-full",
                        isDark ? "border-gray-700/30" : "border-gray-300/30"
                    )} />

                    {/* Source Connections Section */}
                    <div className="mt-6">
                        <h2 className="text-xl font-semibold tracking-tight mb-4 text-foreground">Source Connections</h2>

                        <div className="flex flex-wrap gap-3">
                            {sourceConnections.map((connection) => (
                                <div
                                    key={connection.id}
                                    className={cn(
                                        "h-10 flex items-center gap-2 overflow-hidden flex-shrink-0 flex-grow-0 px-3 py-2 rounded-md cursor-pointer transition-colors",
                                        selectedConnection?.id === connection.id
                                            ? "border-2 border-primary"
                                            : isDark
                                                ? "border border-gray-700 bg-gray-800/50 hover:bg-gray-700/70"
                                                : "border border-gray-200 bg-white hover:bg-gray-50"
                                    )}
                                    onClick={() => handleSelectConnection(connection)}
                                >
                                    {getConnectionStatusIndicator(connection)}

                                    <div className={cn(
                                        "rounded-md flex items-center justify-center overflow-hidden flex-shrink-0",
                                    )}>
                                        <img
                                            src={getAppIconUrl(connection.short_name, resolvedTheme)}
                                            alt={connection.name}
                                            className="h-6 w-6 object-contain"
                                        />
                                    </div>
                                    <div className="flex-1 min-w-0">
                                        <span className="text-[16px] font-medium truncate block text-foreground">{connection.name}</span>
                                    </div>
                                </div>
                            ))}
                        </div>

                        {sourceConnections.length === 0 && (
                            <div className={cn(
                                "text-center py-6 rounded-md border",
                                isDark ? "border-gray-700 bg-gray-800/20 text-gray-400" : "border-gray-200 bg-white text-muted-foreground"
                            )}>
                                <p className="mb-2">No source connections found.</p>
                                <TooltipProvider delayDuration={100}>
                                    <Tooltip>
                                        <TooltipTrigger asChild>
                                            <span tabIndex={0}>
                                                <Button
                                                    variant="outline"
                                                    className={cn(
                                                        "mt-2",
                                                        isDark ? "border-gray-700 hover:bg-gray-800" : "border-gray-200 hover:bg-gray-50",
                                                        (!sourceConnectionsAllowed || isCheckingUsage) && "opacity-50 cursor-not-allowed"
                                                    )}
                                                    onClick={() => setShowAddSourceDialog(true)}
                                                    disabled={!sourceConnectionsAllowed || isCheckingUsage}
                                                >
                                                    <Plus className="h-4 w-4 mr-2" />
                                                    Add a source connection
                                                </Button>
                                            </span>
                                        </TooltipTrigger>
                                        {!sourceConnectionsAllowed && sourceConnectionCheckDetails?.reason === 'usage_limit_exceeded' && (
                                            <TooltipContent className="max-w-xs">
                                                <p className="text-xs">
                                                    Source connection limit reached.{' '}
                                                    <a
                                                        href="/organization/settings?tab=billing"
                                                        className="underline"
                                                        onClick={(e) => e.stopPropagation()}
                                                    >
                                                        Upgrade your plan
                                                    </a>
                                                    {' '}for more connections.
                                                </p>
                                            </TooltipContent>
                                        )}
                                    </Tooltip>
                                </TooltipProvider>
                            </div>
                        )}
                    </div>

                    {/* Render SourceConnectionDetailView when a connection is selected */}
                    {selectedConnection && (
                        selectedConnection.short_name === "postgresql" ? (
                            <div className={cn(
                                "mt-6 p-8 rounded-lg border text-center",
                                isDark ? "border-gray-700/50 bg-gray-800/30" : "border-gray-200 bg-gray-50"
                            )}>
                                <AlertCircle className={cn(
                                    "h-12 w-12 mx-auto mb-4",
                                    isDark ? "text-gray-400" : "text-gray-500"
                                )} />
                                <p className={cn(
                                    "text-lg font-medium",
                                    isDark ? "text-gray-300" : "text-gray-700"
                                )}>
                                    PostgreSQL sync visualization not yet supported
                                </p>
                                <p className={cn(
                                    "text-sm mt-2 max-w-md mx-auto",
                                    isDark ? "text-gray-400" : "text-gray-500"
                                )}>
                                    Entity graph and progress tracking for PostgreSQL sources is coming soon.
                                    You can still run syncs and query your data - the sync will complete in the background.
                                </p>
                                <div className={cn(
                                    "mt-4 p-3 rounded-md text-sm text-left max-w-sm mx-auto",
                                    isDark ? "bg-gray-700/50 text-gray-300" : "bg-gray-100 text-gray-600"
                                )}>
                                    <p className="font-medium mb-1">💡 Tip:</p>
                                    <p>Check the sync status badge in the source connection list above to see if your sync is running.</p>
                                </div>
                            </div>
                        ) : (
                            <div className="mt-10">
                                <SourceConnectionDetailView
                                    key={selectedConnection.id}
                                    sourceConnectionId={selectedConnection.id}
                                />
                            </div>
                        )
                    )}

                    {/* Delete Collection Dialog */}
                    <DeleteCollectionDialog
                        open={showDeleteDialog}
                        onOpenChange={setShowDeleteDialog}
                        onConfirm={handleDeleteCollection}
                        collectionReadableId={collection?.readable_id || ''}
                        confirmText={confirmText}
                        setConfirmText={setConfirmText}
                    />

                    {/* Replace this ConnectFlow with DialogFlow */}
                    {collection && (
                        <DialogFlow
                            isOpen={showAddSourceDialog}
                            onOpenChange={setShowAddSourceDialog}
                            mode="add-source"
                            collectionId={collection.readable_id}
                            collectionName={collection.name}
                            dialogId="collection-detail-add-source"
                            onComplete={async (newSourceConnection?: any) => {
                                setShowAddSourceDialog(false);

                                // If we have a new source connection with an active sync job, subscribe to it
                                if (newSourceConnection &&
                                    (newSourceConnection.latest_sync_job_status === 'pending' ||
                                        newSourceConnection.latest_sync_job_status === 'in_progress') &&
                                    newSourceConnection.latest_sync_job_id) {
                                    console.log(`New source connection created, subscribing to sync job ${newSourceConnection.latest_sync_job_id}`);
                                    subscribe(newSourceConnection.latest_sync_job_id, newSourceConnection.id);
                                }

                                // Reload to get the new source connection in the list
                                await reloadData();

                                // Re-check source connection limits after creating a new one
                                await checkUsageActions(sourceConnections.length + 1);
                            }}
                        />
                    )}
                </>
            )}
        </div>
    );
};

export default Collections;
