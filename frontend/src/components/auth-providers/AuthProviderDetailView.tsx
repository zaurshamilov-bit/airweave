import React, { useState, useEffect } from "react";
import type { DialogViewProps } from "@/components/types/dialog";
import { useTheme } from "@/lib/theme-provider";
import { cn } from "@/lib/utils";
import { apiClient } from "@/lib/api";
import { Copy, Check, Trash, Pencil } from "lucide-react";
import { toast } from "sonner";
import { getAuthProviderIconUrl } from "@/lib/utils/icons";
import { format } from "date-fns";
import { useAuthProvidersStore } from "@/lib/stores/authProviders";
import { clearStoredErrorDetails } from "@/lib/error-utils";
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

// Delete Connection Dialog component
interface DeleteConnectionDialogProps {
    open: boolean;
    onOpenChange: (open: boolean) => void;
    onConfirm: () => void;
    connectionReadableId: string;
    confirmText: string;
    setConfirmText: (text: string) => void;
    isDeleting: boolean;
    isDark: boolean;
}

const DeleteConnectionDialog: React.FC<DeleteConnectionDialogProps> = ({
    open,
    onOpenChange,
    onConfirm,
    connectionReadableId,
    confirmText,
    setConfirmText,
    isDeleting,
    isDark
}) => (
    <AlertDialog open={open} onOpenChange={onOpenChange}>
        <AlertDialogContent className={cn(
            "border-border",
            isDark ? "bg-card-solid text-foreground" : "bg-white"
        )}>
            <AlertDialogHeader>
                <AlertDialogTitle className="text-foreground">Delete Auth Provider Connection</AlertDialogTitle>
                <AlertDialogDescription className={isDark ? "text-gray-300" : "text-foreground"}>
                    <div className="mb-4">
                        This will permanently delete this auth provider connection.
                    </div>
                    <div className="mb-4 font-semibold text-red-500">
                        Warning: All source connections that were created using this auth provider will also be deleted,
                        as they will no longer work without this connection.
                    </div>
                    <div className="mb-4">
                        This action cannot be undone.
                    </div>

                    <div className="mt-4">
                        <label htmlFor="confirm-delete" className="text-sm font-medium block mb-2">
                            Type <span className="font-bold">{connectionReadableId}</span> to confirm deletion
                        </label>
                        <input
                            id="confirm-delete"
                            value={confirmText}
                            onChange={(e) => setConfirmText(e.target.value)}
                            className={cn(
                                "w-full px-3 py-2 rounded-lg text-sm",
                                "border bg-transparent",
                                "focus:outline-none focus:border-gray-400 dark:focus:border-gray-600",
                                isDark
                                    ? "border-gray-700 text-white placeholder:text-gray-500"
                                    : "border-gray-200 text-gray-900 placeholder:text-gray-400"
                            )}
                            placeholder={connectionReadableId}
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
                    disabled={confirmText !== connectionReadableId || isDeleting}
                    className="bg-red-600 text-white hover:bg-red-700 dark:bg-red-500 dark:text-white dark:hover:bg-red-600 disabled:opacity-50"
                >
                    {isDeleting ? "Deleting..." : "Delete Connection"}
                </AlertDialogAction>
            </AlertDialogFooter>
        </AlertDialogContent>
    </AlertDialog>
);

export interface AuthProviderDetailViewProps extends DialogViewProps {
    viewData?: {
        authProviderConnectionId?: string;
        authProviderName?: string;
        authProviderShortName?: string;
        dialogId?: string;
        [key: string]: any;
    };
}

export const AuthProviderDetailView: React.FC<AuthProviderDetailViewProps> = ({
    onCancel,
    onComplete,
    viewData = {},
    onError,
}) => {
    const { authProviderConnectionId, authProviderName, authProviderShortName } = viewData;
    const { resolvedTheme } = useTheme();
    const isDark = resolvedTheme === 'dark';
    const { fetchAuthProviderConnections } = useAuthProvidersStore();

    const [loading, setLoading] = useState(true);
    const [connectionDetails, setConnectionDetails] = useState<any>(null);
    const [copiedField, setCopiedField] = useState<string | null>(null);

    // Delete dialog state
    const [showDeleteDialog, setShowDeleteDialog] = useState(false);
    const [confirmText, setConfirmText] = useState('');
    const [isDeleting, setIsDeleting] = useState(false);
    const [isClosing, setIsClosing] = useState(false);

    console.log('🔍 [AuthProviderDetailView] Component mounted with:', {
        authProviderConnectionId,
        authProviderName,
        authProviderShortName,
        viewData
    });

    // Log component lifecycle
    useEffect(() => {
        console.log('🌟 [AuthProviderDetailView] useEffect mount check');

        return () => {
            console.log('💥 [AuthProviderDetailView] Component unmounting');
            // Clear any stored errors when component unmounts
            clearStoredErrorDetails();
        };
    }, []);

    // Fetch connection details
    useEffect(() => {
        if (!authProviderConnectionId || isClosing) {
            if (!authProviderConnectionId) {
                console.warn('⚠️ [AuthProviderDetailView] No authProviderConnectionId provided');
            }
            return;
        }

        let isMounted = true;

        const fetchConnectionDetails = async () => {
            console.log('📡 [AuthProviderDetailView] Fetching connection details for:', authProviderConnectionId);
            setLoading(true);
            try {
                const response = await apiClient.get(`/auth-providers/connections/${authProviderConnectionId}`);
                if (response.ok && isMounted) {
                    const data = await response.json();
                    setConnectionDetails(data);
                } else if (!response.ok) {
                    const errorText = await response.text();
                    throw new Error(`Failed to load connection details: ${errorText}`);
                }
            } catch (error) {
                if (isMounted && !isClosing) {
                    console.error("Error fetching connection details:", error);
                    if (onError) {
                        onError(error instanceof Error ? error : new Error(String(error)), authProviderName);
                    }
                }
            } finally {
                if (isMounted) {
                    setLoading(false);
                }
            }
        };

        fetchConnectionDetails();

        return () => {
            isMounted = false;
        };
    }, [authProviderConnectionId, authProviderName, onError, isClosing]);

    const handleCopy = async (value: string, fieldName: string) => {
        try {
            await navigator.clipboard.writeText(value);
            setCopiedField(fieldName);
            toast.success(`${fieldName} copied to clipboard`);

            // Reset copied state after 2 seconds
            setTimeout(() => {
                setCopiedField(null);
            }, 2000);
        } catch (error) {
            toast.error("Failed to copy to clipboard");
        }
    };

    const formatDate = (dateString: string) => {
        try {
            return format(new Date(dateString), "PPP 'at' p");
        } catch {
            return dateString;
        }
    };

    const handleDeleteConnection = async () => {
        if (!authProviderConnectionId || confirmText !== connectionDetails?.readable_id) return;

        setIsDeleting(true);
        setIsClosing(true);  // Prevent any further fetches

        try {
            const response = await apiClient.delete(`/auth-providers/${authProviderConnectionId}`);

            if (response.ok) {
                toast.success("Auth provider connection deleted successfully");

                // Clear any stored error details to prevent error dialog on navigation
                clearStoredErrorDetails();

                // Close the delete dialog immediately
                setShowDeleteDialog(false);
                setConfirmText('');

                // Refresh auth provider connections in the store
                await fetchAuthProviderConnections();

                // Close the main dialog using onComplete to properly cleanup
                if (onComplete) {
                    onComplete({ success: true, action: 'deleted' });
                }

                // Navigate will be handled by the parent component after dialog closes
            } else {
                const errorText = await response.text();
                throw new Error(`Failed to delete auth provider connection: ${errorText}`);
            }
        } catch (err) {
            console.error("Error deleting auth provider connection:", err);
            toast.error(err instanceof Error ? err.message : "Failed to delete auth provider connection");
            setIsDeleting(false);
            setShowDeleteDialog(false);
            setConfirmText(''); // Reset confirm text
        }
    };

    if (loading) {
        return (
            <div className="flex justify-center items-center py-8">
                <div className="animate-spin w-8 h-8 border-4 border-blue-500 border-t-transparent rounded-full"></div>
            </div>
        );
    }

    if (!connectionDetails) {
        return (
            <div className="text-center py-8 text-muted-foreground">
                <p>No connection details available</p>
            </div>
        );
    }

    const DeleteConnectionDialogComponent = (
        <DeleteConnectionDialog
            open={showDeleteDialog}
            onOpenChange={setShowDeleteDialog}
            onConfirm={handleDeleteConnection}
            connectionReadableId={connectionDetails?.readable_id}
            confirmText={confirmText}
            setConfirmText={setConfirmText}
            isDeleting={isDeleting}
            isDark={isDark}
        />
    );

    return (
        <div className="h-full flex flex-col max-h-[90vh]">
            {/* Fixed header with action buttons */}
            <div className={cn(
                "px-6 pt-6 pb-4 border-b",
                isDark ? "border-gray-800/50" : "border-gray-100"
            )}>
                <div className="flex items-center justify-between">
                    <h2 className="text-lg font-medium text-gray-900 dark:text-white">
                        {authProviderName} Connection
                    </h2>

                    {/* Action buttons - more subtle */}
                    <div className="flex gap-1">
                        <button
                            onClick={() => {
                                if (onComplete) {
                                    onComplete({
                                        action: 'edit',
                                        authProviderConnectionId,
                                        authProviderName,
                                        authProviderShortName
                                    });
                                }
                            }}
                            className={cn(
                                "h-8 w-8 rounded-lg transition-all duration-150 flex items-center justify-center",
                                isDark
                                    ? "hover:bg-gray-800/60 text-gray-400 hover:text-gray-200"
                                    : "hover:bg-gray-100 text-gray-500 hover:text-gray-700"
                            )}
                            title="Edit connection"
                        >
                            <Pencil className="h-4 w-4" />
                        </button>

                        <button
                            onClick={() => setShowDeleteDialog(true)}
                            className={cn(
                                "h-8 w-8 rounded-lg transition-all duration-150 flex items-center justify-center",
                                isDark
                                    ? "hover:bg-gray-800/60 text-gray-400 hover:text-red-400"
                                    : "hover:bg-gray-100 text-gray-500 hover:text-red-500"
                            )}
                            title="Delete connection"
                        >
                            <Trash className="h-4 w-4" />
                        </button>
                    </div>
                </div>
                <p className="mt-1 text-xs text-gray-500 dark:text-gray-400">
                    View and manage your {authProviderName} connection details
                </p>
            </div>

            {/* Content area - scrollable with better spacing */}
            <div className="flex-1 overflow-y-auto px-6 py-6">
                <div className="space-y-6 pb-6">
                    {/* Auth Provider Icon - more integrated */}
                    {authProviderShortName && (
                        <div className="flex justify-center py-4">
                            <div className={cn(
                                "w-20 h-20 flex items-center justify-center rounded-xl p-3",
                                isDark ? "bg-gray-800/30" : "bg-gray-50/70"
                            )}>
                                <img
                                    src={getAuthProviderIconUrl(authProviderShortName, resolvedTheme)}
                                    alt={`${authProviderName} icon`}
                                    className="w-full h-full object-contain"
                                    onError={(e) => {
                                        e.currentTarget.style.display = 'none';
                                        e.currentTarget.parentElement!.innerHTML = `
                                            <div class="w-full h-full rounded-lg flex items-center justify-center ${isDark ? 'bg-blue-900/50' : 'bg-blue-50'}">
                                                <span class="text-xl font-semibold ${isDark ? 'text-blue-400' : 'text-blue-600'}">
                                                    ${authProviderShortName.substring(0, 2).toUpperCase()}
                                                </span>
                                            </div>
                                        `;
                                    }}
                                />
                            </div>
                        </div>
                    )}

                    {/* Connection Details - cleaner design */}
                    <div className="space-y-4">
                        {/* Name */}
                        <div className="space-y-1.5">
                            <label className="block text-[10px] font-medium text-gray-500 dark:text-gray-500 uppercase tracking-wide">
                                Name
                            </label>
                            <div className={cn(
                                "w-full px-3 py-2 rounded-md text-sm",
                                isDark
                                    ? "bg-gray-800/40 text-gray-100"
                                    : "bg-gray-50 text-gray-900"
                            )}>
                                {connectionDetails.name}
                            </div>
                        </div>

                        {/* Readable ID */}
                        <div className="space-y-1.5">
                            <label className="block text-[10px] font-medium text-gray-500 dark:text-gray-500 uppercase tracking-wide">
                                Readable ID
                            </label>
                            <div className={cn(
                                "w-full px-3 py-2 rounded-md text-sm flex items-center justify-between group",
                                isDark
                                    ? "bg-gray-800/40 text-gray-100"
                                    : "bg-gray-50 text-gray-900"
                            )}>
                                <span className="font-mono text-xs break-all">{connectionDetails.readable_id}</span>
                                <button
                                    onClick={() => handleCopy(connectionDetails.readable_id, "Readable ID")}
                                    className={cn(
                                        "p-1 rounded transition-opacity opacity-0 group-hover:opacity-100",
                                        isDark
                                            ? "hover:bg-gray-700/50"
                                            : "hover:bg-gray-200/50"
                                    )}
                                >
                                    {copiedField === "Readable ID" ? (
                                        <Check className="h-3.5 w-3.5 text-green-500" />
                                    ) : (
                                        <Copy className="h-3.5 w-3.5 text-gray-400" />
                                    )}
                                </button>
                            </div>
                        </div>

                        {/* Created By */}
                        {connectionDetails.created_by_email && (
                            <div className="space-y-1.5">
                                <label className="block text-[10px] font-medium text-gray-500 dark:text-gray-500 uppercase tracking-wide">
                                    Created By
                                </label>
                                <div className={cn(
                                    "w-full px-3 py-2 rounded-md text-sm",
                                    isDark
                                        ? "bg-gray-800/40 text-gray-100"
                                        : "bg-gray-50 text-gray-900"
                                )}>
                                    {connectionDetails.created_by_email}
                                </div>
                            </div>
                        )}

                        {/* Created At */}
                        <div className="space-y-1.5">
                            <label className="block text-[10px] font-medium text-gray-500 dark:text-gray-500 uppercase tracking-wide">
                                Created At
                            </label>
                            <div className={cn(
                                "w-full px-3 py-2 rounded-md text-sm",
                                isDark
                                    ? "bg-gray-800/40 text-gray-100"
                                    : "bg-gray-50 text-gray-900"
                            )}>
                                {formatDate(connectionDetails.created_at)}
                            </div>
                        </div>

                        {/* Modified By */}
                        {connectionDetails.modified_by_email && (
                            <div className="space-y-1.5">
                                <label className="block text-[10px] font-medium text-gray-500 dark:text-gray-500 uppercase tracking-wide">
                                    Modified By
                                </label>
                                <div className={cn(
                                    "w-full px-3 py-2 rounded-md text-sm",
                                    isDark
                                        ? "bg-gray-800/40 text-gray-100"
                                        : "bg-gray-50 text-gray-900"
                                )}>
                                    {connectionDetails.modified_by_email}
                                </div>
                            </div>
                        )}

                        {/* Modified At */}
                        <div className="space-y-1.5">
                            <label className="block text-[10px] font-medium text-gray-500 dark:text-gray-500 uppercase tracking-wide">
                                Modified At
                            </label>
                            <div className={cn(
                                "w-full px-3 py-2 rounded-md text-sm",
                                isDark
                                    ? "bg-gray-800/40 text-gray-100"
                                    : "bg-gray-50 text-gray-900"
                            )}>
                                {formatDate(connectionDetails.modified_at)}
                            </div>
                        </div>
                    </div>
                </div>
            </div>

            {/* Bottom actions - minimal and clean */}
            <div className={cn(
                "px-6 py-4 border-t",
                isDark ? "border-gray-800/50" : "border-gray-100"
            )}>
                <button
                    onClick={onCancel}
                    className={cn(
                        "w-full py-2 px-4 rounded-lg text-sm font-medium transition-all duration-150",
                        isDark
                            ? "bg-gray-800 hover:bg-gray-700 text-gray-100"
                            : "bg-gray-100 hover:bg-gray-200 text-gray-700"
                    )}
                >
                    Done
                </button>
            </div>

            {/* Delete Connection Dialog */}
            {DeleteConnectionDialogComponent}
        </div>
    );
};

export default AuthProviderDetailView;
