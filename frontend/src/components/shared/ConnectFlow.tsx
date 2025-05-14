/**
 * ConnectFlow.tsx
 *
 * This is the orchestration layer for the source connection flow. It handles the UI flow
 * for connecting data sources to collections, managing which views to display and when.
 *
 * The component acts as a "flow controller" that:
 * 1. Manages which dialog views to show based on user actions
 * 2. Determines if source configuration is needed
 * 3. Handles bypassing unnecessary steps
 * 4. Collects necessary data before handing off to the API layer
 *
 * Flow overview:
 * - Dashboard → Click source → ConnectFlow (create-collection mode) → CreateCollectionView
 * - Collection detail → Add source → ConnectFlow (add-source mode) → SourceSelectorView → CreateCollectionView
 * - After collection creation → Check if source needs config → Show SourceConfigView or bypass to API
 * - Error handling → Show ConnectionErrorView with error details
 *
 * =====================================================================
 * IMPORTANT DATABASE OPERATION NOTE
 *
 * ConnectFlow DOES NOT directly create collections or source connections
 * in the database. It only collects the necessary information and then
 * passes it to ConnectToSourceFlow which performs the actual API calls.
 *
 * The actual database operations happen in:
 * 1. ConnectToSourceFlow.tsx - For direct creation paths
 * 2. SourceConfigView.tsx - When config is collected via form
 * 3. AuthCallback.tsx - For OAuth flow completions
 * =====================================================================
 */

import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { toast } from 'sonner';

import FlowDialog from './FlowDialog';
import {
    CreateCollectionView,
    SourceConfigView,
    SourceSelectorView,
} from './views';
import ConnectionErrorView from './views/ConnectionErrorView';
import { apiClient } from '@/lib/api';
import { useConnectToSourceFlow } from '@/lib/ConnectToSourceFlow';
import { redirectWithError } from '@/lib/error-utils';

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
 * ConnectFlow Component
 *
 * Manages the flow of connecting data sources to collections through a series
 * of dialog views. Determines source configuration requirements and orchestrates
 * the connection process.
 *
 * Flow paths based on mode:
 *
 * 1. 'source-selector' - Default flow starting with source selection
 *    SourceSelectorView → CreateCollectionView → SourceConfigView (if needed) → API
 *
 * 2. 'create-collection' - Flow starting with collection creation (when source is pre-selected)
 *    CreateCollectionView → SourceConfigView (if needed) → API
 *
 * 3. 'add-source' - Flow for adding a source to an existing collection
 *    SourceSelectorView → SourceConfigView (if needed) → API
 *    (Skips CreateCollectionView and reuses existing collection)
 *
 * 4. 'source-first-collection' - Flow for creating a collection starting with source selection
 *    SourceSelectorView → CreateCollectionView → SourceConfigView (if needed) → API
 *    (Used by the "+ Create collection" button in the sidebar)
 *
 * 5. 'error-view' - Flow starting with error view after redirection
 *    ConnectionErrorView → retry or cancel
 *
 * Special behavior:
 * - For OAuth sources, flow may redirect to provider and continue in AuthCallback
 * - Sources without config fields bypass SourceConfigView
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
    const { initiateConnection, performOAuthRedirect } = useConnectToSourceFlow();

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
        console.log("🧹 [ConnectFlow] Resetting all state with mode:", mode);

        // Determine the correct initial view based on mode
        let initialView = 'createCollection';
        if (mode === 'source-selector' || mode === 'add-source' || mode === 'source-first-collection') {
            initialView = 'sourceSelector';
        } else if (mode === 'error-view') {
            console.log("🔔 [ConnectFlow] Initializing in error-view mode with:", errorData);
            initialView = 'connectionError';
        }

        // Reset state
        setCurrentView(initialView);
        setViewData({
            sourceName,
            sourceShortName,
            sourceId,
            collectionId,
            collectionName,
            isNewCollection: mode === 'source-first-collection' // Flag to indicate we're creating a new collection
        });
        setIsBypassingSourceConfig(false);
        setCachedSourceDetails(null);

        // If in error view mode, set the error state
        if (mode === 'error-view' && errorData) {
            console.log("🔔 [ConnectFlow] Setting connection error state for error-view mode");
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
            console.log("🚪 [ConnectFlow] Dialog closing, will reset state");
            // We'll reset state in the useEffect below when isOpen becomes false
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
            console.log("🔔 [ConnectFlow] Dialog opened with mode:", mode, "errorData:", errorData);
            // Reset all state when opening dialog
            resetAllState();
        }
    }, [isOpen, sourceId, sourceName, sourceShortName, mode, errorData]);

    useEffect(() => {
        console.log("🔄 [ConnectFlow] Initial view:", currentView);
        console.log("🔄 [ConnectFlow] Mode:", mode);
    }, [currentView, mode]);

    /**
     * Error handler for API failures
     * Redirects to dashboard with error parameters stored in localStorage
     */
    const handleConnectionError = (error: Error, serviceName: string = sourceShortName || "the service", retryAction?: () => void) => {
        console.error("❌ [ConnectFlow] Connection error:", error);

        // Close the dialog
        onOpenChange(false);

        // Use the utility function to redirect with error
        redirectWithError(navigate, error, serviceName);
    };

    /**
     * Special handling for when view changes to sourceConfig
     *
     * This effect:
     * 1. Checks if the source requires configuration
     * 2. If not, bypasses the config view and initiates connection directly
     * 3. If yes, allows the normal flow to continue
     */
    useEffect(() => {
        console.log("🔄 [ConnectFlow] Current view changed to:", currentView);

        // Check if we need to run special handling when transitioning to sourceConfig
        if (currentView === "sourceConfig" && !isBypassingSourceConfig) {
            console.log("🔄 [ConnectFlow] Transition to sourceConfig detected, checking if we should bypass");

            // Run the check asynchronously to not block the UI
            const checkSourceConfig = async () => {
                try {
                    if (!sourceShortName) {
                        console.log("⚠️ [ConnectFlow] Missing sourceShortName, cannot check source config");
                        return;
                    }

                    // Use cached source details if available
                    let details = cachedSourceDetails;
                    if (!details) {
                        const response = await apiClient.get(`/sources/detail/${sourceShortName}`);
                        if (response.ok) {
                            details = await response.json();
                            // Cache the source details for reuse
                            setCachedSourceDetails(details);
                        } else {
                            console.error("❌ [ConnectFlow] Failed to fetch source details");
                            handleConnectionError(new Error(`Failed to fetch source details: ${await response.text()}`), sourceShortName);
                            return;
                        }
                    }

                    // Get collectionDetails from viewData
                    const collectionDetails = viewData["sourceConfig"]?.collectionDetails;

                    if (!collectionDetails) {
                        console.log("⚠️ [ConnectFlow] Missing collection details, cannot bypass");
                        return;
                    }

                    // Check if source has config fields
                    const hasConfigFields = details?.auth_fields?.fields &&
                        details.auth_fields.fields.length > 0;

                    console.log("🔍 [ConnectFlow] Source details:", details);
                    console.log("🔍 [ConnectFlow] Has config fields:", hasConfigFields);
                    console.log("🔍 [ConnectFlow] Auth type:", details?.auth_type);

                    // If OAuth with no config fields, bypass SourceConfigView
                    if (!hasConfigFields) {
                        console.log("🚀 [ConnectFlow] Source has no config fields, bypassing SourceConfigView");

                        // Set bypassing flag to prevent loops
                        setIsBypassingSourceConfig(true);

                        // Close the dialog
                        onOpenChange(false);

                        // Create a wrapper for onComplete that matches the expected signature
                        const onCompleteWrapper = () => {
                            if (onComplete) {
                                onComplete({ collectionId: collectionDetails.readable_id });
                            }
                        };

                        // Start connection flow directly
                        try {
                            const result = await initiateConnection(
                                sourceShortName,
                                sourceName || "My Connection",
                                collectionDetails,
                                details, // Pass the source details we already fetched
                                onCompleteWrapper
                            );

                            // Check if this is an OAuth redirect result
                            if (result && result.oauthRedirect && result.authUrl) {
                                console.log("🔀 [ConnectFlow] Redirecting to OAuth provider:", result.authUrl);
                                // Use direct browser redirect
                                window.location.href = result.authUrl;
                                return;
                            }
                        } catch (error) {
                            console.error("❌ [ConnectFlow] Error during connection initiation:", error);
                            // Re-open the dialog with error view
                            setConnectionError({
                                serviceName: sourceName || sourceShortName,
                                errorMessage: error instanceof Error ? error.message : "Connection failed",
                                errorDetails: error instanceof Error ? error.stack : JSON.stringify(error),
                                retryAction: () => checkSourceConfig()
                            });
                            setCurrentView("connectionError");
                            onOpenChange(true);
                        }
                    }
                } catch (error) {
                    console.error("❌ [ConnectFlow] Error checking source config:", error);
                    handleConnectionError(error instanceof Error ? error : new Error(String(error)), sourceShortName);
                }
            };

            checkSourceConfig();
        }
    }, [currentView, isBypassingSourceConfig, sourceShortName, sourceName, viewData, onOpenChange, initiateConnection, onComplete, cachedSourceDetails]);

    /**
     * Handler for when the CreateCollectionView completes
     *
     * This function:
     * 1. Checks if the selected source requires configuration
     * 2. If not, bypasses configuration and initiates connection directly
     * 3. If yes, transitions to the SourceConfigView
     */
    const handleCreateCollectionNext = async (data) => {
        console.log("🔍 [ConnectFlow] handleCreateCollectionNext called with data:", data);
        const collectionDetails = data.data.collectionDetails;

        // Check if source needs config
        try {
            // Use cached source details if available
            let details = cachedSourceDetails;
            if (!details) {
                const response = await apiClient.get(`/sources/detail/${sourceShortName}`);
                if (response.ok) {
                    details = await response.json();
                    // Cache the source details
                    setCachedSourceDetails(details);
                } else {
                    console.error("❌ [ConnectFlow] Failed to fetch source details");
                    handleConnectionError(new Error(`Failed to fetch source details: ${await response.text()}`), sourceShortName,
                        () => handleCreateCollectionNext(data));
                    return;
                }
            }

            // Check if source has config fields
            const hasConfigFields = details?.auth_fields?.fields &&
                details.auth_fields.fields.length > 0;

            console.log("🔍 [ConnectFlow] Source details:", details);
            console.log("🔍 [ConnectFlow] Has config fields:", hasConfigFields);
            console.log("🔍 [ConnectFlow] Auth type:", details?.auth_type);

            // If OAuth with no config fields, bypass SourceConfigView
            if (!hasConfigFields) {
                console.log("🚀 [ConnectFlow] Source has no config fields, bypassing SourceConfigView");

                // Set bypassing flag
                setIsBypassingSourceConfig(true);

                // Close the dialog
                onOpenChange(false);

                // Create a wrapper for onComplete that matches the expected signature
                const onCompleteWrapper = () => {
                    if (onComplete) {
                        onComplete({ collectionId: collectionDetails.readable_id });
                    }
                };

                // Start connection flow directly
                try {
                    const result = await initiateConnection(
                        sourceShortName,
                        sourceName || "My Connection",
                        collectionDetails,
                        details, // Pass the source details we already fetched
                        onCompleteWrapper
                    );

                    // Check if this is an OAuth flow that needs redirect
                    if (result && result.oauthRedirect && result.authUrl) {
                        console.log("🔀 [ConnectFlow] Handling OAuth redirect from initiateConnection");
                        // Redirect to the OAuth provider
                        window.location.href = result.authUrl;
                        return;
                    }
                } catch (error) {
                    console.error("❌ [ConnectFlow] Error during connection initiation:", error);
                    // Re-open the dialog with error view
                    handleConnectionError(
                        error instanceof Error ? error : new Error(String(error)),
                        sourceName || sourceShortName,
                        () => handleCreateCollectionNext(data)
                    );
                }
                return;
            }
        } catch (error) {
            console.error("❌ [ConnectFlow] Error checking source config:", error);
            handleConnectionError(error instanceof Error ? error : new Error(String(error)), sourceShortName);
            return;
        }

        // If we need config or check failed, proceed to source config view
        setCurrentView("sourceConfig");
        setViewData({ ...viewData, sourceConfig: data.data });
    };

    /**
     * Map of view names to view components
     * These are the steps in the connection flow
     */
    const views = {
        sourceSelector: SourceSelectorView,
        createCollection: CreateCollectionView,
        sourceConfig: SourceConfigView,
        connectionError: ConnectionErrorView,
    };

    /**
     * Handler for flow completion
     *
     * Called when:
     * - A view calls onComplete (flow is done)
     * - User has finished all steps
     * - OAuth redirect is needed
     *
     * Routes to appropriate destination based on result.
     */
    const handleComplete = (result: any) => {
        console.log('Flow completed with result:', result);

        // Check if this is an error completion
        if (result?.error) {
            // Close the dialog
            onOpenChange(false);

            // Create an error object
            const errorObj = new Error(result.errorMessage || "Connection failed");

            // If error details are provided, add them to the error object
            if (result.errorDetails) {
                Object.defineProperty(errorObj, 'stack', {
                    value: result.errorDetails
                });
            }

            // Redirect to dashboard with error details
            redirectWithError(
                navigate,
                errorObj,
                result.serviceName || sourceName || sourceShortName
            );
            return;
        }

        // Handle different completion scenarios
        if (result?.oauthRedirect && result?.authUrl) {
            // OAuth redirect case - use direct browser redirection
            console.log("🔀 [ConnectFlow] Redirecting to OAuth provider:", result.authUrl);
            window.location.href = result.authUrl;
            return;
        }

        if (result?.sourceConnection) {
            // User completed SourceConfigView with source connection config
            console.log("🔄 [ConnectFlow] Flow completed with source config:", result);

            // Close the dialog
            onOpenChange(false);

            const sourceConfig = {
                name: result.sourceConnection.name,
                auth_fields: result.sourceConnection.auth_fields || {}
            };

            // Instead of navigation, pass control to ConnectToSourceFlow with the collected config
            const onCompleteWrapper = () => {
                if (onComplete) {
                    onComplete({ collectionId: result.collectionId });
                }
            };

            // Get cached source details
            const details = cachedSourceDetails;

            // Start the connection process with the collected config
            try {
                initiateConnection(
                    sourceShortName,
                    sourceName || "My Connection",
                    { name: collectionName || "My Collection", readable_id: result.collectionId },
                    details,
                    onCompleteWrapper,
                    sourceConfig
                ).then(result => {
                    // Handle OAuth redirect if needed
                    if (result && result.oauthRedirect && result.authUrl) {
                        console.log("🔀 [ConnectFlow] Redirecting to OAuth provider from source config completion");
                        window.location.href = result.authUrl;
                    }
                });
            } catch (error) {
                console.error("❌ [ConnectFlow] Error during connection initiation with config:", error);
                // Redirect to dashboard with error view
                handleConnectionError(
                    error instanceof Error ? error : new Error(String(error)),
                    sourceName || sourceShortName,
                    () => handleComplete(result)
                );
            }

            return;
        }

        if (result?.collectionId) {
            // Successfully created collection and/or source connection
            toast.success('Connection created successfully');

            // Navigate to collection detail page
            navigate(`/collections/${result.collectionId}?connected=success`);
        }

        // Close the dialog when successful
        onOpenChange(false);

        // Call the onComplete callback
        if (onComplete) {
            onComplete(result);
        }
    };

    /**
     * Custom transition handler for FlowDialog
     *
     * Intercepts transitions between views and applies custom logic
     * Particularly handles the transition from createCollection to sourceConfig
     */
    const handleViewTransition = (data) => {
        console.log("🔄 [ConnectFlow] handleViewTransition called with data:", data);

        // If transitioning from createCollection to sourceConfig, run our custom handler
        if (currentView === "createCollection" &&
            ((typeof data === "string" && data === "sourceConfig") ||
                (data?.view === "sourceConfig"))) {

            console.log("🔄 [ConnectFlow] Intercepting transition from createCollection to sourceConfig");
            handleCreateCollectionNext(data);
            return null; // Prevent default transition
        }

        // If transitioning from sourceSelector to sourceConfig, transform the data
        if (currentView === "sourceSelector" && data?.view === "sourceConfig") {
            console.log("🔄 [ConnectFlow] Transforming data from sourceSelector to sourceConfig");

            // If collectionId exists in data, wrap it in collectionDetails
            if (data.data && data.data.collectionId) {
                const collectionId = data.data.collectionId;
                console.log("🧩 [ConnectFlow] Found collectionId in source selector data:", collectionId);
                console.log("🧩 [ConnectFlow] This indicates we're adding to an EXISTING collection (not creating a new one)");

                data.data.collectionDetails = {
                    name: collectionName,
                    readable_id: collectionId
                };
                console.log("🔄 [ConnectFlow] Added collectionDetails with readable_id:", collectionId);
            } else {
                console.log("⚠️ [ConnectFlow] No collectionId found in data - creating a new collection");
            }
        }

        // Default behavior for other transitions
        return data;
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
            // Override the onNext prop to intercept transitions
            onNext={handleViewTransition}
        />
    );
};

export default ConnectFlow;
