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
    errorData?: any; // Add explicit error data prop for direct error passing
}

// Add this interface after DialogFlowProps
export interface DialogViewProps {
    onNext?: (data?: any) => void;
    onBack?: () => void;
    onCancel?: () => void;
    onComplete?: (data?: any) => void;
    viewData?: Record<string, any>;
    onError?: (error: Error | string, errorSource?: string) => void;
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
    errorData,
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
    // Add a new ref to track if dialog is being restored without reset
    const isRestoringRef = useRef(false);

    // Reset state when dialog opens or mode changes
    useEffect(() => {
        // DON'T reset viewData or currentStep if we're restoring dialog or in restoration process
        if (isOpen && !hasProcessedRestoreRef.current && !isRestoringRef.current) {
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

    // Handle direct error data passed via props
    useEffect(() => {
        if (errorData && isOpen) {
            console.log("🔔 [DialogFlow] Direct error data provided:", errorData);
            setErrorViewData({
                serviceName: errorData.serviceName || sourceName || "the service",
                sourceShortName: errorData.sourceShortName || sourceShortName || errorData.serviceName?.toLowerCase(),
                errorMessage: errorData.errorMessage || "Connection failed",
                errorDetails: errorData.errorDetails,
                retryAction: errorData.retryAction
            });
            setShowErrorView(true);
        }
    }, [errorData, isOpen, sourceName, sourceShortName]);

    // Update the effect to force dialog open
    useEffect(() => {
        const restoreDialog = searchParams.get('restore_dialog') === 'true';
        const oauthError = searchParams.get('oauth_error') === 'true';
        const connectionError = searchParams.get('connected') === 'error';

        // Prevent processing the restore more than once
        if ((restoreDialog || oauthError) && !hasProcessedRestoreRef.current) {
            // Mark that we're starting the restoration process - DON'T reset in the other effects
            isRestoringRef.current = true;

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

                        // First update the step (before opening dialog)
                        const restoredStep = typeof savedState.dialogFlowStep === 'number' ? savedState.dialogFlowStep : 1;
                        setCurrentStep(restoredStep);
                        console.log(`🔢 Setting current step to: ${restoredStep}`);

                        // Set the viewData with all necessary state information from savedState
                        // This ensures we include connectionName and all other fields from the saved state
                        setViewData({
                            ...savedState,                  // Include ALL fields from saved state
                            dialogId: savedState.dialogId,  // Ensure the dialog ID is set
                            dialogFlowStep: restoredStep,   // Update with the current step
                            dialogMode: savedState.dialogMode || mode // Use saved mode or current mode
                        });

                        // Force dialog open with a robust approach
                        setTimeout(() => {
                            console.log(`🚨 Forcing dialog open with dialogId: ${dialogId}`);

                            // Set the flag that we've forced the dialog open BEFORE opening
                            setHasBeenForced(true);

                            // Mark as processed right before opening
                            hasProcessedRestoreRef.current = true;

                            // Open the dialog
                            onOpenChange(true);

                            // Clean up stored dialog state after dialog is open
                            sessionStorage.removeItem('oauth_dialog_state');

                            // Keep isRestoringRef true until dialog is fully open
                            setTimeout(() => {
                                isRestoringRef.current = false;
                                console.log(`✅ Restoration complete for dialog: ${dialogId}`);
                            }, 50);
                        }, 50);
                    } else {
                        console.log(`⏭️ Dialog ID mismatch: saved=${savedState.dialogId}, current=${dialogId}, skipping restore`);
                        isRestoringRef.current = false;
                    }

                    console.log("📊 FULL SAVED STATE IN DIALOG FLOW:", JSON.stringify(savedState, null, 2));
                    console.log("📊 FULL VIEW DATA AFTER RESTORE:", JSON.stringify(viewData, null, 2));
                } catch (error) {
                    console.error("❌ Error restoring dialog state:", error);
                    isRestoringRef.current = false;

                    // Handle restoration errors by showing error view
                    setErrorViewData({
                        serviceName: sourceName || "Dialog",
                        sourceShortName: sourceShortName || "dialog",
                        errorMessage: "Failed to restore dialog state",
                        errorDetails: error instanceof Error ? error.stack : String(error)
                    });
                    setShowErrorView(true);
                    onOpenChange(true);
                }
            } else {
                isRestoringRef.current = false;
            }
        } else if (connectionError) {
            console.log("🔍 Checking for stored error details");
            // Check for errors stored via error-utils
            const errorDetails = getStoredErrorDetails();

            if (errorDetails) {
                console.log("🔔 Found error details in localStorage:",
                    { type: typeof errorDetails, hasMessage: !!errorDetails.errorMessage });

                // Extract JSON error details if available
                const errorMessage = errorDetails.errorMessage || "Connection failed";
                let errorDetailsText = errorDetails.errorDetails || "";

                // Try to parse JSON from error message if it exists
                if (errorMessage && typeof errorMessage === 'string' && errorMessage.includes('{')) {
                    try {
                        const jsonStart = errorMessage.indexOf('{');
                        const jsonEnd = errorMessage.lastIndexOf('}') + 1;
                        if (jsonStart > -1 && jsonEnd > jsonStart) {
                            const jsonStr = errorMessage.substring(jsonStart, jsonEnd);
                            const parsed = JSON.parse(jsonStr);
                            // Use the detail from the JSON if available
                            if (parsed.detail) {
                                errorDetailsText = parsed.detail;
                            }
                        }
                    } catch (e) {
                        console.error("Error parsing JSON from error message:", e);
                    }
                }

                // Set error view data with retry action
                setErrorViewData({
                    serviceName: errorDetails.serviceName || sourceName || "the service",
                    sourceShortName: errorDetails.sourceShortName ||
                        sourceShortName ||
                        errorDetails.serviceName?.toLowerCase(),
                    errorMessage: errorMessage,
                    errorDetails: errorDetailsText,
                    // Add a retry action if available
                    retryAction: errorDetails.canRetry ? () => {
                        setShowErrorView(false);
                        // Return to the last step
                        if (errorDetails.dialogState?.dialogFlowStep) {
                            setCurrentStep(errorDetails.dialogState.dialogFlowStep);
                        }
                    } : undefined
                });

                // Show error view and open dialog
                setShowErrorView(true);
                onOpenChange(true);

                // Don't clean up URL right away - wait until dialog is visible
                setTimeout(() => {
                    // Only clean up if dialog is still showing
                    if (isOpen && showErrorView) {
                        const newUrl = window.location.pathname;
                        window.history.replaceState({}, '', newUrl);
                    }
                }, 500);
            } else if (searchParams.get("connected") === "error") {
                console.warn("🚫 Connection error parameter present but no error details found",
                    localStorage.getItem(CONNECTION_ERROR_STORAGE_KEY));

                // Get error details from URL search params if possible
                const errorParam = searchParams.get('error');
                const errorMsg = searchParams.get('error_message');

                // Fallback error when details are missing
                setErrorViewData({
                    serviceName: sourceName || "Unknown service",
                    sourceShortName: sourceShortName || "unknown service",
                    errorMessage: errorMsg || "Connection failed - details unavailable",
                    errorDetails: "The error details were not properly captured. This may be a browser storage issue."
                });
                setShowErrorView(true);
                onOpenChange(true);
            }

            // Clean up URL regardless
            setTimeout(() => {
                const newUrl = window.location.pathname;
                window.history.replaceState({}, '', newUrl);
            }, 100);
        }
    }, [searchParams, onOpenChange, isOpen, dialogId, mode, sourceName, sourceShortName]);

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
    const currentView = showErrorView ? "error" : (currentFlow ? currentFlow[currentStep] : null);

    // Move all useEffect hooks here, before any returns or conditional logic

    // Effect for opening dialog with populated credential info
    useEffect(() => {
        // Only open dialog when viewData has been populated with credential info
        // AND we haven't just closed it manually AND not marked as completed
        if (viewData.credentialId && !isOpen && hasProcessedRestoreRef.current && !viewData.isCompleted) {
            console.log(`🔔 Opening dialog ${dialogId} with populated viewData:`, JSON.stringify(viewData, null, 2));
            onOpenChange(true);
        }
    }, [viewData, isOpen, onOpenChange, dialogId]);

    // Effect for resetting authentication
    useEffect(() => {
        // Only reset if this is NOT a fresh OAuth authentication
        if (viewData.isAuthenticated && !viewData.credentialId) {
            setViewData(prevData => ({
                ...prevData,
                isAuthenticated: false
            }));
        }
    }, [viewData.isAuthenticated]);

    // Effect for handling dialog closing
    useEffect(() => {
        // If the dialog is closed by any means (ESC, backdrop click, etc.)
        if (!isOpen && hasProcessedRestoreRef.current) {
            console.log('🚪 Dialog closed, cleaning up state');
            // Reset the restore ref so a normal reopen doesn't use saved state
            hasProcessedRestoreRef.current = false;
            isRestoringRef.current = false;

            // Also clear error state when dialog is closed
            if (showErrorView) {
                setShowErrorView(false);
                setErrorViewData(null);
            }

            // Don't reset the viewData here to preserve authentication state
            // But you could clear other temporary state as needed
        }
    }, [isOpen, showErrorView]);

    // Now implement renderView() without any hooks inside
    const renderView = () => {
        // If we should show the error view, return that
        if (showErrorView || currentView === "error") {
            return (
                <ConnectionErrorView
                    onCancel={() => {
                        // Mark that we're handling this error - prevent cycles
                        setShowErrorView(false);

                        // Close the dialog first
                        onOpenChange(false);

                        // Only after dialog is closed, clean up storage and URL
                        setTimeout(() => {
                            // Clear error from localStorage
                            clearStoredErrorDetails();

                            // Clean up URL parameters
                            const url = new URL(window.location.href);
                            if (url.searchParams.has('connected')) {
                                url.searchParams.delete('connected');
                                window.history.replaceState({}, '', url.toString());
                            }
                        }, 100);
                    }}
                    viewData={errorViewData}
                />
            );
        }

        // If currentView is null (invalid mode), return an error view
        if (currentView === null) {
            return (
                <ConnectionErrorView
                    onCancel={() => {
                        onOpenChange(false);
                    }}
                    viewData={{
                        serviceName: "Dialog Flow",
                        sourceShortName: "dialog",
                        errorMessage: `Configuration error in dialog flow`,
                        errorDetails: `Invalid mode: ${mode} or missing flow sequence`
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
                dialogFlowStep: currentStep, // Store current step for restoration
                dialogMode: mode, // Always include mode for restoration
            } as any,
            onError: handleError,
        };

        // Only add back button if not at first step
        if (currentStep > 0) {
            (commonProps as any).onBack = handleBack;
        }

        switch (currentView) {
            case "sourceSelector":
                return <SourceSelectorView {...commonProps} />;
            case "createCollection":
                return <CreateCollectionView {...commonProps} />;
            case "connectSource":
                return <ConfigureSourceView {...commonProps} />;
            default:
                return (
                    <ConnectionErrorView
                        onCancel={() => onOpenChange(false)}
                        viewData={{
                            serviceName: "Dialog Flow",
                            sourceShortName: "dialog",
                            errorMessage: `Unknown view: ${currentView}`,
                            errorDetails: `Available views: sourceSelector, createCollection, connectSource`
                        }}
                    />
                );
        }
    };

    // Handle next step
    const handleNext = (data?: any) => {
        if (data) {
            setViewData(prevData => {
                const newData = {
                    ...prevData,
                    ...data,
                    dialogId, // Always maintain the dialogId
                    dialogMode: mode // Always maintain the dialogMode
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

        // Check if we're in error view mode
        const isInErrorMode = showErrorView;

        // Always close the dialog immediately
        onOpenChange(false);

        // Reset the dialog state
        setCurrentStep(0);
        setShowErrorView(false);
        setErrorViewData(null);

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

        // Clear error state from localStorage (if we were showing an error)
        if (isInErrorMode) {
            clearStoredErrorDetails();

            // Clean up URL parameters
            const currentUrl = new URL(window.location.href);
            if (currentUrl.searchParams.has('connected')) {
                currentUrl.searchParams.delete('connected');
                window.history.replaceState({}, '', currentUrl.toString());
            }
        }
    };

    // Handle completion
    const handleComplete = (result: any) => {
        // Preserve the isCompleted flag in viewData to prevent reopening
        if (result && result.isCompleted) {
            setViewData(prevData => ({
                ...prevData,
                isCompleted: true
            }));
        }

        onOpenChange(false);
        if (onComplete) {
            onComplete(result);
        }
    };

    // Add enhanced error handling function that can be passed to views
    const handleError = (error: Error | string, errorSource?: string) => {
        console.error(`❌ [DialogFlow] Error with dialogId=${dialogId}:`, error);

        // Create the ability to retry by default
        const canRetry = currentStep > 0;

        // First, close the dialog to prevent stale state
        onOpenChange(false);

        // Add the retry capability to the error data
        const errorMsg = error instanceof Error ? error.message : error;
        const errorStack = error instanceof Error ? error.stack : undefined;

        // Create complete error details
        const completeError = {
            serviceName: errorSource || viewData.sourceName || "the service",
            errorMessage: errorMsg,
            errorDetails: errorStack,
            canRetry,
            // Store current dialog state for potential retry
            dialogState: {
                ...viewData,
                dialogFlowStep: currentStep
            },
            dialogId,
            timestamp: Date.now()
        };

        // Use the common error utility to redirect with full details
        redirectWithError(navigate, completeError, errorSource || viewData.sourceName);
    };

    // Fix DialogFlow error handling
    const handleDialogError = (error: Error | string, errorSource?: string) => {
        console.log('❌ [DialogFlow] Error with dialogId=' + dialogId + ':', error);

        // Prepare error data
        const errorData = {
            serviceName: errorSource || 'Unknown service',
            errorMessage: error instanceof Error ? error.message : error,
            errorDetails: error instanceof Error ? error.stack || error.message : String(error),
            canRetry: dialogState?.canRetry || false,
            dialogState,
            dialogId,
            timestamp: Date.now()
        };

        // Store error details without clearing
        redirectWithError(navigate, errorData.errorMessage, errorData.serviceName, errorData);

        // Update current step to Error view
        setCurrentStep(6); // Assuming 6 is your error view step

        if (onError) {
            onError(error, errorSource);
        }
    };

    // Fix dialog restoration and error handling useEffect (~line 570)
    useEffect(() => {
        // Check for URL param indicating an error
        if (searchParams.get('connected') === 'error') {
            const errorDetails = getStoredErrorDetails();
            console.log('🔔 Found error details in localStorage:', {
                type: typeof errorDetails,
                hasMessage: errorDetails?.errorMessage ? true : false
            });

            if (errorDetails) {
                // Don't clear localStorage here, wait for explicit dismissal
                setErrorViewData({
                    serviceName: errorDetails.serviceName || sourceName || "the service",
                    sourceShortName: errorDetails.sourceShortName ||
                        sourceShortName ||
                        errorDetails.serviceName?.toLowerCase(),
                    errorMessage: errorDetails.errorMessage || "Connection failed",
                    errorDetails: errorDetails.errorDetails || "",
                    // Add a retry action if available
                    retryAction: errorDetails.canRetry ? () => {
                        setShowErrorView(false);
                        // Return to the last step
                        if (errorDetails.dialogState?.dialogFlowStep) {
                            setCurrentStep(errorDetails.dialogState.dialogFlowStep);
                        }
                    } : undefined
                });

                // Force open the error dialog
                if (dialogId && errorDetails.dialogId === dialogId) {
                    setShowErrorView(true);
                    // Use onOpenChange directly instead of undefined forceOpenDialog
                    onOpenChange(true);
                }
            } else {
                console.log('🚫 Connection error parameter present but no error details found', errorDetails);

                // Fallback error when details are missing
                setErrorViewData({
                    serviceName: sourceName || "Unknown service",
                    sourceShortName: sourceShortName || "unknown service",
                    errorMessage: "Connection failed - details unavailable",
                    errorDetails: "The error details were not properly captured. This may be a browser storage issue."
                });
                setShowErrorView(true);
                onOpenChange(true);
            }
        }
    }, [searchParams, dialogId, sourceName, sourceShortName, onOpenChange]);

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
