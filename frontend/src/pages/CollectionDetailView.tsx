import { useState, useEffect, useRef } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { Alert } from "@/components/ui/alert";
import { AlertCircle, RefreshCw, Pencil, Trash, Plus, Clock, Play, Plug, Copy, Check } from "lucide-react";
import { apiClient } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { toast } from "@/hooks/use-toast";
import { getAppIconUrl } from "@/lib/utils/icons";
import { useTheme } from "@/lib/theme-provider";
import { cn } from "@/lib/utils";
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
import SourceConnectionDetailView from "@/components/collection/SourceConnectionDetailView";
import { emitCollectionEvent, COLLECTION_DELETED } from "@/lib/events";
import { QueryTool } from '@/components/collection/QueryTool';
import { LiveApiDoc } from '@/components/collection/LiveApiDoc';

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

// DeleteCollectionDialog component
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
                        <p className="mb-4">This will permanently delete this collection and all its source connections. This action cannot be undone.</p>

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

const Collections = () => {
    /********************************************
     * COMPONENT STATE
     ********************************************/
    const { readable_id } = useParams();
    const { resolvedTheme } = useTheme();
    const isDark = resolvedTheme === 'dark';
    const navigate = useNavigate();

    // Page state
    const [isLoading, setIsLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);
    const [isReloading, setIsReloading] = useState(false);

    // Collection state
    const [collection, setCollection] = useState<Collection | null>(null);
    const [isEditingName, setIsEditingName] = useState(false);
    const nameInputRef = useRef<HTMLInputElement>(null);

    // Source connection state
    const [sourceConnections, setSourceConnections] = useState<SourceConnection[]>([]);
    const [selectedConnection, setSelectedConnection] = useState<SourceConnection | null>(null);

    // Add state for delete dialog
    const [showDeleteDialog, setShowDeleteDialog] = useState(false);
    const [confirmText, setConfirmText] = useState('');
    const [isDeleting, setIsDeleting] = useState(false);

    // Add state for copy animation
    const [isCopied, setIsCopied] = useState(false);

    /********************************************
     * API AND DATA FETCHING FUNCTIONS
     ********************************************/

    // Initial entry point for data loading
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

    // Gets list of source connections associated with a collection
    const fetchSourceConnections = async (collectionId: string) => {
        try {
            console.log("Fetching source connections for collection:", collectionId);
            const response = await apiClient.get(`/source-connections/?collection=${collectionId}`);

            if (response.ok) {
                const data = await response.json();
                console.log("Loaded source connections:", data);
                setSourceConnections(data);

                // Select first connection by default if there are any connections
                // and no connection is currently selected
                if (data.length > 0 && !selectedConnection) {
                    console.log("Auto-selecting first connection:", data[0]);
                    setSelectedConnection(data[0]);
                } else {
                    console.log("Not auto-selecting connection. Current selection:", selectedConnection);
                }
            } else {
                console.error("Failed to load source connections:", await response.text());
                setSourceConnections([]);
            }
        } catch (err) {
            console.error("Error fetching source connections:", err);
            setSourceConnections([]);
        } finally {
            setIsLoading(false);
        }
    };

    /********************************************
     * UI EVENT HANDLERS
     ********************************************/

    // Update selected connection
    const handleSelectConnection = async (connection: SourceConnection) => {
        setSelectedConnection(connection);
    };

    // Handle name editing
    const startEditingName = () => {
        setIsEditingName(true);
        // Set input's initial value to current name
        if (nameInputRef.current) {
            nameInputRef.current.value = collection?.name || "";
        }
        setTimeout(() => nameInputRef.current?.focus(), 0);
    };

    const handleSaveNameChange = async () => {
        // Get value directly from input ref
        const newName = nameInputRef.current?.value || "";

        if (!newName.trim() || newName === collection?.name) {
            setIsEditingName(false);
            return;
        }

        try {
            const response = await apiClient.patch(`/collections/${readable_id}`, { name: newName });
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
        fetchCollection();
    }, [readable_id]);

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
                    description: "Collection deleted successfully"
                });
                // Navigate back to dashboard after successful deletion
                navigate("/dashboard");
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
                    <Button onClick={() => navigate("/dashboard")}>
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
                                    isDark ? "bg-gray-800 border-gray-700" : "bg-background border-gray-300"
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
                                <Input
                                    ref={nameInputRef}
                                    defaultValue={collection?.name || ""}
                                    className="text-2xl font-bold h-10 min-w-[300px]"
                                    autoFocus
                                    onKeyDown={(e) => {
                                        if (e.key === 'Enter') {
                                            handleSaveNameChange();
                                        }
                                        if (e.key === 'Escape') {
                                            setIsEditingName(false);
                                        }
                                    }}
                                    onBlur={handleSaveNameChange}
                                />
                            </div>
                        ) : (
                            <div className="flex items-center gap-2">
                                <h1 className="text-3xl font-bold tracking-tight text-foreground">{collection?.name}</h1>
                                <Button
                                    variant="ghost"
                                    size="icon"
                                    className="h-6 w-6 text-muted-foreground hover:text-foreground"
                                    onClick={startEditingName}
                                >
                                    <Pencil className="h-3.5 w-3.5" />
                                </Button>
                                {collection?.status && (
                                    <Badge className="rounded-full font-semibold">{collection.status.toUpperCase()}</Badge>
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
                            isDark ? "hover:bg-gray-800" : "hover:bg-gray-100",
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
                        disabled={isDeleting}
                        className={cn(
                            "h-8 w-8 rounded-full transition-all",
                            isDark ? "hover:bg-gray-800 text-muted-foreground hover:text-destructive"
                                : "hover:bg-gray-100 text-muted-foreground hover:text-destructive"
                        )}
                        title="Delete collection"
                    >
                        <Trash className="h-4 w-4" />
                    </Button>
                </div>
            </div>
            <div className="flex justify-end gap-2 mb-0">
                <Button
                    variant="outline"
                    onClick={() => { }}
                    className={cn(
                        "gap-1 text-xs font-medium h-8 px-3",
                        isDark ? "border-gray-700 hover:bg-gray-800" : "border-gray-300 hover:bg-gray-100"
                    )}
                >
                    <Plus className="h-3.5 w-3.5" />
                    Add Source
                </Button>
                <Button
                    variant="outline"
                    onClick={() => { }}
                    className={cn(
                        "gap-1 text-xs font-medium h-8 px-3",
                        isDark ? "border-gray-700 hover:bg-gray-800" : "border-gray-300 hover:bg-gray-100"
                    )}
                >
                    <Plug className="h-3.5 w-3.5 mr-1" />
                    Refresh all sources
                </Button>
            </div>

            {/* Add QueryTool and LiveApiDoc when a connection with syncId is selected */}
            {selectedConnection?.sync_id && (
                <>
                    <div className='py-3 space-y-2 mt-1'>
                        <QueryTool
                            syncId={selectedConnection.sync_id}
                            collectionReadableId={collection?.readable_id}
                        />
                    </div>
                    <div className='py-1 space-y-1 mt-2'>
                        <LiveApiDoc syncId={selectedConnection.sync_id} />
                    </div>
                </>
            )}

            <hr className={cn(
                "border-t my-2 max-w-full",
                isDark ? "border-gray-700" : "border-gray-300"
            )} />

            {/* Source Connections Section */}
            <div className="mt-6">
                <h2 className="text-2xl font-bold tracking-tight mb-4 text-foreground">Source Connections</h2>

                <div className="flex flex-wrap gap-3">
                    {sourceConnections.map((connection) => (
                        <Button
                            key={connection.id}
                            variant="outline"
                            className={cn(
                                "w-60 h-13 flex items-center gap-2 justify-start overflow-hidden flex-shrink-0 flex-grow-0",
                                selectedConnection?.id === connection.id
                                    ? "border-2 border-primary"
                                    : isDark
                                        ? "border border-gray-700 bg-gray-800/50 hover:bg-gray-800"
                                        : "border border-gray-300 hover:bg-gray-100"
                            )}
                            onClick={() => handleSelectConnection(connection)}
                        >
                            <div className={cn(
                                "w-10 h-10 rounded-md flex items-center justify-center overflow-hidden flex-shrink-0",
                                isDark ? "bg-gray-800" : "bg-background"
                            )}>
                                <img
                                    src={getAppIconUrl(connection.short_name, resolvedTheme)}
                                    alt={connection.name}
                                    className="max-w-full max-h-full w-auto h-auto object-contain"
                                />
                            </div>
                            <div className="flex-1 min-w-0">
                                <span className="text-[18px] font-medium truncate block text-left text-foreground">{connection.name}</span>
                            </div>
                        </Button>
                    ))}
                </div>

                {sourceConnections.length === 0 && (
                    <div className={cn(
                        "text-center py-6 rounded-md border",
                        isDark ? "border-gray-700 bg-gray-800/20 text-gray-400" : "border-gray-200 bg-gray-50 text-muted-foreground"
                    )}>
                        <p className="mb-2">No source connections found.</p>
                        <Button
                            variant="outline"
                            className={cn(
                                "mt-2",
                                isDark ? "border-gray-700 hover:bg-gray-800" : ""
                            )}
                            onClick={() => { }}
                        >
                            <Plus className="h-4 w-4 mr-2" />
                            Add a source connection
                        </Button>
                    </div>
                )}
            </div>

            {/* Render SourceConnectionDetailView when a connection is selected */}
            {selectedConnection && (
                <SourceConnectionDetailView sourceConnectionId={selectedConnection.id} />
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
        </div>
    );
};

export default Collections;
