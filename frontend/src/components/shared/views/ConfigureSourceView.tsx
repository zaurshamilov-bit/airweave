import React, { useEffect, useState } from "react";
import { Button } from "@/components/ui/button";
import { DialogTitle, DialogDescription, DialogFooter } from "@/components/ui/dialog";
import { useTheme } from "@/lib/theme-provider";
import { cn } from "@/lib/utils";
import { useNavigate } from "react-router-dom";
import { redirectWithError } from "@/lib/error-utils";

export interface ConfigureSourceViewProps {
    onNext?: (data?: any) => void;
    onBack?: () => void;
    onCancel?: () => void;
    onComplete?: (data?: any) => void;
    viewData?: Record<string, any>;
    onError?: (error: Error | string, errorSource?: string) => void;
}

export const ConfigureSourceView: React.FC<ConfigureSourceViewProps> = ({
    onNext,
    onBack,
    onCancel,
    onComplete,
    viewData = {},
    onError,
}) => {
    const { resolvedTheme } = useTheme();
    const isDark = resolvedTheme === "dark";
    const navigate = useNavigate();

    // Extract data passed from previous views
    const {
        sourceName,
        sourceShortName,
        // Original collection data
        collectionId,
        collectionName,
        // Collection data created in CreateCollectionView
        created_collection_id,
        created_collection_name
    } = viewData;

    // Handle errors by redirecting to dashboard with error parameters
    const handleError = (error: Error | string, errorType: string) => {
        console.error(`❌ [ConfigureSourceView] ${errorType}:`, error);
        redirectWithError(navigate, error, sourceName || sourceShortName);
    };

    const handleComplete = () => {
        try {
            if (onComplete) {
                onComplete({
                    success: true,
                    message: "Source connected successfully"
                });
            }
        } catch (error) {
            handleError(error instanceof Error ? error : new Error(String(error)), "Source connection error");
        }
    };

    return (
        <div className="flex flex-col h-full">
            {/* Content area - scrollable */}
            <div className="flex-grow overflow-y-auto">
                <div className="p-8 h-full flex flex-col">
                    <DialogTitle className="text-2xl font-semibold text-left mb-4">
                        Connect Source
                    </DialogTitle>

                    <DialogDescription className="text-muted-foreground mb-6">
                        {sourceName ? `Connecting ${sourceName}` : "Configure your source connection"}
                    </DialogDescription>

                    {/* Display both collection data sets */}
                    <div className="bg-muted p-6 rounded-lg mb-4">
                        <h3 className="font-medium mb-4">Collection Information</h3>

                        {/* Existing Collection */}
                        <div className="mb-4 p-3 bg-primary/10 rounded border border-primary/20">
                            <h4 className="font-medium text-sm mb-2">Existing Collection:</h4>
                            <ul className="space-y-1 text-sm">
                                <li><strong>Name:</strong> <span className="font-mono">{collectionName || "undefined"}</span></li>
                                <li><strong>ID:</strong> <span className="font-mono">{collectionId || "undefined"}</span></li>
                            </ul>
                        </div>

                        {/* Created Collection */}
                        <div className="p-3 bg-blue-500/10 rounded border border-blue-500/20">
                            <h4 className="font-medium text-sm mb-2">Created Collection:</h4>
                            <ul className="space-y-1 text-sm">
                                <li><strong>Name:</strong> <span className="font-mono">{created_collection_name || "undefined"}</span></li>
                                <li><strong>ID:</strong> <span className="font-mono">{created_collection_id || "undefined"}</span></li>
                            </ul>
                        </div>
                    </div>

                    {/* All viewData for debugging */}
                    <div className="mt-4 p-3 bg-gray-500/10 rounded border border-gray-500/20">
                        <h4 className="font-medium text-sm mb-2">All Available Data:</h4>
                        <pre className="text-xs overflow-auto max-h-40 p-2 bg-black/5 rounded">
                            {JSON.stringify(viewData, null, 2)}
                        </pre>
                    </div>
                </div>
            </div>

            {/* Footer - fixed at bottom */}
            <div className="flex-shrink-0 border-t">
                <DialogFooter className="flex justify-between gap-3 p-6">
                    <div>
                        {onBack && (
                            <Button
                                type="button"
                                variant="outline"
                                onClick={onBack}
                                className={cn("px-6", isDark ? "border-gray-700" : "border-gray-300")}
                            >
                                Back
                            </Button>
                        )}
                    </div>
                    <div className="flex gap-3">
                        <Button
                            type="button"
                            variant="outline"
                            onClick={onCancel}
                            className={cn("px-6", isDark ? "border-gray-700" : "border-gray-300")}
                        >
                            Cancel
                        </Button>
                        <Button
                            type="button"
                            onClick={handleComplete}
                            className="px-6 bg-blue-600 hover:bg-blue-700 text-white"
                        >
                            Connect
                        </Button>
                    </div>
                </DialogFooter>
            </div>
        </div>
    );
};

export default ConfigureSourceView;
