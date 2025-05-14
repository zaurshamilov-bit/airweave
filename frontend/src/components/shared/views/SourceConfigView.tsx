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

// Field definition from backend API
interface ConfigField {
    name: string;
    title: string;
    description: string;
    type: string;
}

// Source details from backend API
interface SourceDetails {
    name: string;
    description: string;
    short_name: string;
    auth_fields?: {
        fields: ConfigField[];
    };
    auth_type?: string;
}

// Collection details interface
interface CollectionDetails {
    name?: string;
    readable_id?: string;
}

export interface SourceConfigViewProps extends DialogViewProps {
    viewData?: {
        collectionDetails?: CollectionDetails;
        sourceId?: string;
        sourceName?: string;
        sourceShortName?: string;
        sourceDetails?: SourceDetails;
    };
}

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

    // =========================================
    // STATE MANAGEMENT
    // =========================================
    const [step, setStep] = useState(1);
    const [sourceDetails, setSourceDetails] = useState<SourceDetails | null>(null);
    const [config, setConfig] = useState<{ name: string; auth_fields: Record<string, string> }>({
        name: "",
        auth_fields: {}
    });
    const [isSubmitting, setIsSubmitting] = useState(false);
    const [isLoading, setIsLoading] = useState(false);
    const [validationError, setValidationError] = useState<string | null>(null);

    // =========================================
    // INITIALIZATION & CLEANUP
    // =========================================

    // Initialize from passed source details
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

    // Fetch source details if not passed
    useEffect(() => {
        if (!passedSourceDetails && sourceShortName) {
            fetchSourceDetails();
        }
    }, [passedSourceDetails, sourceShortName]);

    const fetchSourceDetails = async () => {
        try {
            setIsLoading(true);
            console.log("🔍 [SourceConfigView] Fetching source details for:", sourceShortName);

            const response = await apiClient.get(`/sources/detail/${sourceShortName}`);
            if (!response.ok) {
                throw new Error("Failed to fetch source details");
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

                            // Get the auth URL
                            const resp = await apiClient.get(`/connections/oauth2/source/auth_url?short_name=${sourceShortName}`);
                            if (!resp.ok) {
                                throw new Error("Failed to retrieve auth URL");
                            }

                            const authUrl = await resp.text();
                            const cleanUrl = authUrl.replace(/^"|"$/g, ''); // Remove surrounding quotes

                            console.log("🔗 [SourceConfigView] Received OAuth URL, redirecting");

                            // Complete with OAuth redirect info
                            onComplete?.({
                                oauthRedirect: true,
                                collectionId: collectionDetails.readable_id,
                                authUrl: cleanUrl
                            });
                        } catch (error) {
                            console.error("❌ [SourceConfigView] OAuth initialization error:", error);
                            onCancel?.();
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
            toast.error("Failed to load source configuration");
        } finally {
            setIsLoading(false);
        }
    };

    // =========================================
    // VALIDATION & NAVIGATION
    // =========================================
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

    const handleBack = () => {
        if (step > 1) {
            setStep(1);
        } else {
            onBack?.();
        }
    };

    const handleNext = () => {
        if (validateConfig()) setStep(2);
    };

    // Helper to mask sensitive values in review screen
    const maskSensitiveValue = (value: string) => {
        if (!value) return '';
        return value.slice(0, 3) + '*'.repeat(Math.max(value.length - 3, 3));
    };

    // =========================================
    // SUBMIT HANDLER
    // =========================================
    const handleSubmit = async () => {
        if (!validateConfig()) return;

        try {
            setIsSubmitting(true);
            console.log("🚀 [SourceConfigView] Submitting config");

            // First create the collection
            let collectionId;
            if (collectionDetails) {
                console.log("📝 [SourceConfigView] Creating collection first:", collectionDetails);
                const collectionResponse = await apiClient.post("/collections/", collectionDetails);

                if (!collectionResponse.ok) {
                    const errorText = await collectionResponse.text();
                    throw new Error(`Failed to create collection: ${errorText}`);
                }

                const collection = await collectionResponse.json();
                collectionId = collection.readable_id;
                console.log("✅ [SourceConfigView] Collection created successfully:", collection);
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
                    throw new Error("Failed to retrieve auth URL");
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
            toast.error(error instanceof Error ? error.message : "Failed to create connection");
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
