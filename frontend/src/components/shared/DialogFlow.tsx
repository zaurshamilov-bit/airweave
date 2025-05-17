import React, { useState, useEffect } from "react";
import { Dialog, DialogContent, DialogPortal, DialogOverlay } from "@/components/ui/dialog";
import { useTheme } from "@/lib/theme-provider";
import { cn } from "@/lib/utils";
import { CreateCollectionView } from "./views/CreateCollectionView";
import { SourceSelectorView } from "./views/SourceSelectorView";
import { ConfigureSourceView } from "./views/ConfigureSourceView";
import { useNavigate } from "react-router-dom";
import { redirectWithError } from "@/lib/error-utils";

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
}) => {
    const { resolvedTheme } = useTheme();
    const isDark = resolvedTheme === "dark";
    const [currentStep, setCurrentStep] = useState(0);
    const [viewData, setViewData] = useState<Record<string, any>>({});
    const navigate = useNavigate();

    // Reset state when dialog opens or mode changes
    useEffect(() => {
        if (isOpen) {
            setCurrentStep(0);
            setViewData({
                sourceId,
                sourceName,
                sourceShortName,
                collectionId,
                collectionName
            });
        }
    }, [isOpen, mode, sourceId, sourceName, sourceShortName, collectionId, collectionName]);

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
                const newData = { ...prevData, ...data };
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
        onOpenChange(false);
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
        console.error(`❌ [DialogFlow] Error:`, error);
        onOpenChange(false);
        redirectWithError(navigate, error, sourceName);
    };

    // Render current view based on flow step
    const renderView = () => {
        const commonProps = {
            onNext: handleNext,
            onCancel: handleCancel,
            onComplete: handleComplete,
            viewData,
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
                return <div>Unknown view</div>;
        }
    };

    return (
        <Dialog open={isOpen} onOpenChange={onOpenChange}>
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
