/**
 * SourceConfigView.tsx
 *
 * This component is responsible for collecting configuration credentials and settings
 * for a data source. It's shown within the ConnectFlow dialog when a source requires
 * additional configuration (e.g., API keys, credentials, URLs).
 *
 * Key responsibilities:
 * 1. Display configuration fields based on source requirements
 * 2. Collect and validate user-entered configuration values
 * 3. Submit configuration to create source connection
 * 4. Handle OAuth special cases and redirect preparation
 *
 * Flow context:
 * - Appears after CreateCollectionView (if source needs configuration)
 * - Only shown for sources that require configuration fields
 * - For OAuth sources, prepares for redirection to provider
 */

import { useState, useEffect } from "react";
import { DialogTitle, DialogDescription, DialogFooter } from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Loader2, Check, ArrowLeft, ArrowRight, Info, AlertCircle } from "lucide-react";
import { toast } from "sonner";
import { DialogViewProps } from "../FlowDialog";
import { apiClient } from "@/lib/api";
import { useTheme } from "@/lib/theme-provider";
import { cn } from "@/lib/utils";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { redirectWithError } from "@/lib/error-utils";
import { useNavigate } from "react-router-dom";

/**
 * Field definition structure from backend API
 * Defines a configuration input field
 */
interface ConfigField {
    /** Field identifier */
    name: string;
    /** Display name */
    title: string;
    /** Optional description/help text */
    description: string;
    /** Input field type (e.g., "string", "password") */
    type: string;
}

/**
 * Source details structure from backend API
 */
interface SourceDetails {
    /** Source display name */
    name: string;
    /** Source description text */
    description?: string;
    /** Source identifier/short name */
    short_name: string;
    /** Configuration field definitions */
    auth_fields?: {
        fields: ConfigField[];
    };
    /** Authentication type (oauth2, basic, etc.) */
    auth_type?: string;
}

/**
 * Collection details interface
 */
interface CollectionDetails {
    /** Collection name */
    name?: string;
    /** Collection identifier */
    readable_id?: string;
}

/**
 * Props for the SourceConfigView component
 * Extends FlowDialog's common DialogViewProps
 */
export interface SourceConfigViewProps extends DialogViewProps {
    viewData?: {
        /** Details for the collection being created */
        collectionDetails?: CollectionDetails;
        /** Source ID */
        sourceId?: string;
        /** Source display name */
        sourceName?: string;
        /** Source short name identifier */
        sourceShortName?: string;
        /** Optional pre-fetched source details */
        sourceDetails?: SourceDetails;
    };
}

/**
 * SourceConfigView Component
 *
 * Collects and validates source configuration and creates the source connection.
 * Handles multi-step form process, validation, and submission.
 */
export const SourceConfigView: React.FC<SourceConfigViewProps> = ({
    onNext,
    onBack,
    onCancel,
    onComplete,
    viewData = {},
}) => {
    // Cast viewData to the expected interface
    const typedViewData = viewData as SourceConfigViewProps["viewData"];
    const collectionDetails: CollectionDetails = typedViewData?.collectionDetails || {};
    const sourceId = typedViewData?.sourceId || "";
    const sourceName = typedViewData?.sourceName || "";
    const sourceShortName = typedViewData?.sourceShortName || "";
    const passedSourceDetails = typedViewData?.sourceDetails;

    const { resolvedTheme } = useTheme();
    const isDark = resolvedTheme === "dark";
    const navigate = useNavigate();

    // =========================================
    // STATE MANAGEMENT
    // =========================================
    /** Current step in the configuration process (1: configure, 2: review) */
    const [step, setStep] = useState(1);
    /** Source details including field definitions */
    const [sourceDetails, setSourceDetails] = useState<SourceDetails | null>(null);
    /** Form configuration values */
    const [config, setConfig] = useState<{ name: string; auth_fields: Record<string, string> }>({
        name: "",
        auth_fields: {}
    });
    /** Form submission state */
    const [isSubmitting, setIsSubmitting] = useState(false);
    /** API loading state */
    const [isLoading, setIsLoading] = useState(false);
    /** Form validation error message */
    const [validationError, setValidationError] = useState<string | null>(null);

    /**
     * Handle API errors by redirecting to dashboard with error parameters
     *
     * @param error - The error that occurred
     * @param errorType - Type of error for better context
     * @param retryAction - Optional function to retry the operation
     */
    const handleError = (error: Error | string, errorType: string, retryAction?: () => void) => {
        console.error(`❌ [SourceConfigView] ${errorType}:`, error);

        // Convert string errors to Error objects
        const errorObj = typeof error === 'string' ? new Error(error) : error;

        // Extract meaningful message from the error
        let errorMessage = errorObj.message;
        let errorDetails = errorObj.stack || errorObj.message;

        // Try to parse and extract more readable error messages
        if (typeof errorMessage === 'string') {
            try {
                // Check for validation errors (common with 422 responses)
                if (errorMessage.includes('RequestValidationError') || errorMessage.includes('body.name')) {
                    // Parse the error JSON if present
                    const errorMatch = errorMessage.match(/({.*})/);
                    if (errorMatch && errorMatch[1]) {
                        const errorJSON = JSON.parse(errorMatch[1]);

                        // Format field validation errors
                        if (errorJSON.error_messages?.errors) {
                            const fieldErrors = errorJSON.error_messages.errors.map((err: any) => {
                                const field = Object.keys(err)[0];
                                // Format field name more nicely (e.g., body.name -> Name)
                                const fieldName = field.replace('body.', '').replace(/^\w/, c => c.toUpperCase());
                                return `${fieldName}: ${err[field]}`;
                            });

                            errorMessage = `Validation Error: ${fieldErrors.join(', ')}`;
                            errorDetails = `The following fields have validation errors:\n${fieldErrors.join('\n')}`;
                        }
                    }
                } else if (errorMessage.includes("Failed to")) {
                    const match = errorMessage.match(/Failed to ([^:]+):/);
                    if (match) {
                        errorMessage = match[0];
                    }
                }
            } catch (e) {
                // If parsing fails, keep the original message
                console.warn("Error parsing error details:", e);
            }
        }

        // Create enhanced error with parsed message and details
        const enhancedError = new Error(errorMessage);
        Object.defineProperty(enhancedError, 'stack', {
            value: errorDetails
        });

        // Use the common error utility to redirect
        redirectWithError(navigate, enhancedError, sourceName || sourceShortName);
    };

    // =========================================
    // INITIALIZATION & CLEANUP
    // =========================================

    /**
     * Initialize from passed source details
     * If sourceDetails are passed through props, use them directly
     */
    useEffect(() => {
        if (passedSourceDetails) {
            console.log("📋 [SourceConfigView] Using passed source details");
            setSourceDetails(passedSourceDetails);

            // Initialize config fields from source definition
            if (passedSourceDetails.auth_fields?.fields) {
                const initialConfig: Record<string, string> = {};
                passedSourceDetails.auth_fields.fields.forEach((field: ConfigField) => {
                    initialConfig[field.name] = "";
                });
                setConfig({
                    name: `My ${sourceName} Connection`,
                    auth_fields: initialConfig
                });
            }
        }
    }, [passedSourceDetails, sourceName]);

    /**
     * Fetch source details if not passed as props
     */
    useEffect(() => {
        if (!passedSourceDetails && sourceShortName) {
            fetchSourceDetails();
        }
    }, [passedSourceDetails, sourceShortName]);

    /**
     * Fetches source details from the API
     * Gets field definitions and authentication requirements
     */
    const fetchSourceDetails = async () => {
        try {
            setIsLoading(true);
            console.log("🔍 [SourceConfigView] Fetching source details for:", sourceShortName);

            const response = await apiClient.get(`/sources/detail/${sourceShortName}`);
            if (!response.ok) {
                const errorText = await response.text();
                throw new Error(`Failed to fetch source details: ${errorText}`);
            }

            const data = await response.json();
            setSourceDetails(data);
            console.log("📥 [SourceConfigView] Received source details");

            // Initialize config
            if (data.auth_fields?.fields) {
                const initialConfig: Record<string, string> = {};
                data.auth_fields.fields.forEach((field: ConfigField) => {
                    initialConfig[field.name] = "";
                });
                setConfig({
                    name: `My ${sourceName} Connection`,
                    auth_fields: initialConfig
                });
            } else {
                // No config fields - shouldn't be in this view
                console.log("⚠️ [SourceConfigView] Source has no config fields");

                // If this is OAuth without fields, initiate redirect instead of just canceling
                if (data.auth_type?.startsWith('oauth2') && sourceShortName && collectionDetails) {
                    console.log("🔐 [SourceConfigView] Initiating OAuth flow for source without config fields");

                    const initiateOAuth = async () => {
                        try {
                            // Store the collection details in localStorage
                            localStorage.setItem("oauth_collection_details", JSON.stringify(collectionDetails));

                            // Also store the collection ID directly to ensure it's available
                            if (collectionDetails.readable_id) {
                                localStorage.setItem("oauth_collection_id", collectionDetails.readable_id);
                                localStorage.setItem("oauth_return_url", `/collections/${collectionDetails.readable_id}`);
                                console.log("💾 [SourceConfigView] Stored collection ID for OAuth:", collectionDetails.readable_id);
                            } else {
                                console.error("❌ [SourceConfigView] No collection ID available for OAuth flow");
                            }

                            // Get the auth URL
                            const resp = await apiClient.get(`/connections/oauth2/source/auth_url?short_name=${sourceShortName}`);
                            if (!resp.ok) {
                                const errorText = await resp.text();
                                throw new Error(`Failed to retrieve auth URL: ${errorText}`);
                            }

                            const authUrl = await resp.text();
                            const cleanUrl = authUrl.replace(/^"|"$/g, ''); // Remove surrounding quotes

                            console.log("🔗 [SourceConfigView] Received OAuth URL, redirecting");

                            // Complete with OAuth redirect info
                            onComplete?.({
                                oauthRedirect: true,
                                collectionId: collectionDetails.readable_id, // Only use the real collection ID
                                authUrl: cleanUrl
                            });
                        } catch (error) {
                            console.error("❌ [SourceConfigView] OAuth initialization error:", error);
                            handleError(
                                error instanceof Error ? error : new Error(String(error)),
                                "OAuth initialization error",
                                () => fetchSourceDetails()
                            );
                        }
                    };

                    initiateOAuth();
                } else {
                    // Not OAuth or missing details, just cancel
                    onCancel?.();
                }
            }
        } catch (error) {
            console.error("❌ [SourceConfigView] Error fetching source details:", error);
            handleError(
                error instanceof Error ? error : new Error(String(error)),
                "Error fetching source details",
                () => fetchSourceDetails()
            );
        } finally {
            setIsLoading(false);
        }
    };

    // =========================================
    // VALIDATION & NAVIGATION
    // =========================================
    /**
     * Validates the configuration form
     * Checks for required fields and formats
     *
     * @returns Boolean indicating if form is valid
     */
    const validateConfig = () => {
        console.log("🔍 [SourceConfigView] Validating config");
        setValidationError(null);

        if (!config.name.trim()) {
            setValidationError("Please enter a name for your connection");
            return false;
        }

        // Validate all required fields
        const missingFields = sourceDetails?.auth_fields?.fields.filter(
            field => !config.auth_fields[field.name]?.trim()
        );

        if (missingFields && missingFields.length > 0) {
            setValidationError(`Please fill in: ${missingFields.map(f => f.title).join(", ")}`);
            return false;
        }

        return true;
    };

    /**
     * Handler for back button click
     * Returns to previous step or view
     */
    const handleBack = () => {
        if (step > 1) {
            setStep(1);
        } else {
            onBack?.();
        }
    };

    /**
     * Handler for next button click
     * Validates and proceeds to review step
     */
    const handleNext = () => {
        if (validateConfig()) setStep(2);
    };

    /**
     * Helper to mask sensitive values in review screen
     * Displays first few characters and masks the rest
     *
     * @param value The sensitive value to mask
     * @returns Masked string
     */
    const maskSensitiveValue = (value: string) => {
        if (!value) return '';
        return value.slice(0, 3) + '*'.repeat(Math.max(value.length - 3, 3));
    };

    // =========================================
    // SUBMIT HANDLER
    // =========================================
    /**
     * Handles form submission
     * Creates collection and source connection with configuration
     */
    const handleSubmit = async () => {
        if (!validateConfig()) return;

        try {
            setIsSubmitting(true);
            console.log("🚀 [SourceConfigView] Submitting config");

            // First create the collection
            let collectionId;
            if (collectionDetails) {
                // If we already have a readable_id, use it directly (adding to existing collection)
                if (collectionDetails.readable_id) {
                    console.log("ℹ️ [SourceConfigView] Using existing collection:", collectionDetails.readable_id);
                    collectionId = collectionDetails.readable_id;
                } else {
                    // Create a new collection if no readable_id (original flow)
                    console.log("📝 [SourceConfigView] Creating collection first:", collectionDetails);
                    const collectionResponse = await apiClient.post("/collections/", collectionDetails);

                    if (!collectionResponse.ok) {
                        const errorText = await collectionResponse.text();
                        throw new Error(`Failed to create collection: ${errorText}`);
                    }

                    const collection = await collectionResponse.json();
                    collectionId = collection.readable_id;
                    console.log("✅ [SourceConfigView] Collection created successfully:", collection);
                }
            } else {
                throw new Error("Collection details are required");
            }

            // BRANCH 1: OAUTH2 SOURCES
            if (sourceDetails?.auth_type?.startsWith('oauth2')) {
                console.log("🔐 [SourceConfigView] OAuth2 source - storing config for later");

                // Store config fields in session storage for AuthCallback.tsx to use
                sessionStorage.setItem(`oauth2_config_${sourceShortName}`, JSON.stringify({
                    connection_name: config.name,
                    auth_fields: config.auth_fields
                }));

                // Store the collection ID and return URL for OAuth
                localStorage.setItem("oauth_collection_id", collectionId);
                localStorage.setItem("oauth_return_url", `/collections/${collectionId}`);

                toast.success("Configuration saved, redirecting to authorization...");

                // Get the auth URL
                const resp = await apiClient.get(`/connections/oauth2/source/auth_url?short_name=${sourceShortName}`);
                if (!resp.ok) {
                    const errorText = await resp.text();
                    throw new Error(`Failed to retrieve OAuth authorization URL: ${errorText}`);
                }

                const authUrl = await resp.text();
                const cleanUrl = authUrl.replace(/^"|"$/g, ''); // Remove surrounding quotes

                // Complete the flow with OAuth redirect info
                onComplete?.({
                    oauthRedirect: true,
                    collectionId,
                    authUrl: cleanUrl
                });

                return;
            }

            // BRANCH 2: CONFIG_CLASS / API_KEY SOURCES
            console.log("🛠️ [SourceConfigView] Config class source - creating source connection directly");

            // Create source connection with config fields
            const sourceConnectionPayload = {
                name: config.name,
                short_name: sourceShortName,
                collection: collectionId,
                auth_fields: config.auth_fields,
                sync_immediately: true
            };

            console.log("📤 [SourceConfigView] Creating source connection");

            // =====================================================================
            // BACKEND SOURCE CONNECTION CREATION - IMPORTANT DATABASE OPERATION
            // This is where a new SOURCE CONNECTION is created in the database
            // POST /source-connections/ endpoint creates a persistent source connection
            // record with the provided authentication fields in source_connections.py
            // =====================================================================
            const response = await apiClient.post(
                `/source-connections/`,
                sourceConnectionPayload
            );

            if (!response.ok) {
                const errorText = await response.text();
                throw new Error(`Failed to create source connection: ${errorText}`);
            }

            const data = await response.json();
            console.log("✅ [SourceConfigView] Source connection created with ID:", data.id);

            // Store the created source connection data
            sessionStorage.setItem('last_created_source_connection', JSON.stringify(data));

            toast.success("Connection created successfully!");

            // Complete with source connection and collection data
            onComplete?.({
                sourceConnection: data,
                collectionId
            });
        } catch (error) {
            console.error("❌ [SourceConfigView] Error:", error);
            handleError(
                error instanceof Error ? error : new Error(String(error)),
                "Connection creation error",
                () => handleSubmit()
            );
        } finally {
            setIsSubmitting(false);
        }
    };

    // =========================================
    // RENDER UI
    // =========================================
    return (
        <div className="flex flex-col h-full">
            {/* Content area - scrollable */}
            <div className="flex-grow overflow-y-auto">
                <div className="p-8">
                    {/* Configuration step */}
                    {step === 1 && (
                        <div className="space-y-8 animate-in fade-in duration-300">
                            {isLoading ? (
                                <div className="flex items-center justify-center py-12">
                                    <Loader2 className="h-8 w-8 animate-spin text-primary" />
                                </div>
                            ) : sourceDetails ? (
                                <>
                                    <div className="space-y-2">
                                        <DialogTitle className="text-2xl font-bold">Configure {sourceDetails.name}</DialogTitle>
                                        <DialogDescription className="text-muted-foreground">
                                            {sourceDetails.description?.split('\n')[0]}
                                        </DialogDescription>
                                    </div>

                                    {/* Validation error message */}
                                    {validationError && (
                                        <Alert variant="destructive" className="border-red-500 bg-red-500/10 text-red-500">
                                            <AlertCircle className="h-4 w-4" />
                                            <AlertDescription>{validationError}</AlertDescription>
                                        </Alert>
                                    )}

                                    <div className="space-y-4">
                                        <div className="space-y-2">
                                            <Label htmlFor="name">Connection Name</Label>
                                            <Input
                                                id="name"
                                                value={config.name}
                                                onChange={(e) => setConfig({ ...config, name: e.target.value })}
                                                placeholder="Enter a name for this connection"
                                            />
                                        </div>

                                        {sourceDetails.auth_fields?.fields.map((field) => (
                                            <div key={field.name} className="space-y-2">
                                                <Label htmlFor={field.name}>
                                                    {field.title}
                                                    {field.description && (
                                                        <span className="text-xs text-muted-foreground ml-2">
                                                            ({field.description})
                                                        </span>
                                                    )}
                                                </Label>
                                                <Input
                                                    id={field.name}
                                                    type={field.type === "string" ? "text" : field.type}
                                                    value={config.auth_fields[field.name] || ""}
                                                    onChange={(e) => {
                                                        // Clear validation errors when user makes changes
                                                        if (validationError) setValidationError(null);
                                                        setConfig({
                                                            ...config,
                                                            auth_fields: {
                                                                ...config.auth_fields,
                                                                [field.name]: e.target.value
                                                            }
                                                        });
                                                    }}
                                                    placeholder={`Enter ${field.title.toLowerCase()}`}
                                                />
                                            </div>
                                        ))}
                                    </div>
                                </>
                            ) : (
                                <div className="text-center text-muted-foreground">
                                    Failed to load configuration. Please try again.
                                </div>
                            )}
                        </div>
                    )}

                    {/* Review step */}
                    {step === 2 && sourceDetails && (
                        <div className="space-y-8 animate-in fade-in duration-300">
                            <div className="space-y-2">
                                <DialogTitle className="text-2xl font-bold">Review Configuration</DialogTitle>
                                <DialogDescription className="text-muted-foreground">
                                    Review your configuration and complete setup.
                                </DialogDescription>
                            </div>

                            <div className="space-y-4 rounded-lg border p-4">
                                <div className="grid gap-4">
                                    <div>
                                        <p className="text-sm text-muted-foreground">Connection Name</p>
                                        <p className="font-medium">{config.name}</p>
                                    </div>

                                    {sourceDetails.auth_fields?.fields.map((field) => (
                                        <div key={field.name}>
                                            <p className="text-sm text-muted-foreground">{field.title}</p>
                                            <p className="font-medium">
                                                {field.type === "password" || field.name.toLowerCase().includes('key') || field.name.toLowerCase().includes('token')
                                                    ? maskSensitiveValue(config.auth_fields[field.name])
                                                    : config.auth_fields[field.name]}
                                            </p>
                                        </div>
                                    ))}

                                    <div>
                                        <p className="text-sm text-muted-foreground">Collection Name</p>
                                        <p className="font-medium">{collectionDetails?.name || ""}</p>
                                    </div>

                                    {collectionDetails?.readable_id && (
                                        <div>
                                            <p className="text-sm text-muted-foreground">Collection ID</p>
                                            <p className="font-medium">{collectionDetails.readable_id}</p>
                                        </div>
                                    )}
                                </div>
                            </div>
                        </div>
                    )}
                </div>
            </div>

            {/* Footer actions - fixed at bottom */}
            <div className="flex-shrink-0 border-t">
                <DialogFooter className="flex justify-between p-6">
                    <div>
                        {step > 1 || onBack ? (
                            <Button variant="outline" onClick={handleBack} disabled={isSubmitting}>
                                <ArrowLeft className="mr-2 h-4 w-4" /> Back
                            </Button>
                        ) : (
                            <Button variant="outline" onClick={onCancel} disabled={isSubmitting}>
                                Cancel
                            </Button>
                        )}
                    </div>

                    <div>
                        {step === 1 ? (
                            <Button
                                onClick={() => {
                                    if (validateConfig()) setStep(2);
                                }}
                                disabled={isLoading}
                                className="bg-blue-600 hover:bg-blue-700 text-white"
                            >
                                Next <ArrowRight className="ml-2 h-4 w-4" />
                            </Button>
                        ) : (
                            <Button
                                onClick={handleSubmit}
                                disabled={isSubmitting}
                                className="bg-blue-600 hover:bg-blue-700 text-white"
                            >
                                {isSubmitting ? (
                                    <>
                                        <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                                        {sourceDetails?.auth_type?.startsWith('oauth2')
                                            ? "Saving Configuration..."
                                            : "Creating Connection..."}
                                    </>
                                ) : (
                                    <>
                                        <Check className="mr-2 h-4 w-4" />
                                        Complete Setup
                                    </>
                                )}
                            </Button>
                        )}
                    </div>
                </DialogFooter>
            </div>
        </div>
    );
};

export default SourceConfigView;
