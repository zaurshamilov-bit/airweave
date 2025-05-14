import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { toast } from 'sonner';
import ReactDOM from 'react-dom';

import FlowDialog from './FlowDialog';
import {
    CreateCollectionView,
    SourceConfigView,
    SourceSelectorView,
} from './views';
import { apiClient } from '@/lib/api';
import { ConnectToSourceFlow, useConnectToSourceFlow } from '@/lib/ConnectToSourceFlow';

// Entry points to the flow
export type ConnectFlowMode =
    | 'source-selector' // Start with source selection
    | 'create-collection' // Start with collection creation
    | 'add-source'; // Start with adding a source to existing collection

interface ConnectFlowProps {
    isOpen: boolean;
    onOpenChange: (open: boolean) => void;
    mode?: ConnectFlowMode;
    sourceId?: string; // Optional source ID to preselect
    sourceName?: string; // Optional source name to preselect
    sourceShortName?: string; // Optional source short name to preselect
    collectionId?: string; // Optional collection ID if adding to existing collection
    collectionName?: string; // Optional collection name if adding to existing collection
    onComplete?: (result: any) => void; // Called when flow completes successfully
}

export const ConnectFlow: React.FC<ConnectFlowProps> = ({
    isOpen,
    onOpenChange,
    mode = 'source-selector',
    sourceId,
    sourceName,
    sourceShortName,
    collectionId,
    collectionName,
    onComplete,
}) => {
    const navigate = useNavigate();
    const [currentView, setCurrentView] = useState('createCollection');
    const [viewData, setViewData] = useState({});
    const { initiateConnection, renderConfigDialog } = useConnectToSourceFlow();

    // Add a flag to track if we're bypassing the source config view
    const [isBypassingSourceConfig, setIsBypassingSourceConfig] = useState(false);

    // Function to reset all state to initial values
    const resetAllState = () => {
        console.log("🧹 [ConnectFlow] Resetting all state");

        // Determine the correct initial view based on mode
        let initialView = 'createCollection';
        if (mode === 'source-selector') {
            initialView = 'sourceSelector';
        } else if (mode === 'add-source') {
            initialView = 'sourceSelector';
        }

        // Reset state
        setCurrentView(initialView);
        setViewData({
            sourceName,
            sourceShortName,
            sourceId
        });
        setIsBypassingSourceConfig(false);
    };

    // Custom onOpenChange handler that resets state when closing
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
            // Reset all state when opening dialog
            resetAllState();
        }
    }, [isOpen, sourceId, sourceName, sourceShortName, mode]);

    useEffect(() => {
        console.log("🔄 [ConnectFlow] Initial view:", currentView);
        console.log("🔄 [ConnectFlow] Mode:", mode);
    }, [currentView, mode]);

    // NEW: Monitor view changes specifically from createCollection to sourceConfig
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

                    const response = await apiClient.get(`/sources/detail/${sourceShortName}`);
                    if (response.ok) {
                        const details = await response.json();

                        // Get collectionDetails from viewData
                        const collectionDetails = viewData["sourceConfig"]?.collectionDetails;

                        if (!collectionDetails) {
                            console.log("⚠️ [ConnectFlow] Missing collection details, cannot bypass");
                            return;
                        }

                        // Check if source has config fields
                        const hasConfigFields = details?.auth_fields?.fields &&
                            details.auth_fields.fields.length > 0;

                        console.log("⚠️ [ConnectFlow] Source details:", details);
                        console.log("⚠️ [ConnectFlow] Has config fields:", hasConfigFields);
                        console.log("⚠️ [ConnectFlow] Auth type:", details?.auth_type);

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
                            initiateConnection(
                                sourceShortName,
                                sourceName,
                                collectionDetails,
                                details, // Pass the source details we already fetched
                                onCompleteWrapper
                            );
                        }
                    }
                } catch (error) {
                    console.error("Error checking source config:", error);
                }
            };

            checkSourceConfig();
        }
    }, [currentView, isBypassingSourceConfig, sourceShortName, sourceName, viewData, onOpenChange, initiateConnection, onComplete]);

    const handleCreateCollectionNext = async (data) => {
        console.log("🔍 [ConnectFlow] handleCreateCollectionNext called with data:", data);
        const collectionDetails = data.data.collectionDetails;

        // Check if source needs config
        try {
            const response = await apiClient.get(`/sources/detail/${sourceShortName}`);
            if (response.ok) {
                const details = await response.json();

                // Check if source has config fields
                const hasConfigFields = details?.auth_fields?.fields &&
                    details.auth_fields.fields.length > 0;

                console.log("⚠️ [ConnectFlow] Source details:", details);
                console.log("⚠️ [ConnectFlow] Has config fields:", hasConfigFields);
                console.log("⚠️ [ConnectFlow] Auth type:", details?.auth_type);

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
                    initiateConnection(
                        sourceShortName,
                        sourceName,
                        collectionDetails,
                        details, // Pass the source details we already fetched
                        onCompleteWrapper
                    );
                    return;
                }
            }
        } catch (error) {
            console.error("Error checking source config:", error);
        }

        // If we need config or check failed, proceed to source config view
        setCurrentView("sourceConfig");
        setViewData({ ...viewData, sourceConfig: data.data });
    };

    // Define all possible views
    const views = {
        sourceSelector: SourceSelectorView,
        createCollection: CreateCollectionView,
        sourceConfig: SourceConfigView,
    };

    // Handle completion of the flow
    const handleComplete = (result: any) => {
        console.log('Flow completed with result:', result);

        // Handle different completion scenarios
        if (result?.oauthRedirect && result?.authUrl) {
            // OAuth redirect case
            window.location.href = result.authUrl;
            return;
        }

        if (result?.collectionId) {
            // Successfully created collection and/or source connection
            toast.success('Connection created successfully');

            // Navigate to collection detail page
            navigate(`/collections/${result.collectionId}?connected=success`);
        }

        // Call the onComplete callback
        if (onComplete) {
            onComplete(result);
        }
    };

    // Don't render until we have the initial view set up
    if (!currentView) return null;

    // NEW: Custom transition handler for FlowDialog
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

        // Default behavior for other transitions
        return data;
    };

    return (
        <>
            <FlowDialog
                isOpen={isOpen}
                onOpenChange={handleOpenChange}
                initialView={currentView}
                views={views}
                initialData={viewData}
                onComplete={handleComplete}
                // Override the onNext prop to intercept transitions
                onNext={handleViewTransition}
                // Disable animations completely to prevent flashing previous views
                disableAnimations={true}
            />
            {/* Render config dialog from ConnectToSourceFlow if needed */}
            {renderConfigDialog()}
        </>
    );
};

export default ConnectFlow;
