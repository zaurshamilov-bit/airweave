import React, { useEffect, useState } from "react";
import { Button } from "@/components/ui/button";
import { DialogTitle, DialogDescription, DialogFooter } from "@/components/ui/dialog";
import { useTheme } from "@/lib/theme-provider";
import { cn } from "@/lib/utils";
import { useNavigate } from "react-router-dom";
import { redirectWithError } from "@/lib/error-utils";
import { apiClient } from "@/lib/api";

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
    const [loading, setLoading] = useState(false);
    const [sourceDetails, setSourceDetails] = useState<any>(null);

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

    // Fetch source details including auth and config fields
    useEffect(() => {
        if (!sourceShortName) return;

        const fetchSourceDetails = async () => {
            setLoading(true);
            try {
                const response = await apiClient.get(`/sources/detail/${sourceShortName}`);
                if (response.ok) {
                    const data = await response.json();
                    setSourceDetails(data);
                    console.log("Source details loaded:", data);
                } else {
                    const errorText = await response.text();
                    console.error(`Failed to load source details: ${errorText}`);
                    handleError(new Error(`Failed to load source details: ${errorText}`), "Source details fetch error");
                }
            } catch (error) {
                console.error("Error fetching source details:", error);
                handleError(error instanceof Error ? error : new Error(String(error)), "Source details fetch error");
            } finally {
                setLoading(false);
            }
        };

        fetchSourceDetails();
    }, [sourceShortName]);

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

                    {/* Display source configuration fields if loaded */}
                    {loading ? (
                        <div className="flex justify-center items-center py-8">
                            <div className="animate-spin w-8 h-8 border-4 border-blue-500 border-t-transparent rounded-full"></div>
                        </div>
                    ) : sourceDetails ? (
                        <div className="space-y-6">
                            {/* Auth fields section */}
                            {sourceDetails.auth_config_class && (
                                <div className="bg-muted p-6 rounded-lg mb-4">
                                    <div className="flex justify-between items-center mb-4">
                                        <h3 className="font-medium">Authentication</h3>
                                        <span className="text-xs text-muted-foreground bg-muted-foreground/20 px-2 py-1 rounded">
                                            {sourceDetails.auth_config_class}
                                        </span>
                                    </div>

                                    {sourceDetails.auth_fields && sourceDetails.auth_fields.fields &&
                                        Object.keys(sourceDetails.auth_fields.fields).length > 0 ? (
                                        <div className="space-y-4">
                                            {Object.entries(sourceDetails.auth_fields.fields || {}).map(([key, field]: [string, any]) => (
                                                <div key={key} className="space-y-2">
                                                    <label className="text-sm font-medium">{field.title || key}</label>
                                                    <input
                                                        type={field.type === 'password' ? 'password' : 'text'}
                                                        className={cn(
                                                            "w-full p-2 rounded border",
                                                            isDark ? "bg-gray-800 border-gray-700" : "bg-white border-gray-300"
                                                        )}
                                                        placeholder={field.description || ''}
                                                    />
                                                    {field.description && (
                                                        <p className="text-xs text-muted-foreground">{field.description}</p>
                                                    )}
                                                </div>
                                            ))}
                                        </div>
                                    ) : (
                                        <div className="py-4 text-sm text-muted-foreground italic">
                                            No authentication fields defined for this source.
                                        </div>
                                    )}
                                </div>
                            )}

                            {/* Config schema section */}
                            <div className="bg-muted p-6 rounded-lg mb-4">
                                <div className="flex justify-between items-center mb-4">
                                    <h3 className="font-medium">Configuration</h3>
                                    {sourceDetails.config_class && (
                                        <span className="text-xs text-muted-foreground bg-muted-foreground/20 px-2 py-1 rounded">
                                            {sourceDetails.config_class}
                                        </span>
                                    )}
                                </div>

                                {sourceDetails.config_schema &&
                                    sourceDetails.config_schema.properties &&
                                    Object.keys(sourceDetails.config_schema.properties).length > 0 ? (
                                    <div className="space-y-4">
                                        {Object.entries(sourceDetails.config_schema.properties || {}).map(([key, field]: [string, any]) => (
                                            <div key={key} className="space-y-2">
                                                <label className="text-sm font-medium">{field.title || key}</label>
                                                <input
                                                    type="text"
                                                    className={cn(
                                                        "w-full p-2 rounded border",
                                                        isDark ? "bg-gray-800 border-gray-700" : "bg-white border-gray-300"
                                                    )}
                                                    placeholder={field.description || ''}
                                                />
                                                {field.description && (
                                                    <p className="text-xs text-muted-foreground">{field.description}</p>
                                                )}
                                            </div>
                                        ))}
                                    </div>
                                ) : (
                                    <div className="py-4 text-sm text-muted-foreground italic">
                                        No configuration fields defined for this source.
                                    </div>
                                )}
                            </div>
                        </div>
                    ) : (
                        <div className="text-center py-8 text-muted-foreground">
                            No source configuration available
                        </div>
                    )}

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
                            disabled={loading}
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
