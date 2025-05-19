import React, { useState, useEffect, useRef } from "react";
import { Dialog, DialogContent, DialogPortal, DialogOverlay } from "@/components/ui/dialog";
import { useTheme } from "@/lib/theme-provider";
import { cn } from "@/lib/utils";
import { CreateCollectionView } from "./views/CreateCollectionView";
import { SourceSelectorView } from "./views/SourceSelectorView";
import { ConfigureSourceView } from "./views/ConfigureSourceView";
import { useNavigate, useSearchParams } from "react-router-dom";
import { redirectWithError, getStoredErrorDetails, clearStoredErrorDetails, CONNECTION_ERROR_STORAGE_KEY } from "@/lib/error-utils";
import { ConnectionErrorView } from "./views/ConnectionErrorView";

// Flow types
export type DialogFlowMode =
    | "source-button"     // Dashboard SourceButton flow
    | "add-source"        // CollectionDetailView "+ add source" flow
    | "create-collection"; // DashboardLayout "+ create collection" flow

interface DialogFlowProps {
    isOpen: boolean;
    onOpenChange: (open: boolean) => void;
    mode: DialogFlowMode;
    sourceId?: string;
    sourceName?: string;
    sourceShortName?: string;
    collectionId?: string;
    collectionName?: string;
    onComplete?: (result: any) => void;
    dialogId?: string; // Add unique dialog ID prop
}

export const DialogFlow: React.FC<DialogFlowProps> = ({
    isOpen,
    onOpenChange,
    mode,
    sourceId,
    sourceName,
    sourceShortName,
    collectionId,
    collectionName,
    onComplete,
    dialogId = "default", // Default ID if none provided
}) => {
    const { resolvedTheme } = useTheme();
    const isDark = resolvedTheme === "dark";
    const [currentStep, setCurrentStep] = useState(0);
    const [viewData, setViewData] = useState<Record<string, any>>({});
    const navigate = useNavigate();
    const [searchParams] = useSearchParams();
    const [showErrorView, setShowErrorView] = useState(false);
    const [errorViewData, setErrorViewData] = useState<any>(null);
    const [hasBeenForced, setHasBeenForced] = useState(false);

    // Add a ref to track if we've already processed restore
    const hasProcessedRestoreRef = useRef(false);

    // Reset state when dialog opens or mode changes
    useEffect(() => {
        // DON'T reset viewData or currentStep if we're restoring dialog
        if (isOpen && !hasProcessedRestoreRef.current) {
            setCurrentStep(0);
            setViewData({
                sourceId,
                sourceName,
                sourceShortName,
                collectionId,
                collectionName,
                dialogId
            });
        }
    }, [isOpen, mode, sourceId, sourceName, sourceShortName, collectionId, collectionName, dialogId]);

    // Update the effect to force dialog open
    useEffect(() => {
        const restoreDialog = searchParams.get('restore_dialog') === 'true';
        const oauthError = searchParams.get('oauth_error') === 'true';
        const connectionError = searchParams.get('connected') === 'error';

        // Prevent processing the restore more than once
        if ((restoreDialog || oauthError) && !hasProcessedRestoreRef.current) {
            hasProcessedRestoreRef.current = true;

            // Clear the URL parameter immediately
            const newUrl = window.location.pathname;
            window.history.replaceState({}, '', newUrl);

            // Retrieve the saved dialog state
            const savedStateJson = sessionStorage.getItem('oauth_dialog_state');
            if (savedStateJson) {
                try {
                    const savedState = JSON.parse(savedStateJson);
                    console.log("🔄 Restoring dialog state:", savedState);
                    console.log("⚠️ Important values:", {
                        credentialId: savedState.credentialId,
                        isAuthenticated: savedState.isAuthenticated,
                        currentStep: savedState.currentStep,
                        dialogFlowStep: savedState.dialogFlowStep,
                        dialogId: savedState.dialogId
                    });

                    // Only restore this dialog if it matches the saved dialogId
                    if (savedState.dialogId && savedState.dialogId === dialogId) {
                        console.log(`🎯 Dialog ID match: ${dialogId}, restoring this dialog instance`);

                        // Set the necessary state to reopen the dialog
                        setCurrentStep(typeof savedState.dialogFlowStep === 'number' ? savedState.dialogFlowStep : 1);
                        setViewData({
                            sourceId: savedState.sourceDetails?.id,
                            sourceName: savedState.sourceDetails?.name,
                            sourceShortName: savedState.sourceShortName,
                            collectionId: savedState.collectionId,
                            collectionName: savedState.collectionName,
                            created_collection_id: savedState.created_collection_id,
                            created_collection_name: savedState.created_collection_name,

                            // The important part - pass ALL the state information
                            credentialId: savedState.credentialId,
                            isAuthenticated: savedState.isAuthenticated && !oauthError,
                            configureStep: savedState.configureStep || 'auth',
                            dialogFlowStep: savedState.dialogFlowStep,
                            dialogId: savedState.dialogId
                        });

                        // Force dialog open with a robust approach
                        setTimeout(() => {
                            console.log(`🚨 Forcing dialog open with dialogId: ${dialogId}`);
                            onOpenChange(true);

                            // Store in state that we've forced the dialog open
                            setHasBeenForced(true);

                            // Clean up stored dialog state immediately after opening
                            sessionStorage.removeItem('oauth_dialog_state');
                        }, 100);

                        // Clean up
                        sessionStorage.removeItem('oauth_dialog_state');
                    } else {
                        console.log(`⏭️ Dialog ID mismatch: saved=${savedState.dialogId}, current=${dialogId}, skipping restore`);
                    }

                    // Add near line 87 after parsing the savedState
                    console.log("📊 FULL SAVED STATE IN DIALOG FLOW:", JSON.stringify(savedState, null, 2));

                    // Add near line 105 after setting viewData
                    console.log("📊 FULL VIEW DATA AFTER RESTORE:", JSON.stringify(viewData, null, 2));
                } catch (error) {
                    console.error("❌ Error restoring dialog state:", error);
                }
            }
        } else if (connectionError) {
            // Check for errors stored via error-utils
            const errorDetails = getStoredErrorDetails();
            if (errorDetails) {
                console.log("🔔 Connection error detected:", errorDetails);

                // Set error view data
                setErrorViewData({
                    serviceName: errorDetails.serviceName,
                    sourceShortName: errorDetails.serviceName?.toLowerCase(),
                    errorMessage: errorDetails.errorMessage,
                    errorDetails: errorDetails.errorDetails
                });

                // Show error view and open dialog
                setShowErrorView(true);
                onOpenChange(true);

                // Clean up URL
                const newUrl = window.location.pathname;
                window.history.replaceState({}, '', newUrl);

                // Clear stored error
                clearStoredErrorDetails();
            }
        }
    }, [searchParams, onOpenChange, isOpen, dialogId]);

    // Add a direct effect on isOpen to log when it changes
    useEffect(() => {
        console.log(`🔍 Dialog isOpen changed for dialogId=${dialogId}: ${isOpen}`);

        // If dialog was open and is now closing (not due to OAuth transition)
        if (!isOpen && hasBeenForced) {
            // Call handleCancel to properly clean up state
            handleCancel();
        }
    }, [isOpen, dialogId, hasBeenForced]);

    // Define flow sequences based on mode
    const flowSequences = {
        "source-button": ["createCollection", "connectSource"],
        "add-source": ["sourceSelector", "connectSource"],
        "create-collection": ["sourceSelector", "createCollection", "connectSource"]
    };

    // Get current flow sequence
    const currentFlow = flowSequences[mode as keyof typeof flowSequences];
    if (!currentFlow) {
        throw new Error(`Invalid dialog flow mode: ${mode}. Expected one of: ${Object.keys(flowSequences).join(', ')}`);
    }
    const currentView = currentFlow[currentStep];

    // Handle next step
    const handleNext = (data?: any) => {

        if (data) {
            setViewData(prevData => {
                const newData = {
                    ...prevData,
                    ...data,
                    dialogId // Always maintain the dialogId
                };
                return newData;
            });
        }

        if (currentStep < currentFlow.length - 1) {
            setCurrentStep(prevStep => prevStep + 1);
        }
    };

    // Handle back step
    const handleBack = () => {
        if (currentStep > 0) {
            setCurrentStep(currentStep - 1);
        }
    };

    // Handle cancel
    const handleCancel = () => {
        console.log('🚪 Cancelling dialog with ID:', dialogId);

        // Check if we're in the middle of an OAuth flow
        const inOAuthProcess = sessionStorage.getItem('oauth_dialog_state') !== null;

        // Only clear credential data if we're not in the OAuth flow
        if (!inOAuthProcess) {
            // Force the dialog closed regardless of internal state
            onOpenChange(false);

            // Clear credential data to prevent auto-reopening
            setViewData(prevData => ({
                sourceId,
                sourceName,
                sourceShortName,
                collectionId,
                collectionName,
                dialogId,
                // Remove credential data to prevent reopening
                credentialId: undefined,
                isAuthenticated: false
            }));

            // Reset step regardless of whether dialog was forced
            setCurrentStep(0);
        } else {
            console.log('🔄 Skipping credential reset during OAuth flow');
        }
    };

    // Handle completion
    const handleComplete = (result: any) => {
        onOpenChange(false);
        if (onComplete) {
            onComplete(result);
        }
    };

    // Add error handling function that can be passed to views
    const handleError = (error: Error | string, sourceName?: string) => {
        console.error(`❌ [DialogFlow] Error with dialogId=${dialogId}:`, error);
        onOpenChange(false);
        redirectWithError(navigate, error, sourceName);
    };

    // Render current view based on flow step
    const renderView = () => {
        // Debug logging for render state
        console.log(`🎯 RENDER - Dialog ${dialogId} Current state:`, {
            currentStep,
            currentView,
            flowMode: mode,
            flowSequence: currentFlow
        });
        console.log(`🎯 RENDER - Dialog ${dialogId} ViewData before rendering:`, JSON.stringify(viewData, null, 2));

        // If we should show the error view, return that
        if (showErrorView) {
            console.log(`🎯 RENDERING: Error View for dialog ${dialogId}`);
            return (
                <ConnectionErrorView
                    onCancel={() => {
                        setShowErrorView(false);
                        onOpenChange(false);
                    }}
                    viewData={errorViewData || {
                        serviceName: viewData.sourceName,
                        sourceShortName: viewData.sourceShortName,
                        errorMessage: "Connection failed"
                    }}
                />
            );
        }

        // Regular view logic...
        const commonProps = {
            onNext: handleNext,
            onCancel: handleCancel,
            onComplete: handleComplete,
            viewData: {
                ...viewData,
                dialogId, // Always include dialogId in viewData
                dialogFlowStep: currentStep // Store current step for restoration
            } as any, // Use type assertion to resolve compatibility issues
            onError: handleError,
        };

        // Only add back button if not at first step
        if (currentStep > 0) {
            (commonProps as any).onBack = handleBack;
        }

        switch (currentView) {
            case "sourceSelector":
                console.log(`🎯 RENDERING: SourceSelectorView for dialog ${dialogId}`);
                return <SourceSelectorView {...commonProps} />;
            case "createCollection":
                console.log(`🎯 RENDERING: CreateCollectionView for dialog ${dialogId}`);
                return <CreateCollectionView {...commonProps} />;
            case "connectSource":
                console.log(`🎯 RENDERING: ConfigureSourceView for dialog ${dialogId}`);
                return <ConfigureSourceView {...commonProps} />;
            default:
                console.log(`🎯 RENDERING: Unknown View for dialog ${dialogId}`);
                return <div>Unknown view: {currentView}</div>;
        }
    };

    // Modify the useEffect that depends on viewData
    useEffect(() => {
        // Only open dialog when viewData has been populated with credential info
        // AND we haven't just closed it manually
        if (viewData.credentialId && !isOpen && hasProcessedRestoreRef.current) {
            console.log(`🔔 Opening dialog ${dialogId} with populated viewData:`, JSON.stringify(viewData, null, 2));
            onOpenChange(true);
        }
    }, [viewData, isOpen, onOpenChange, dialogId]);

    // Only reset authentication when auth values change but preserve credentials from OAuth
    useEffect(() => {
        // Only reset if this is NOT a fresh OAuth authentication
        if (viewData.isAuthenticated && !viewData.credentialId) {
            setViewData(prevData => ({
                ...prevData,
                isAuthenticated: false
            }));
        }
    }, [viewData.isAuthenticated]);

    // Add this useEffect to handle proper dialog closing with ESC key or backdrop click
    useEffect(() => {
        // If the dialog is closed by any means (ESC, backdrop click, etc.)
        if (!isOpen && hasProcessedRestoreRef.current) {
            console.log('🚪 Dialog closed, cleaning up state');
            // Reset the restore ref so a normal reopen doesn't use saved state
            hasProcessedRestoreRef.current = false;

            // Don't reset the viewData here to preserve authentication state
            // But you could clear other temporary state as needed
        }
    }, [isOpen]);

    return (
        <Dialog
            open={isOpen}
            onOpenChange={(open) => {
                if (!open) {
                    // When closing, call handleCancel instead of just setting isOpen
                    handleCancel();
                } else {
                    onOpenChange(open);
                }
            }}
        >
            <DialogPortal>
                <DialogOverlay className="bg-black/75" />
                <DialogContent
                    className={cn(
                        "p-0 rounded-xl border overflow-hidden",
                        isDark ? "bg-background border-gray-800" : "bg-background border-gray-200"
                    )}
                    style={{
                        width: "800px",
                        height: "80vh",
                        maxWidth: "95vw",
                        maxHeight: "95vh"
                    }}
                >
                    <div className="h-full w-full overflow-hidden">
                        {renderView()}
                    </div>
                </DialogContent>
            </DialogPortal>
        </Dialog>
    );
};

export default DialogFlow;
