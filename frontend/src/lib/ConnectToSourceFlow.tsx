import { useState, useEffect, useRef } from "react";
import { toast } from "sonner";
import { useNavigate } from "react-router-dom";
import { SourceConfigDialog } from "@/components/sync";
import { apiClient } from "@/lib/api";

// Interface for source details
interface SourceDetails {
    name: string;
    description?: string;
    short_name: string;
    auth_type?: string;
    auth_fields?: {
        fields: any[];
    };
}

interface ConnectToSourceFlowProps {
    sourceShortName: string;
    sourceName: string;
    collectionId: string;
    onComplete?: (connectionId: string) => void;
    onError?: (error: Error) => void;
}

// Constants for local storage keys
const OAUTH_RETURN_URL_KEY = "oauth_return_url";
const OAUTH_COLLECTION_ID_KEY = "oauth_collection_id";

// Hook that provides all the connection flow logic
export const useConnectToSourceFlow = () => {
    const [configDialogOpen, setConfigDialogOpen] = useState(false);
    const [sourceConnectionConfig, setSourceConnectionConfig] = useState<{
        name: string;
        short_name: string;
        sourceDetails?: any;
        collectionId?: string;
        onConfigComplete?: (connectionId: string) => void;
    } | null>(null);
    const navigate = useNavigate();

    // =========================================
    // MAIN ENTRY POINT: Initiate connection
    // =========================================
    const initiateConnection = async (
        sourceShortName: string,
        sourceName: string,
        collectionId: string,
        sourceDetails?: SourceDetails,
        onComplete?: () => void
    ) => {
        console.log("🚀 [ConnectToSourceFlow] Initiating connection:", {
            sourceShortName,
            sourceName,
            collectionId,
            hasSourceDetails: !!sourceDetails
        });

        try {
            // If sourceDetails is not provided, fetch them
            let details = sourceDetails;
            if (!details) {
                console.log("🔍 [ConnectToSourceFlow] Fetching source details for:", sourceShortName);
                const response = await apiClient.get(`/sources/detail/${sourceShortName}`);
                if (!response.ok) {
                    throw new Error("Failed to fetch source details");
                }
                details = await response.json();
                console.log("📥 [ConnectToSourceFlow] Received source details:", details);
            }

            const authType = details?.auth_type;
            console.log("🔑 [ConnectToSourceFlow] Auth type:", authType);

            // DECISION POINT: Route to appropriate flow based on auth type and config fields
            if (details?.auth_fields?.fields && details.auth_fields.fields.length > 0) {
                // Has config fields (regardless of auth type) - open the wizard
                await handleConfigFieldsAuth(sourceShortName, sourceName, collectionId, details, onComplete);
            }
            else {
                // No config fields required - direct connection or OAuth
                await handleDirectConnection(sourceShortName, sourceName, collectionId, details);
                // Call onComplete immediately for direct connections
                if (onComplete) {
                    onComplete();
                }
            }
        } catch (error) {
            console.error("❌ [ConnectToSourceFlow] Error initiating connection:", error);
            toast.error("Failed to initiate connection to source");
            navigate(`/collections/${collectionId}?connected=error`);
        }
    };

    // =========================================
    // FLOW 1: Source requires configuration fields
    // =========================================
    const handleConfigFieldsAuth = async (
        sourceShortName: string,
        sourceName: string,
        collectionId: string,
        sourceDetails: SourceDetails,
        onComplete?: () => void
    ) => {
        console.log("🛠️ [ConnectToSourceFlow] Source requires configuration - opening dialog");

        // Store onComplete callback to use after config dialog is done
        const handleDialogComplete = (connectionId: string) => {
            console.log("🎉 [ConnectToSourceFlow] Config completed, calling original onComplete");
            if (onComplete) {
                onComplete();
            }
        };

        // Open configuration dialog and hand over control
        setSourceConnectionConfig({
            name: sourceName,
            short_name: sourceShortName,
            sourceDetails: sourceDetails,
            collectionId: collectionId,
            onConfigComplete: handleDialogComplete // Pass the callback
        });
        setConfigDialogOpen(true);

        console.log("👋 [ConnectToSourceFlow] Control passed to SourceConfigDialog");
    };

    // =========================================
    // FLOW 2: Source with no config (direct connection or OAuth)
    // =========================================
    const handleDirectConnection = async (
        sourceShortName: string,
        sourceName: string,
        collectionId: string,
        sourceDetails?: SourceDetails
    ) => {
        console.log("🔌 [ConnectToSourceFlow] Handling direct connection for auth type:", sourceDetails?.auth_type);

        const authType = sourceDetails?.auth_type;

        if (authType === "none" || authType === "basic") {
            // No auth or basic auth - create source connection directly
            console.log("⚡ [ConnectToSourceFlow] Creating source connection directly (no/basic auth)");
            await createDirectSourceConnection(sourceShortName, sourceName, collectionId);
        }
        else if (authType?.startsWith("oauth2")) {
            // OAuth2 with no config fields - start OAuth flow
            console.log("🔐 [ConnectToSourceFlow] Starting OAuth flow (no config fields)");
            await initiateOAuthFlow(sourceShortName, sourceName, collectionId);
        }
        else {
            // Fallback for other auth types
            console.log("⚡ [ConnectToSourceFlow] Creating direct connection (unknown auth type)");
            await createDirectSourceConnection(sourceShortName, sourceName, collectionId);
        }
    };

    // Create a source connection directly (no auth or basic auth)
    const createDirectSourceConnection = async (
        sourceShortName: string,
        sourceName: string,
        collectionId: string,
    ) => {
        console.log("📝 [ConnectToSourceFlow] Creating direct source connection for:", sourceShortName);

        try {
            const payload = {
                name: `My ${sourceName}`,
                short_name: sourceShortName,
                collection: collectionId,
                sync_immediately: true
            };

            console.log("📤 [ConnectToSourceFlow] Request payload:", payload);
            const response = await apiClient.post("/source-connections/", payload);

            if (!response.ok) {
                throw new Error("Failed to create source connection");
            }

            console.log("✅ [ConnectToSourceFlow] Connection created successfully");
            toast.success("Connection created successfully");
            navigate(`/collections/${collectionId}?connected=success`);
        } catch (error) {
            console.error("❌ [ConnectToSourceFlow] Error creating source connection:", error);
            toast.error("Failed to create source connection");
            navigate(`/collections/${collectionId}?connected=error`);
        }
    };

    // =========================================
    // FLOW 3: OAuth handling
    // =========================================
    const initiateOAuthFlow = async (
        sourceShortName: string,
        sourceName: string,
        collectionId: string
    ) => {
        console.log("🔐 [ConnectToSourceFlow] Setting up OAuth flow for:", sourceShortName);

        try {
            // Store the collection ID for after OAuth completes
            localStorage.setItem(OAUTH_RETURN_URL_KEY, `/collections/${collectionId}`);
            localStorage.setItem(OAUTH_COLLECTION_ID_KEY, collectionId);
            console.log("💾 [ConnectToSourceFlow] Stored OAuth data in localStorage");

            const storageKey = `oauth2_config_${sourceShortName}`;

            // Check if we have config from a previous step
            // Only create new config if none exists - don't overwrite!
            if (!sessionStorage.getItem(storageKey)) {
                console.log("📝 [ConnectToSourceFlow] No existing config, creating minimal OAuth config");
                // Basic config for sources that don't need extra fields
                const connectionConfig = {
                    name: `${sourceName} Connection`,
                    connection_name: `${sourceName} Connection`,
                    auth_fields: {} // Empty for sources without config fields
                };
                sessionStorage.setItem(storageKey, JSON.stringify(connectionConfig));
            } else {
                console.log("📋 [ConnectToSourceFlow] Using existing OAuth config from wizard");
            }

            // Get the auth URL
            const resp = await apiClient.get(`/connections/oauth2/source/auth_url?short_name=${sourceShortName}`);
            if (!resp.ok) {
                throw new Error("Failed to retrieve auth URL");
            }

            const authUrl = await resp.text();
            const cleanUrl = authUrl.replace(/^"|"$/g, ''); // Remove surrounding quotes
            console.log("🔗 [ConnectToSourceFlow] Received OAuth URL - redirecting to provider");

            // Control now passes to the OAuth provider
            console.log("👋 [ConnectToSourceFlow] Control passed to OAuth provider");
            window.location.href = cleanUrl;

            // When OAuth redirect comes back, AuthCallback.tsx takes over
        } catch (error) {
            console.error("❌ [ConnectToSourceFlow] OAuth initialization error:", error);
            toast.error("Failed to start authentication flow");
            navigate(`/collections/${collectionId}?connected=error`);
        }
    };

    // =========================================
    // CALLBACK: Handle wizard completion
    // =========================================
    const handleConfigComplete = (connectionId: string) => {
        console.log("🎉 [ConnectToSourceFlow] Config dialog completed with ID:", connectionId);

        if (!sourceConnectionConfig?.collectionId) {
            console.error("❌ [ConnectToSourceFlow] No collection ID found in config");
            return;
        }

        // DECISION POINT: ID starting with "oauth2_" means OAuth flow needs to continue
        if (connectionId.startsWith("oauth2_")) {
            console.log("🔄 [ConnectToSourceFlow] Config stored, continuing OAuth flow");
            // Wizard stored config in session storage, now continue with OAuth
            initiateOAuthFlow(
                sourceConnectionConfig.short_name,
                sourceConnectionConfig.name,
                sourceConnectionConfig.collectionId
            );
        } else {
            // For config_class auth types, AddSourceWizard already created the complete source connection
            console.log("✅ [ConnectToSourceFlow] Source connection created by wizard with ID:", connectionId);

            // Just navigate to success page - no more API calls needed
            navigate(`/collections/${sourceConnectionConfig.collectionId}?connected=success`);
        }
    };

    // =========================================
    // RENDER: Connection wizard if needed
    // =========================================
    const renderConfigDialog = () => {
        if (!sourceConnectionConfig) {
            return null;
        }

        console.log("🪟 [ConnectToSourceFlow] Rendering source config dialog");
        return (
            <SourceConfigDialog
                open={configDialogOpen}
                onOpenChange={(open) => setConfigDialogOpen(open)}
                onComplete={(connectionId) => {
                    console.log("🪟 [ConnectToSourceFlow] Config dialog reported completion");
                    handleConfigComplete(connectionId);
                }}
                shortName={sourceConnectionConfig.short_name}
                name={sourceConnectionConfig.name}
                sourceDetails={sourceConnectionConfig.sourceDetails}
                collectionId={sourceConnectionConfig.collectionId}
            />
        );
    };

    return {
        initiateConnection,
        configDialogOpen,
        renderConfigDialog,
    };
};

// Component that encapsulates the connection flow
export const ConnectToSourceFlow: React.FC<ConnectToSourceFlowProps> = ({
    sourceShortName,
    sourceName,
    collectionId,
    onComplete,
    onError
}) => {
    const { initiateConnection, renderConfigDialog } = useConnectToSourceFlow();

    // Start the connection process on mount
    useEffect(() => {
        console.log("⚡ [ConnectToSourceFlow] Component mounted, starting connection process");
        initiateConnection(sourceShortName, sourceName, collectionId).catch(error => {
            console.error("❌ [ConnectToSourceFlow] Connection process failed:", error);
            if (onError) onError(error instanceof Error ? error : new Error(String(error)));
        });

        return () => {
            console.log("🧹 [ConnectToSourceFlow] Component unmounting, cleanup running");
        };
    }, [sourceShortName, sourceName, collectionId]);

    // Render the dialog if needed
    return renderConfigDialog();
};

// Export constants for use in other components like AuthCallback
export const OAUTH_KEYS = {
    RETURN_URL: OAUTH_RETURN_URL_KEY,
    COLLECTION_ID: OAUTH_COLLECTION_ID_KEY
};

export default ConnectToSourceFlow;
