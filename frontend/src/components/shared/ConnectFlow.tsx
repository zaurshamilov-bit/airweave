/**
 * ConnectFlow - UI orchestration layer for source connection flow.
 * Manages which views to display and transitions between them.
 */

import { useState, useEffect, useRef } from "react";
import { apiClient } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Copy, Eye, Key, Plus, ExternalLink, FileText, Github } from "lucide-react";
import { useNavigate, Link, useLocation, useSearchParams } from "react-router-dom";
import { toast } from "sonner";
import {
    CollectionCard,
    SourceButton,
    ApiKeyCard,
    ExampleProjectCard,
} from "@/components/dashboard";
import {
    CreateCollectionView,
    SourceConfigView,
    SourceSelectorView,
} from './views';
import ConnectionErrorView from './views/ConnectionErrorView';
import FlowDialog from './FlowDialog';
import { cn } from "@/lib/utils";
import { redirectWithError } from "@/lib/error-utils";
import { useConnectToSourceFlow } from "@/lib/ConnectToSourceFlow";

/**
 * Defines the entry point modes for the connect flow
 */
export type ConnectFlowMode =
    | 'source-selector' // Start with source selection (user chooses a source first)
    | 'create-collection' // Start with collection creation (source is pre-selected)
    | 'add-source' // Start with adding a source to existing collection (collection already exists)
    | 'source-first-collection' // Start with source selection, then proceed to collection creation
    | 'error-view'; // Start with error view (when redirected after an error)

/**
 * Props for the ConnectFlow component
 */
interface ConnectFlowProps {
    /** Controls if the dialog is visible */
    isOpen: boolean;
    /** Callback when dialog open state changes */
    onOpenChange: (open: boolean) => void;
    /** Entry point mode - determines initial view and flow sequence */
    mode?: ConnectFlowMode;
    /** Optional source ID if pre-selected (e.g. from dashboard) */
    sourceId?: string;
    /** Optional source name if pre-selected */
    sourceName?: string;
    /** Optional source short_name if pre-selected */
    sourceShortName?: string;
    /** Optional collection ID when adding to existing collection */
    collectionId?: string;
    /** Optional collection name when adding to existing collection */
    collectionName?: string;
    /** Optional error data to show in ConnectionErrorView */
    errorData?: {
        serviceName?: string;
        errorMessage?: string;
        errorDetails?: string;
    };
    /** Callback when flow completes successfully */
    onComplete?: (result: any) => void;
}

/**
 * ConnectFlow - Manages the UI flow for connecting data sources to collections
 *
 * Key separation of concerns:
 * - ConnectFlow (this component): UI transitions and data collection
 * - ConnectToSourceFlow: All API interactions and connection logic
 */
export const ConnectFlow: React.FC<ConnectFlowProps> = ({
    isOpen,
    onOpenChange,
    mode = 'source-selector',
    sourceId,
    sourceName,
    sourceShortName,
    collectionId,
    collectionName,
    errorData,
    onComplete,
}) => {
    const navigate = useNavigate();
    /** Current view being displayed in the dialog */
    const [currentView, setCurrentView] = useState('createCollection');
    /** Data for all views, keyed by view name */
    const [viewData, setViewData] = useState({});
    /** Hook that provides API methods for initiating connections */
    const { handleConnection } = useConnectToSourceFlow();

    /** Flag to track if we're bypassing the source config view */
    const [isBypassingSourceConfig, setIsBypassingSourceConfig] = useState(false);
    /** Cache for source details to prevent duplicate API calls */
    const [cachedSourceDetails, setCachedSourceDetails] = useState<any>(null);

    /** Error state for connection errors */
    const [connectionError, setConnectionError] = useState<{
        serviceName?: string;
        errorMessage?: string;
        errorDetails?: string;
        retryAction?: () => void;
    } | null>(null);

    /**
     * Resets all state to initial values
     * Called when dialog opens or closes
     */
    const resetAllState = () => {
        let initialView = 'createCollection';
        if (mode === 'source-selector' || mode === 'add-source' || mode === 'source-first-collection') {
            initialView = 'sourceSelector';
        } else if (mode === 'error-view') {
            initialView = 'connectionError';
        }

        setCurrentView(initialView);
        setViewData({
            sourceName,
            sourceShortName,
            sourceId,
            collectionId,
            collectionName,
            isNewCollection: mode === 'source-first-collection'
        });
        setIsBypassingSourceConfig(false);
        setCachedSourceDetails(null);

        if (mode === 'error-view' && errorData) {
            setConnectionError(errorData);
        } else {
            setConnectionError(null);
        }
    };

    /**
     * Custom handler for dialog open state changes
     * Ensures proper cleanup when dialog closes
     */
    const handleOpenChange = (open: boolean) => {
        if (!open) {
            // State will reset when isOpen becomes false
        }
        onOpenChange(open);
    };

    // Reset state when dialog closes completely
    useEffect(() => {
        if (!isOpen) {
            resetAllState();
        }
    }, [isOpen]);

    // Reset view when dialog opens
    useEffect(() => {
        if (isOpen) {
            resetAllState();
        }
    }, [isOpen, sourceId, sourceName, sourceShortName, mode, errorData]);

    /**
     * Error handler for API failures
     * Redirects to dashboard with error parameters stored in localStorage
     */
    const handleConnectionError = (error: Error, serviceName: string = sourceShortName || "the service", retryAction?: () => void) => {
        onOpenChange(false);
        redirectWithError(navigate, error, serviceName);
    };

    /**
     * Helper to create config view data from source and collection details
     */
    const createSourceConfigData = (sourceData, collectionDetails) => ({
        collectionDetails,
        sourceId: sourceData.sourceId,
        sourceName: sourceData.sourceName,
        sourceShortName: sourceData.sourceShortName,
        sourceDetails: cachedSourceDetails
    });

    /**
     * Helper to initiate direct connection for sources that don't need configuration
     */
    const initiateDirectConnection = (
        targetSourceShortName: string,
        connectionDisplayName: string,
        collectionDetails: any,
        details: any,
        retryAction?: () => void
    ) => {
        console.log("⏩ [ConnectFlow] Bypassing SourceConfigView for", targetSourceShortName, "- no config fields needed");
        setIsBypassingSourceConfig(true);
        onOpenChange(false);

        // Connect directly using the unified service method
        handleConnection(
            targetSourceShortName,
            connectionDisplayName,
            collectionDetails,
            details,
            undefined, // No config needed
            mode !== 'add-source', // Pass isNewCollection based on mode
            (result) => {
                if (onComplete) {
                    onComplete({ collectionId: collectionDetails.readable_id });
                }
            },
            (url, details) => {
                // Redirect callback for OAuth
                window.location.href = url;
            },
            (error, source) => {
                // Error callback
                setConnectionError({
                    serviceName: connectionDisplayName || targetSourceShortName,
                    errorMessage: typeof error === 'object' && error instanceof Error ? error.message : "Connection failed",
                    errorDetails: typeof error === 'object' && error instanceof Error ? error.stack : JSON.stringify(error),
                    retryAction: retryAction || (() => checkAndHandleSourceConfig(collectionDetails))
                });
                setCurrentView("connectionError");
                onOpenChange(true);
            }
        );
    };

    /**
     * Checks if a source needs configuration and handles accordingly
     * @param collectionDetails - Details of the collection
     * @param retryAction - Optional retry action if the check fails
     * @param overrideSourceInfo - Optional object containing sourceShortName and sourceName to use instead of extracting from viewData
     */
    const checkAndHandleSourceConfig = async (
        collectionDetails: any,
        retryAction?: () => void,
        overrideSourceInfo?: { sourceShortName: string; sourceName?: string }
    ) => {
        try {
            // Get the correct sourceShortName, ensuring it's not undefined
            // If overrideSourceInfo is provided, use that first
            const targetSourceShortName = overrideSourceInfo?.sourceShortName ||
                viewData["sourceConfig"]?.sourceShortName ||
                (viewData as any).sourceShortName ||
                sourceShortName;

            // Similarly for sourceName
            const targetSourceName = overrideSourceInfo?.sourceName ||
                sourceName ||
                viewData["sourceConfig"]?.sourceName ||
                (viewData as any).sourceName;

            if (!targetSourceShortName) {
                console.error("❌ [ConnectFlow] Missing sourceShortName when checking source config", {
                    viewDataSourceShortName: (viewData as any).sourceShortName,
                    sourceConfigShortName: viewData["sourceConfig"]?.sourceShortName,
                    propsSourceShortName: sourceShortName,
                    override: overrideSourceInfo
                });
                handleConnectionError(
                    new Error("Missing source information. Please try again."),
                    "the service",
                    retryAction
                );
                return false;
            }

            console.log("🔍 [ConnectFlow] Checking source config for:", targetSourceShortName);

            // Get source details
            let details = cachedSourceDetails;
            if (!details) {
                const response = await apiClient.get(`/sources/detail/${targetSourceShortName}`);
                if (response.ok) {
                    details = await response.json();
                    setCachedSourceDetails(details);
                } else {
                    handleConnectionError(
                        new Error(`Failed to fetch source details: ${await response.text()}`),
                        targetSourceShortName,
                        retryAction
                    );
                    return false;
                }
            }

            // If this is an OAuth source and doesn't need configuration, skip the config view
            const isOAuthSource = details?.auth_type && details.auth_type.startsWith("oauth2");

            // Check if source has config fields
            const hasConfigFields = details?.auth_fields?.fields &&
                details.auth_fields.fields.length > 0;

            console.log("🔍 [ConnectFlow] Source details check:", {
                isOAuthSource,
                hasConfigFields,
                authType: details?.auth_type,
                fieldsCount: details?.auth_fields?.fields?.length || 0
            });

            // Fix: Only bypass SourceConfigView for sources without config fields
            // This ensures OAuth sources WITH config fields still show the config screen
            if (!hasConfigFields) {
                // Use helper function to initiate direct connection
                initiateDirectConnection(
                    targetSourceShortName,
                    targetSourceName || details?.name || "My Connection",
                    collectionDetails,
                    details,
                    retryAction
                );
                return false; // Indicate that we're bypassing SourceConfigView
            }

            console.log("👉 [ConnectFlow] Source needs configuration:", targetSourceShortName);
            return true; // Config is needed
        } catch (error) {
            console.error("❌ [ConnectFlow] Error checking source config:", error);
            handleConnectionError(error instanceof Error ? error : new Error(String(error)), sourceShortName);
            return false;
        }
    };

    /**
     * Common logic for transitioning to source config view
     */
    const transitionToSourceConfig = (sourceData, collectionDetails) => {
        return checkAndHandleSourceConfig(
            collectionDetails,
            () => handleViewTransition({
                view: 'sourceConfig',
                data: {
                    ...sourceData,
                    collectionDetails
                }
            }),
            sourceData
        )
            .then(needsConfig => {
                if (needsConfig) {
                    // Only proceed to sourceConfig if needed
                    setCurrentView("sourceConfig");

                    const sourceConfigData = createSourceConfigData(sourceData, collectionDetails);
                    setViewData({
                        ...viewData,
                        sourceConfig: sourceConfigData
                    });
                }
                // If no config needed, checkAndHandleSourceConfig already handled it
            });
    };

    /**
     * Handles view transitions with special logic
     */
    const handleViewTransition = (data) => {
        // Special handling for createCollection -> sourceConfig transition
        if (currentView === "createCollection" &&
            (data === "sourceConfig" || data?.view === "sourceConfig")) {
            const collectionDetails = data.data?.collectionDetails;

            // Extract source info directly from transition data
            const sourceDataForCheck = {
                sourceShortName: data.data?.sourceShortName,
                sourceName: data.data?.sourceName,
                sourceId: data.data?.sourceId
            };

            // Use common transition function
            transitionToSourceConfig(sourceDataForCheck, collectionDetails);
            return null; // Prevent default transition
        }

        // Handle sourceSelector -> sourceConfig transition
        if (currentView === "sourceSelector" && data?.view === "sourceConfig") {
            // If adding to existing collection, wrap collectionId in collectionDetails
            if (data.data?.collectionId) {
                data.data.collectionDetails = {
                    name: collectionName,
                    readable_id: data.data.collectionId
                };
            }

            // Extract source and collection details from the transition data
            const collectionDetails = data.data?.collectionDetails;
            const sourceDataForCheck = {
                sourceShortName: data.data?.sourceShortName,
                sourceName: data.data?.sourceName,
                sourceId: data.data?.sourceId
            };

            if (collectionDetails && sourceDataForCheck.sourceShortName) {
                console.log("🔍 [ConnectFlow] Checking source config needs in sourceSelector->sourceConfig transition", {
                    sourceShortName: sourceDataForCheck.sourceShortName,
                    collectionDetails
                });

                // Use common transition function
                transitionToSourceConfig(sourceDataForCheck, collectionDetails);
                return null; // Prevent default transition
            }
        }

        return data;
    };

    /**
     * Handles completion from any view
     */
    const handleComplete = (result: any) => {
        // Handle error result
        if (result?.error) {
            onOpenChange(false);
            const errorObj = new Error(result.errorMessage || "Connection failed");
            if (result.errorDetails) {
                Object.defineProperty(errorObj, 'stack', { value: result.errorDetails });
            }
            redirectWithError(navigate, errorObj, result.serviceName || sourceName || sourceShortName);
            return;
        }

        // Handle direct OAuth redirect
        if (result?.oauthRedirect && result?.authUrl) {
            console.log("🔄 [ConnectFlow] Processing OAuth redirect to:", result.authUrl);

            // Close the dialog before redirecting
            onOpenChange(false);

            // Use a slight delay to ensure dialog is fully closed before redirect
            window.location.href = result.authUrl;

            return;
        }

        // Handle source connection config result
        if (result?.sourceConnection) {
            onOpenChange(false);

            const sourceConfig = {
                name: result.sourceConnection.name,
                auth_fields: result.sourceConnection.auth_fields || {}
            };

            // Get collection ID from various possible sources
            const collectionId = result.collectionId ||
                (viewData["sourceConfig"] as any)?.collectionDetails?.readable_id ||
                (viewData as any)?.collectionDetails?.readable_id;

            if (!collectionId) {
                toast.error("Failed to identify collection");
                return;
            }

            // Get sourceShortName from multiple possible places (including the new one from SourceConfigView)
            const targetSourceShortName = result.sourceShortName ||
                viewData["sourceConfig"]?.sourceShortName ||
                (viewData as any).sourceShortName;

            if (!targetSourceShortName) {
                console.error("❌ [ConnectFlow] Missing sourceShortName in handleComplete");
                toast.error("Missing source information. Please try again.");
                return;
            }

            console.log("🔄 [ConnectFlow] Creating connection for source:", targetSourceShortName);

            // Use the unified connection method
            handleConnection(
                targetSourceShortName,
                sourceName || "My Connection",
                { name: collectionName || "My Collection", readable_id: collectionId },
                cachedSourceDetails,
                sourceConfig,
                mode !== 'add-source',
                (result) => {
                    // Success callback
                    if (onComplete) {
                        onComplete({ collectionId });
                    }
                    toast.success('Connection created successfully');
                    navigate(`/collections/${collectionId}?connected=success`);
                },
                (url, details) => {
                    // Redirect callback
                    window.location.href = url;
                },
                (error, source) => {
                    // Error callback
                    handleConnectionError(
                        error instanceof Error ? error : new Error(String(error)),
                        sourceName || targetSourceShortName
                    );
                }
            );

            return;
        }

        // Handle direct connection success
        if (result?.collectionId) {
            toast.success('Connection created successfully');
            navigate(`/collections/${result.collectionId}?connected=success`);
        }

        onOpenChange(false);

        if (onComplete) {
            onComplete(result);
        }
    };

    // View components mapping
    const views = {
        sourceSelector: SourceSelectorView,
        createCollection: CreateCollectionView,
        sourceConfig: SourceConfigView,
        connectionError: ConnectionErrorView,
    };

    return (
        <FlowDialog
            isOpen={isOpen}
            onOpenChange={handleOpenChange}
            initialView={currentView}
            views={views}
            initialData={
                (connectionError && currentView === "connectionError") ||
                    (mode === 'error-view' && errorData) ?
                    (connectionError || errorData) :
                    viewData
            }
            onComplete={handleComplete}
            onNext={handleViewTransition}
        />
    );
};

export default ConnectFlow;
