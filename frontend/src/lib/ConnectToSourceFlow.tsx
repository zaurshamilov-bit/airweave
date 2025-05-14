/**
 * ConnectToSourceFlow.tsx
 *
 * This is the data and API interaction layer for connecting sources to collections.
 * It handles all API operations related to creating collections, establishing source
 * connections, and managing OAuth flows.
 *
 * Key responsibilities:
 * 1. Initiating source connections based on configuration
 * 2. Creating collections and source connections in the backend
 * 3. Managing OAuth authentication flows for sources that require it
 * 4. Handling API responses and error states
 *
 * This component works in conjunction with ConnectFlow.tsx, which manages the UI layer.
 * The typical flow is:
 * 1. ConnectFlow collects user input (collection details, source config)
 * 2. ConnectToSourceFlow performs the API operations
 * 3. For OAuth sources, AuthCallback.tsx handles the redirect return
 */

import { useState, useEffect, useRef } from "react";
import { useNavigate } from "react-router-dom";
import { apiClient } from "@/lib/api";
import { redirectWithError } from "@/lib/error-utils";

/**
 * Interface for source details returned from the API
 */
interface SourceDetails {
    name: string;
    description?: string;
    short_name: string;
    auth_type?: string;
    auth_fields?: {
        fields: any[];
    };
}

/**
 * Interface for collection details
 */
interface CollectionDetails {
    name: string;
    readable_id?: string;
}

/**
 * Interface for source configuration data
 * Collected by ConnectFlow and passed to initiateConnection
 */
interface SourceConfig {
    name: string;
    auth_fields: Record<string, string>;
}

/**
 * Props for the ConnectToSourceFlow component
 */
interface ConnectToSourceFlowProps {
    /** Short name identifier for the source type (e.g., "notion", "github") */
    sourceShortName: string;
    /** Display name of the source */
    sourceName: string;
    /** Collection details where source will be connected */
    collectionDetails: CollectionDetails;
    /** Optional callback when connection completes successfully */
    onComplete?: () => void;
    /** Optional callback when connection fails */
    onError?: (error: Error) => void;
}

/**
 * Interface for OAuth redirect information
 */
interface OAuthRedirectInfo {
    oauthRedirect: boolean;
    authUrl: string;
    collectionDetails: CollectionDetails;
}

// LocalStorage keys for OAuth flow data persistence
const OAUTH_RETURN_URL_KEY = "oauth_return_url";
const OAUTH_COLLECTION_ID_KEY = "oauth_collection_id";
const OAUTH_COLLECTION_DETAILS_KEY = "oauth_collection_details";

/**
 * Hook that provides all source connection functionality
 *
 * This hook is the core of the connection process, providing methods
 * to initiate connections and handle different authentication types.
 */
export const useConnectToSourceFlow = () => {
    const navigate = useNavigate();

    /**
     * Redirects to dashboard with error information using the common error utility
     */
    const redirectToErrorPage = (error: Error, sourceName?: string) => {
        // Use the common utility
        redirectWithError(navigate, error, sourceName);
    };

    /**
     * Main entry point for initiating a source connection
     *
     * This function:
     * 1. Fetches source details if not provided
     * 2. Determines connection path based on source auth type and config
     * 3. Routes to appropriate specialized handler
     *
     * @param sourceShortName - Identifier for the source type
     * @param sourceName - Display name of the source
     * @param collectionDetails - Details for collection to create/connect to
     * @param sourceDetails - Optional pre-fetched source details
     * @param onComplete - Optional callback when process completes
     * @param preCollectedConfig - Optional configuration collected from UI
     * @returns For OAuth sources, returns an object with redirect information
     */
    const initiateConnection = async (
        sourceShortName: string,
        sourceName: string,
        collectionDetails: CollectionDetails,
        sourceDetails?: SourceDetails,
        onComplete?: () => void,
        preCollectedConfig?: SourceConfig // Configuration from ConnectFlow
    ) => {
        console.log("🚀 [ConnectToSourceFlow] Initiating connection:", {
            sourceShortName,
            sourceName,
            collectionDetails,
            hasSourceDetails: !!sourceDetails,
            hasPreCollectedConfig: !!preCollectedConfig
        });

        try {
            // If sourceDetails is not provided, fetch them
            let details = sourceDetails;
            if (!details) {
                console.log("🔍 [ConnectToSourceFlow] Fetching source details for:", sourceShortName);
                const response = await apiClient.get(`/sources/detail/${sourceShortName}`);
                if (!response.ok) {
                    throw new Error(`Failed to fetch source details: ${await response.text()}`);
                }
                details = await response.json();
                console.log("📥 [ConnectToSourceFlow] Received source details:", details);
            }

            const authType = details?.auth_type;
            console.log("🔑 [ConnectToSourceFlow] Auth type:", authType);

            // DECISION POINT: Route to appropriate flow based on auth type and config
            if (preCollectedConfig) {
                // If we already have config from ConnectFlow, use it directly
                console.log("📋 [ConnectToSourceFlow] Using pre-collected config");

                if (authType?.startsWith("oauth2")) {
                    // Store config for OAuth flow
                    const storageKey = `oauth2_config_${sourceShortName}`;
                    sessionStorage.setItem(storageKey, JSON.stringify({
                        connection_name: preCollectedConfig.name,
                        auth_fields: preCollectedConfig.auth_fields
                    }));

                    // Proceed with OAuth flow
                    const oauthResult = await handleDirectConnection(sourceShortName, sourceName, collectionDetails, details);
                    if (oauthResult && oauthResult.oauthRedirect) {
                        return oauthResult;
                    }
                } else {
                    // For non-OAuth sources, create the connection directly with config
                    await createConfiguredSourceConnection(
                        sourceShortName,
                        preCollectedConfig.name,
                        collectionDetails,
                        preCollectedConfig.auth_fields
                    );
                }

                // Call onComplete if provided and not OAuth
                if (onComplete && authType !== "oauth2" && !authType?.startsWith("oauth2")) {
                    onComplete();
                }
            }
            else if (details?.auth_fields?.fields && details.auth_fields.fields.length > 0) {
                // LEGACY PATH: This should rarely be used now that ConnectFlow handles config collection
                console.log("⚠️ [ConnectToSourceFlow] No pre-collected config for source that requires config");
                throw new Error("Configuration required but not provided");
            }
            else {
                // No config fields required - direct connection or OAuth
                const result = await handleDirectConnection(sourceShortName, sourceName, collectionDetails, details);

                // If OAuth flow, return OAuth information for redirect
                if (result && result.oauthRedirect) {
                    console.log("🚀 [ConnectToSourceFlow] Returning OAuth redirect info to caller");
                    return result;
                }

                // Only call onComplete for non-OAuth flows (OAuth will complete via redirect)
                if (onComplete && authType !== "oauth2" && !authType?.startsWith("oauth2")) {
                    onComplete();
                }
            }
        } catch (error) {
            console.error("❌ [ConnectToSourceFlow] Error initiating connection:", error);

            // Redirect to dashboard with error details
            redirectToErrorPage(
                error instanceof Error ? error : new Error(String(error)),
                sourceName || sourceShortName
            );

            // Re-throw the error for the caller to handle
            throw error;
        }
    };

    /**
     * Creates a source connection with provided configuration
     *
     * Used for sources that need configuration (API keys, credentials, etc.)
     *
     * @param sourceShortName - Identifier for the source type
     * @param connectionName - Name for the new connection
     * @param collectionDetails - Collection to connect to
     * @param authFields - Authentication fields (credentials, API keys, etc.)
     */
    const createConfiguredSourceConnection = async (
        sourceShortName: string,
        connectionName: string,
        collectionDetails: CollectionDetails,
        authFields: Record<string, string>
    ) => {
        console.log("📝 [ConnectToSourceFlow] Creating configured source connection for:", sourceShortName);

        try {
            // First check if collection already exists
            let collectionId;
            if (collectionDetails.readable_id) {
                console.log("ℹ️ [ConnectToSourceFlow] Using existing collection:", collectionDetails.readable_id);
                collectionId = collectionDetails.readable_id;
            } else {
                // Create new collection (existing code)
                console.log("📝 [ConnectToSourceFlow] Creating collection first:", collectionDetails);
                const collectionResponse = await apiClient.post("/collections/", collectionDetails);

                if (!collectionResponse.ok) {
                    const errorText = await collectionResponse.text();
                    throw new Error(`Failed to create collection: ${errorText}`);
                }

                const collection = await collectionResponse.json();
                collectionId = collection.readable_id;
                console.log("✅ [ConnectToSourceFlow] Collection created successfully:", collection);
            }

            // Now create the source connection with auth fields
            const payload = {
                name: connectionName,
                short_name: sourceShortName,
                collection: collectionId,
                auth_fields: authFields,
                sync_immediately: true
            };

            console.log("📤 [ConnectToSourceFlow] Request payload:", {
                ...payload,
                auth_fields: "REDACTED" // Don't log auth fields
            });

            // =====================================================================
            // BACKEND SOURCE CONNECTION CREATION - IMPORTANT DATABASE OPERATION
            // This is where a new SOURCE CONNECTION is created in the database
            // POST /source-connections/ endpoint creates a persistent source connection
            // record with the provided authentication fields in source_connections.py
            // =====================================================================
            const response = await apiClient.post("/source-connections/", payload);

            if (!response.ok) {
                const errorText = await response.text();
                throw new Error(`Failed to create source connection: ${errorText}`);
            }

            console.log("✅ [ConnectToSourceFlow] Connection created successfully");

            // Return the collection ID
            return collectionId;
        } catch (error) {
            console.error("❌ [ConnectToSourceFlow] Error creating source connection:", error);

            // Redirect to dashboard with error details
            redirectToErrorPage(
                error instanceof Error ? error : new Error(String(error)),
                sourceShortName
            );

            // Re-throw the error for the caller to handle
            throw error;
        }
    };

    /**
     * Handles connections for sources with no config fields
     *
     * Routes to specific handlers based on auth type:
     * - OAuth sources: Redirects to provider authorization
     * - Basic/No auth: Creates direct connection
     *
     * @param sourceShortName - Identifier for the source type
     * @param sourceName - Display name of the source
     * @param collectionDetails - Collection to connect to
     * @param sourceDetails - Source details with auth_type information
     * @returns For OAuth sources, an object with OAuth redirect info
     */
    const handleDirectConnection = async (
        sourceShortName: string,
        sourceName: string,
        collectionDetails: CollectionDetails,
        sourceDetails?: SourceDetails
    ): Promise<OAuthRedirectInfo | undefined> => {
        console.log("🔌 [ConnectToSourceFlow] Handling direct connection for auth type:", sourceDetails?.auth_type);

        const authType = sourceDetails?.auth_type;

        if (authType === "none" || authType === "basic") {
            // No auth or basic auth - create source connection directly
            console.log("⚡ [ConnectToSourceFlow] Creating source connection directly (no/basic auth)");
            await createDirectSourceConnection(sourceShortName, sourceName, collectionDetails);
            return undefined;
        }
        else if (authType?.startsWith("oauth2")) {
            // OAuth2 with no config fields - start OAuth flow
            console.log("🔐 [ConnectToSourceFlow] Starting OAuth flow (no config fields)");
            return await initiateOAuthFlow(sourceShortName, sourceName, collectionDetails);
        }
        else {
            // Fallback for other auth types
            console.log("⚡ [ConnectToSourceFlow] Creating direct connection (unknown auth type)");
            await createDirectSourceConnection(sourceShortName, sourceName, collectionDetails);
            return undefined;
        }
    };

    /**
     * Creates a source connection without configuration
     *
     * Used for sources that don't require auth or have basic auth
     *
     * @param sourceShortName - Identifier for the source type
     * @param sourceName - Display name of the source
     * @param collectionDetails - Collection to connect to
     */
    const createDirectSourceConnection = async (
        sourceShortName: string,
        sourceName: string,
        collectionDetails: CollectionDetails,
    ) => {
        console.log("📝 [ConnectToSourceFlow] Creating direct source connection for:", sourceShortName);

        try {
            // First check if collection already exists
            let collectionId;
            if (collectionDetails.readable_id) {
                console.log("ℹ️ [ConnectToSourceFlow] Using existing collection:", collectionDetails.readable_id);
                collectionId = collectionDetails.readable_id;
            } else {
                // Create new collection (existing code)
                console.log("📝 [ConnectToSourceFlow] Creating collection first:", collectionDetails);
                const collectionResponse = await apiClient.post("/collections/", collectionDetails);

                if (!collectionResponse.ok) {
                    const errorText = await collectionResponse.text();
                    throw new Error(`Failed to create collection: ${errorText}`);
                }

                const collection = await collectionResponse.json();
                collectionId = collection.readable_id;
                console.log("✅ [ConnectToSourceFlow] Collection created successfully:", collection);
            }

            // Now create the source connection
            const payload = {
                name: `My ${sourceName}`,
                short_name: sourceShortName,
                collection: collectionId,
                sync_immediately: true
            };

            console.log("📤 [ConnectToSourceFlow] Request payload:", payload);

            // =====================================================================
            // BACKEND SOURCE CONNECTION CREATION - IMPORTANT DATABASE OPERATION
            // This is where a new SOURCE CONNECTION is created in the database
            // POST /source-connections/ endpoint creates a persistent source connection
            // record without authentication fields (for no-auth/basic sources)
            // in source_connections.py
            // =====================================================================
            const response = await apiClient.post("/source-connections/", payload);

            if (!response.ok) {
                const errorText = await response.text();
                throw new Error(`Failed to create source connection: ${errorText}`);
            }

            console.log("✅ [ConnectToSourceFlow] Connection created successfully");

            // Return the collection ID
            return collectionId;
        } catch (error) {
            console.error("❌ [ConnectToSourceFlow] Error creating source connection:", error);

            // Redirect to dashboard with error details
            redirectToErrorPage(
                error instanceof Error ? error : new Error(String(error)),
                sourceName || sourceShortName
            );

            // Re-throw the error for the caller to handle
            throw error;
        }
    };

    /**
     * Initiates OAuth flow for OAuth-based sources
     *
     * This function:
     * 1. Stores necessary data in localStorage for after redirect
     * 2. Gets the authorization URL from the backend
     * 3. Returns an object with the OAuth URL for redirection
     *
     * After authorization, the flow continues in AuthCallback.tsx
     *
     * @param sourceShortName - Identifier for the source type
     * @param sourceName - Display name of the source
     * @param collectionDetails - Collection to connect to
     * @returns Object with OAuth redirect information
     */
    const initiateOAuthFlow = async (
        sourceShortName: string,
        sourceName: string,
        collectionDetails: CollectionDetails
    ): Promise<OAuthRedirectInfo> => {
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
                const errorText = await resp.text();
                throw new Error(`Failed to retrieve auth URL: ${errorText}`);
            }

            const authUrl = await resp.text();
            const cleanUrl = authUrl.replace(/^"|"$/g, ''); // Remove surrounding quotes
            console.log("🔗 [ConnectToSourceFlow] Received OAuth URL - redirecting to provider:", cleanUrl);

            // Return the OAuth redirect information
            return {
                oauthRedirect: true,
                authUrl: cleanUrl,
                collectionDetails
            };
        } catch (error) {
            console.error("❌ [ConnectToSourceFlow] OAuth initialization error:", error);

            // Redirect to dashboard with error details
            redirectToErrorPage(
                error instanceof Error ? error : new Error(String(error)),
                sourceName || sourceShortName
            );

            // Re-throw the error for the caller to handle
            throw error;
        }
    };

    /**
     * Perform the actual OAuth redirection
     * This is a convenience method that immediately redirects the browser
     *
     * @param url OAuth authorization URL
     */
    const performOAuthRedirect = (url: string) => {
        console.log("🚀 [ConnectToSourceFlow] Redirecting to OAuth provider:", url);
        // Use window.location.href for actual browser redirection
        window.location.href = url;
    };

    return {
        initiateConnection,
        performOAuthRedirect,
        redirectToErrorPage
    };
};

/**
 * ConnectToSourceFlow Component
 *
 * A component wrapper around the useConnectToSourceFlow hook.
 * Used to initiate a connection flow directly in component form.
 *
 * Note: This component starts the connection process immediately on mount
 * and is rarely used directly - typically the hook is preferred.
 */
export const ConnectToSourceFlow: React.FC<ConnectToSourceFlowProps> = ({
    sourceShortName,
    sourceName,
    collectionDetails,
    onComplete,
    onError
}) => {
    const { initiateConnection, redirectToErrorPage } = useConnectToSourceFlow();

    // Start the connection process on mount
    useEffect(() => {
        console.log("⚡ [ConnectToSourceFlow] Component mounted, starting connection process");
        initiateConnection(sourceShortName, sourceName, collectionDetails).then(result => {
            // Check if we got OAuth redirect info
            if (result && result.oauthRedirect && result.authUrl) {
                console.log("🔄 [ConnectToSourceFlow] Redirecting to OAuth provider:", result.authUrl);
                window.location.href = result.authUrl;
            }
        }).catch(error => {
            console.error("❌ [ConnectToSourceFlow] Connection process failed:", error);

            // Redirect to dashboard with error parameters
            redirectToErrorPage(
                error instanceof Error ? error : new Error(String(error)),
                sourceName || sourceShortName
            );

            // Also call the onError callback if provided
            if (onError) onError(error instanceof Error ? error : new Error(String(error)));
        });

        return () => {
            console.log("🧹 [ConnectToSourceFlow] Component unmounting, cleanup running");
        };
    }, [sourceShortName, sourceName, collectionDetails]);

    // No need to render anything - this is just a controller component
    return null;
};

/**
 * Export constants for use in other components like AuthCallback
 * These keys are used to store/retrieve data during the OAuth flow
 */
export const OAUTH_KEYS = {
    RETURN_URL: OAUTH_RETURN_URL_KEY,
    COLLECTION_ID: OAUTH_COLLECTION_ID_KEY,
    COLLECTION_DETAILS: OAUTH_COLLECTION_DETAILS_KEY
};

export default ConnectToSourceFlow;
