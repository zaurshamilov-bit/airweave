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

// Add interface for collection details
interface CollectionDetails {
    name: string;
    readable_id?: string;
}

interface ConnectToSourceFlowProps {
    sourceShortName: string;
    sourceName: string;
    collectionDetails: CollectionDetails;
    onComplete?: () => void;
    onError?: (error: Error) => void;
}

// Update constants for local storage keys to include collection details
const OAUTH_RETURN_URL_KEY = "oauth_return_url";
const OAUTH_COLLECTION_ID_KEY = "oauth_collection_id";
const OAUTH_COLLECTION_DETAILS_KEY = "oauth_collection_details";

// Hook that provides all the connection flow logic
export const useConnectToSourceFlow = () => {
    const [configDialogOpen, setConfigDialogOpen] = useState(false);
    const [sourceConnectionConfig, setSourceConnectionConfig] = useState<{
        name: string;
        short_name: string;
        sourceDetails?: any;
        collectionDetails?: any;
        onConfigComplete?: (connectionId: string) => void;
    } | null>(null);
    const navigate = useNavigate();

    // =========================================
    // MAIN ENTRY POINT: Initiate connection
    // =========================================
    const initiateConnection = async (
        sourceShortName: string,
        sourceName: string,
        collectionDetails: CollectionDetails,
        sourceDetails?: SourceDetails,
        onComplete?: () => void
    ) => {
        console.log("🚀 [ConnectToSourceFlow] Initiating connection:", {
            sourceShortName,
            sourceName,
            collectionDetails,
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
                // Has config fields - open the wizard
                await handleConfigFieldsAuth(sourceShortName, sourceName, collectionDetails, details, onComplete);
            }
            else {
                // No config fields required - direct connection or OAuth
                await handleDirectConnection(sourceShortName, sourceName, collectionDetails, details);

                // Only call onComplete for non-OAuth flows (OAuth will complete via redirect)
                if (onComplete && authType !== "oauth2" && !authType?.startsWith("oauth2")) {
                    onComplete();
                }
            }
        } catch (error) {
            console.error("❌ [ConnectToSourceFlow] Error initiating connection:", error);
            toast.error("Failed to initiate connection to source");
            navigate(`/dashboard?connected=error`);
        }
    };

    // =========================================
    // FLOW 1: Source requires configuration fields
    // =========================================
    const handleConfigFieldsAuth = async (
        sourceShortName: string,
        sourceName: string,
        collectionDetails: CollectionDetails,
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

        // Open configuration dialog and hand over control with collection details
        setSourceConnectionConfig({
            name: sourceName,
            short_name: sourceShortName,
            sourceDetails: sourceDetails,
            collectionDetails: collectionDetails,
            onConfigComplete: handleDialogComplete
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
        collectionDetails: CollectionDetails,
        sourceDetails?: SourceDetails
    ) => {
        console.log("🔌 [ConnectToSourceFlow] Handling direct connection for auth type:", sourceDetails?.auth_type);

        const authType = sourceDetails?.auth_type;

        if (authType === "none" || authType === "basic") {
            // No auth or basic auth - create source connection directly
            console.log("⚡ [ConnectToSourceFlow] Creating source connection directly (no/basic auth)");
            await createDirectSourceConnection(sourceShortName, sourceName, collectionDetails);
        }
        else if (authType?.startsWith("oauth2")) {
            // OAuth2 with no config fields - start OAuth flow
            console.log("🔐 [ConnectToSourceFlow] Starting OAuth flow (no config fields)");
            await initiateOAuthFlow(sourceShortName, sourceName, collectionDetails);
        }
        else {
            // Fallback for other auth types
            console.log("⚡ [ConnectToSourceFlow] Creating direct connection (unknown auth type)");
            await createDirectSourceConnection(sourceShortName, sourceName, collectionDetails);
        }
    };

    // Create a source connection directly (no auth or basic auth)
    const createDirectSourceConnection = async (
        sourceShortName: string,
        sourceName: string,
        collectionDetails: CollectionDetails,
    ) => {
        console.log("📝 [ConnectToSourceFlow] Creating direct source connection for:", sourceShortName);

        try {
            // First create the collection
            console.log("📝 [ConnectToSourceFlow] Creating collection first:", collectionDetails);
            const collectionResponse = await apiClient.post("/collections/", collectionDetails);

            if (!collectionResponse.ok) {
                const errorText = await collectionResponse.text();
                throw new Error(`Failed to create collection: ${errorText}`);
            }

            const collection = await collectionResponse.json();
            const collectionId = collection.readable_id;
            console.log("✅ [ConnectToSourceFlow] Collection created successfully:", collection);

            // Now create the source connection
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
            navigate(`/dashboard?connected=error`);
        }
    };

    // =========================================
    // FLOW 3: OAuth handling
    // =========================================
    const initiateOAuthFlow = async (
        sourceShortName: string,
        sourceName: string,
        collectionDetails: CollectionDetails
    ) => {
        console.log("🔐 [ConnectToSourceFlow] Setting up OAuth flow for:", sourceShortName);

        try {
            // Store the collection details for after OAuth completes
            localStorage.setItem(OAUTH_RETURN_URL_KEY, `/dashboard`);
            localStorage.setItem(OAUTH_COLLECTION_DETAILS_KEY, JSON.stringify(collectionDetails));
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
            navigate(`/dashboard?connected=error`);
        }
    };

    // =========================================
    // CALLBACK: Handle wizard completion
    // =========================================
    const handleConfigComplete = (connectionId: string) => {
        console.log("🎉 [ConnectToSourceFlow] Config dialog completed with ID:", connectionId);

        if (!sourceConnectionConfig?.collectionDetails) {
            console.error("❌ [ConnectToSourceFlow] No collection details found in config");
            return;
        }

        // DECISION POINT: ID starting with "oauth2_" means OAuth flow needs to continue
        if (connectionId.startsWith("oauth2_")) {
            console.log("🔄 [ConnectToSourceFlow] Config stored, continuing OAuth flow");
            // Wizard stored config in session storage, now continue with OAuth
            initiateOAuthFlow(
                sourceConnectionConfig.short_name,
                sourceConnectionConfig.name,
                sourceConnectionConfig.collectionDetails
            );
        } else {
            // For config_class auth types, SourceConfigDialog already created the collection and source connection
            console.log("✅ [ConnectToSourceFlow] Source connection created by wizard with ID:", connectionId);

            // Just navigate to success page - we'll get the collectionId from the returned data
            const sourceConnection = JSON.parse(sessionStorage.getItem('last_created_source_connection') || '{}');
            const collectionId = sourceConnection.collection;

            if (collectionId) {
                navigate(`/collections/${collectionId}?connected=success`);
            } else {
                navigate(`/dashboard?connected=success`);
            }
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
                collectionDetails={sourceConnectionConfig.collectionDetails}
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
    collectionDetails,
    onComplete,
    onError
}) => {
    const { initiateConnection, renderConfigDialog } = useConnectToSourceFlow();

    // Start the connection process on mount
    useEffect(() => {
        console.log("⚡ [ConnectToSourceFlow] Component mounted, starting connection process");
        initiateConnection(sourceShortName, sourceName, collectionDetails).catch(error => {
            console.error("❌ [ConnectToSourceFlow] Connection process failed:", error);
            if (onError) onError(error instanceof Error ? error : new Error(String(error)));
        });

        return () => {
            console.log("🧹 [ConnectToSourceFlow] Component unmounting, cleanup running");
        };
    }, [sourceShortName, sourceName, collectionDetails]);

    // Render the dialog if needed
    return renderConfigDialog();
};

// Export constants for use in other components like AuthCallback
export const OAUTH_KEYS = {
    RETURN_URL: OAUTH_RETURN_URL_KEY,
    COLLECTION_ID: OAUTH_COLLECTION_ID_KEY,
    COLLECTION_DETAILS: OAUTH_COLLECTION_DETAILS_KEY
};

export default ConnectToSourceFlow;
